"""
智能搜索驅動爬蟲 v3
基於Google Search API和LLM的智能關鍵字策略
"""

import os
import asyncio
import json
import logging
from typing import List, Dict, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
import uuid

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, CacheMode
from .google_search_integration import (
    GoogleSearchAPI, 
    GoogleSearchConfig, 
    SearchResult, 
    IntelligentKeywordGenerator,
    create_google_search_config_from_env
)

logger = logging.getLogger(__name__)

@dataclass
class TaskObjectiveV3:
    """任務目標定義 v3"""
    title: str
    description: str
    initial_keywords: List[str] = field(default_factory=list)
    output_format: str = "structured"  # "structured" or "summary"
    max_iterations: int = 3  # 最大迭代次數
    target_confidence: float = 0.85  # 目標信心度
    max_total_pages: int = 50  # 最大總頁面數
    max_search_results_per_keyword: int = 10  # 每個關鍵字最大搜索結果數
    enable_keyword_refinement: bool = True  # 啟用關鍵字優化
    time_priority: bool = True  # 時間優先級
    require_taiwan_sources: bool = False  # 是否要求台灣來源

@dataclass
class CrawlPageResult:
    """爬蟲頁面結果"""
    url: str
    title: str
    content: str
    summary: str
    relevance_score: float
    confidence_score: float
    is_helpful: bool
    crawl_time: datetime
    source_keyword: str  # 來源關鍵字
    search_rank: int     # 搜索排名
    error_message: str = ""
    success: bool = True

@dataclass
class IterationResult:
    """迭代結果"""
    iteration_number: int
    keywords_used: List[str]
    search_results: List[SearchResult] = field(default_factory=list)
    crawled_pages: List[CrawlPageResult] = field(default_factory=list)
    confidence_score: float = 0.0
    new_keywords_generated: List[str] = field(default_factory=list)
    should_continue: bool = True

@dataclass
class SmartCrawlResult:
    """智能爬蟲最終結果"""
    task_id: str
    objective: TaskObjectiveV3
    iterations: List[IterationResult] = field(default_factory=list)
    final_confidence: float = 0.0
    total_pages_crawled: int = 0
    total_keywords_used: int = 0
    execution_time: float = 0.0
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    summary: str = ""
    structured_data: List[Dict] = field(default_factory=list)

class SmartSearchCrawler:
    """智能搜索爬蟲"""
    
    def __init__(self, llm_config: LLMConfig, google_config: Optional[GoogleSearchConfig] = None):
        self.llm_config = llm_config
        self.google_config = google_config or create_google_search_config_from_env()
        self.google_search = GoogleSearchAPI(self.google_config)
        self.keyword_generator = IntelligentKeywordGenerator(llm_config)
        self.crawled_urls: Set[str] = set()
        
    async def execute_smart_crawl(self, objective: TaskObjectiveV3) -> SmartCrawlResult:
        """執行智能搜索爬蟲"""
        task_id = str(uuid.uuid4())[:8]
        result = SmartCrawlResult(
            task_id=task_id,
            objective=objective,
            start_time=datetime.now(),
            status="running"
        )
        
        try:
            logger.info(f"開始執行智能搜索任務: {objective.title}")
            
            # 初始化關鍵字
            current_keywords = objective.initial_keywords.copy()
            if not current_keywords:
                logger.info("生成初始關鍵字...")
                current_keywords = await self.keyword_generator.generate_initial_keywords(
                    objective.title, objective.description
                )
            
            total_crawled_pages = 0
            all_crawled_results = []
            
            # 執行迭代搜索和爬蟲
            for iteration in range(objective.max_iterations):
                logger.info(f"=== 迭代 {iteration + 1}/{objective.max_iterations} ===")
                
                iteration_result = IterationResult(
                    iteration_number=iteration + 1,
                    keywords_used=current_keywords.copy()
                )
                
                # 階段1：Google搜索
                logger.info(f"使用關鍵字搜索: {current_keywords}")
                search_results = await self._perform_google_search(current_keywords, objective)
                iteration_result.search_results = search_results
                
                # 階段2：爬蟲和分析
                logger.info(f"開始爬蟲 {len(search_results)} 個搜索結果...")
                crawl_results = await self._crawl_search_results(search_results, objective)
                iteration_result.crawled_pages = crawl_results
                
                # 更新總計數據
                total_crawled_pages += len(crawl_results)
                all_crawled_results.extend(crawl_results)
                
                # 階段3：評估信心度
                confidence = await self._calculate_iteration_confidence(crawl_results, objective)
                iteration_result.confidence_score = confidence
                
                logger.info(f"迭代 {iteration + 1} 完成，信心度: {confidence:.2%}")
                
                # 檢查是否達到目標或限制
                if confidence >= objective.target_confidence:
                    logger.info(f"達到目標信心度 {objective.target_confidence:.2%}")
                    iteration_result.should_continue = False
                elif total_crawled_pages >= objective.max_total_pages:
                    logger.info(f"達到最大頁面數限制 {objective.max_total_pages}")
                    iteration_result.should_continue = False
                elif iteration == objective.max_iterations - 1:
                    logger.info("達到最大迭代次數")
                    iteration_result.should_continue = False
                
                result.iterations.append(iteration_result)
                
                # 階段4：如果需要繼續，生成新關鍵字
                if iteration_result.should_continue and objective.enable_keyword_refinement:
                    logger.info("分析結果並生成新關鍵字...")
                    new_keywords = await self._generate_refined_keywords(
                        objective, current_keywords, all_crawled_results, confidence
                    )
                    
                    if new_keywords:
                        iteration_result.new_keywords_generated = new_keywords
                        current_keywords.extend(new_keywords)
                        # 去重
                        current_keywords = list(dict.fromkeys(current_keywords))
                        logger.info(f"新增關鍵字: {new_keywords}")
                    else:
                        logger.info("無法生成新關鍵字，結束搜索")
                        break
                else:
                    break
            
            # 最終處理
            result.total_pages_crawled = total_crawled_pages
            result.total_keywords_used = len(set(kw for iter_result in result.iterations for kw in iter_result.keywords_used))
            result.final_confidence = await self._calculate_final_confidence(all_crawled_results, objective)
            
            # 生成最終輸出
            if objective.output_format == "structured":
                result.structured_data = await self._extract_structured_data(all_crawled_results, objective)
            else:
                result.summary = await self._generate_final_summary(all_crawled_results, objective)
            
            result.status = "completed"
            result.end_time = datetime.now()
            if result.start_time:
                result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            logger.info(f"智能搜索任務完成！總計爬取 {total_crawled_pages} 頁，最終信心度: {result.final_confidence:.2%}")
            
            return result
            
        except Exception as e:
            logger.error(f"智能搜索任務失敗: {e}")
            result.status = "failed"
            result.end_time = datetime.now()
            if result.start_time:
                result.execution_time = (result.end_time - result.start_time).total_seconds()
            raise
    
    async def _perform_google_search(self, keywords: List[str], objective: TaskObjectiveV3) -> List[SearchResult]:
        """執行Google搜索"""
        all_results = []
        
        for keyword in keywords:
            try:
                results = await self.google_search.search(
                    keyword, 
                    objective.max_search_results_per_keyword
                )
                
                # 過濾已爬取的URL
                new_results = [r for r in results if r.url not in self.crawled_urls]
                all_results.extend(new_results)
                
                # 標記URL為已處理
                for result in new_results:
                    self.crawled_urls.add(result.url)
                
                logger.info(f"關鍵字 '{keyword}' 找到 {len(new_results)} 個新結果")
                
            except Exception as e:
                logger.error(f"搜索關鍵字 '{keyword}' 失敗: {e}")
                continue
        
        # 去重並按搜索排名排序
        unique_results = {}
        for result in all_results:
            if result.url not in unique_results:
                unique_results[result.url] = result
        
        final_results = list(unique_results.values())
        final_results.sort(key=lambda x: x.search_rank)
        
        logger.info(f"Google搜索完成，共獲得 {len(final_results)} 個唯一結果")
        return final_results
    
    async def _crawl_search_results(self, search_results: List[SearchResult], objective: TaskObjectiveV3) -> List[CrawlPageResult]:
        """爬蟲搜索結果"""
        crawl_results = []
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for i, search_result in enumerate(search_results):
                try:
                    logger.info(f"爬取 {i+1}/{len(search_results)}: {search_result.url}")
                    
                    config = CrawlerRunConfig(
                        word_count_threshold=50,
                        cache_mode=CacheMode.BYPASS,
                        page_timeout=30000
                    )
                    
                    crawl_response = await crawler.arun(url=search_result.url, config=config)
                    
                    # 動態處理結果
                    page_result = None
                    try:
                        if hasattr(crawl_response, 'results'):
                            page_result = getattr(crawl_response, 'results')[0]
                        elif hasattr(crawl_response, '_results'):
                            page_result = getattr(crawl_response, '_results')[0]
                        else:
                            page_result = crawl_response
                    except:
                        page_result = crawl_response
                    
                    if page_result and getattr(page_result, 'success', False):
                        # 提取內容
                        title = getattr(page_result, 'cleaned_html', '')[:200] or search_result.title
                        content = getattr(page_result, 'markdown', '') or getattr(page_result, 'cleaned_html', '')
                        
                        # LLM分析
                        analysis = await self._analyze_page_content(
                            search_result.url, title, content, search_result.snippet, objective
                        )
                        
                        crawl_result = CrawlPageResult(
                            url=search_result.url,
                            title=title,
                            content=content,
                            summary=analysis.get('summary', ''),
                            relevance_score=analysis.get('relevance_score', 0.0),
                            confidence_score=analysis.get('confidence_score', 0.0),
                            is_helpful=analysis.get('is_helpful', False),
                            crawl_time=datetime.now(),
                            source_keyword=search_result.search_query,
                            search_rank=search_result.search_rank,
                            success=True
                        )
                        
                        crawl_results.append(crawl_result)
                        logger.info(f"爬取成功，相關度: {crawl_result.relevance_score:.2f}")
                        
                    else:
                        # 爬蟲失敗
                        error_msg = getattr(page_result, 'error_message', '爬蟲失敗') if page_result else '爬蟲失敗'
                        crawl_result = CrawlPageResult(
                            url=search_result.url,
                            title=search_result.title,
                            content="",
                            summary="",
                            relevance_score=0.0,
                            confidence_score=0.0,
                            is_helpful=False,
                            crawl_time=datetime.now(),
                            source_keyword=search_result.search_query,
                            search_rank=search_result.search_rank,
                            error_message=error_msg,
                            success=False
                        )
                        crawl_results.append(crawl_result)
                        logger.warning(f"爬取失敗: {error_msg}")
                
                except Exception as e:
                    logger.error(f"爬取 {search_result.url} 異常: {e}")
                    crawl_result = CrawlPageResult(
                        url=search_result.url,
                        title=search_result.title,
                        content="",
                        summary="",
                        relevance_score=0.0,
                        confidence_score=0.0,
                        is_helpful=False,
                        crawl_time=datetime.now(),
                        source_keyword=search_result.search_query,
                        search_rank=search_result.search_rank,
                        error_message=str(e),
                        success=False
                    )
                    crawl_results.append(crawl_result)
        
        successful_crawls = [r for r in crawl_results if r.success]
        logger.info(f"爬蟲完成，成功 {len(successful_crawls)}/{len(crawl_results)} 頁")
        
        return crawl_results
    
    async def _analyze_page_content(self, url: str, title: str, content: str, snippet: str, objective: TaskObjectiveV3) -> Dict[str, Any]:
        """使用LLM分析頁面內容"""
        try:
            # 截取內容避免token過多
            content_sample = content[:3000] if content else snippet
            
            prompt = f"""分析以下網頁內容與任務目標的相關性和有用性。

任務目標: {objective.title}
任務描述: {objective.description}
目標關鍵字: {', '.join(objective.initial_keywords)}

網頁資訊:
URL: {url}
標題: {title}
內容摘要: {content_sample}

請從以下角度分析：
1. 相關度 (0-1): 內容與任務目標的相關程度
2. 信心度 (0-1): 資訊的可信度和權威性
3. 有用性: 是否對完成任務有幫助
4. 摘要: 提取關鍵資訊 (100-200字)

請返回JSON格式：
{{
    "relevance_score": 0.8,
    "confidence_score": 0.7,
    "is_helpful": true,
    "summary": "頁面內容摘要..."
}}"""

            response = await self._call_llm_api(prompt)
            if response:
                try:
                    # 嘗試解析JSON
                    analysis = json.loads(response.strip())
                    return analysis
                except json.JSONDecodeError:
                    # JSON解析失敗，使用預設值
                    logger.warning(f"LLM返回非JSON格式，使用預設分析")
                    return {
                        "relevance_score": 0.5,
                        "confidence_score": 0.5,
                        "is_helpful": True,
                        "summary": snippet[:200] if snippet else title
                    }
            
        except Exception as e:
            logger.error(f"分析頁面內容失敗 {url}: {e}")
        
        # 預設返回值
        return {
            "relevance_score": 0.3,
            "confidence_score": 0.3,
            "is_helpful": False,
            "summary": snippet[:200] if snippet else "無法分析內容"
        }
    
    async def _calculate_iteration_confidence(self, crawl_results: List[CrawlPageResult], objective: TaskObjectiveV3) -> float:
        """計算迭代信心度"""
        if not crawl_results:
            return 0.0
        
        successful_results = [r for r in crawl_results if r.success]
        if not successful_results:
            return 0.0
        
        # 計算平均相關度和信心度
        avg_relevance = sum(r.relevance_score for r in successful_results) / len(successful_results)
        avg_confidence = sum(r.confidence_score for r in successful_results) / len(successful_results)
        helpful_ratio = sum(1 for r in successful_results if r.is_helpful) / len(successful_results)
        
        # 綜合計算
        iteration_confidence = (avg_relevance * 0.4 + avg_confidence * 0.3 + helpful_ratio * 0.3)
        
        return min(iteration_confidence, 1.0)
    
    async def _calculate_final_confidence(self, all_results: List[CrawlPageResult], objective: TaskObjectiveV3) -> float:
        """計算最終信心度"""
        if not all_results:
            return 0.0
        
        successful_results = [r for r in all_results if r.success]
        if not successful_results:
            return 0.0
        
        # 按相關度排序，取前70%計算
        sorted_results = sorted(successful_results, key=lambda x: x.relevance_score, reverse=True)
        top_results = sorted_results[:max(1, int(len(sorted_results) * 0.7))]
        
        avg_relevance = sum(r.relevance_score for r in top_results) / len(top_results)
        avg_confidence = sum(r.confidence_score for r in top_results) / len(top_results)
        helpful_ratio = sum(1 for r in top_results if r.is_helpful) / len(top_results)
        
        # 考慮數據量完整性
        data_completeness = min(len(successful_results) / 20, 1.0)  # 20頁為滿分
        
        final_confidence = (
            avg_relevance * 0.35 + 
            avg_confidence * 0.25 + 
            helpful_ratio * 0.25 + 
            data_completeness * 0.15
        )
        
        return min(final_confidence, 1.0)
    
    async def _generate_refined_keywords(self, 
                                       objective: TaskObjectiveV3, 
                                       used_keywords: List[str], 
                                       crawl_results: List[CrawlPageResult],
                                       current_confidence: float) -> List[str]:
        """生成優化的關鍵字"""
        try:
            # 將crawl_results轉換為字典格式供keyword_generator使用
            results_data = []
            for result in crawl_results:
                results_data.append({
                    'title': result.title,
                    'summary': result.summary,
                    'is_helpful': result.is_helpful,
                    'relevance_score': result.relevance_score,
                    'url': result.url
                })
            
            new_keywords = await self.keyword_generator.refine_keywords_based_on_results(
                objective.title,
                objective.description,
                used_keywords,
                results_data,
                current_confidence
            )
            
            return new_keywords
            
        except Exception as e:
            logger.error(f"生成優化關鍵字失敗: {e}")
            return []
    
    async def _extract_structured_data(self, crawl_results: List[CrawlPageResult], objective: TaskObjectiveV3) -> List[Dict]:
        """抽取結構化資料"""
        structured_data = []
        
        successful_results = [r for r in crawl_results if r.success and r.is_helpful]
        
        for result in successful_results:
            try:
                # 使用LLM抽取結構化資料
                extracted = await self._llm_extract_structured_data(result, objective)
                if extracted:
                    item = {
                        "source_url": result.url,
                        "title": result.title,
                        "summary": result.summary,
                        "relevance_score": result.relevance_score,
                        "confidence_score": result.confidence_score,
                        "source_keyword": result.source_keyword,
                        "crawl_time": result.crawl_time.isoformat(),
                        "extracted_data": extracted
                    }
                    structured_data.append(item)
                    
            except Exception as e:
                logger.error(f"抽取結構化資料失敗 {result.url}: {e}")
                continue
        
        logger.info(f"成功抽取了 {len(structured_data)} 條結構化資料")
        return structured_data
    
    async def _llm_extract_structured_data(self, result: CrawlPageResult, objective: TaskObjectiveV3) -> Optional[Dict]:
        """使用LLM抽取結構化資料"""
        try:
            content_sample = result.content[:2000] if result.content else result.summary
            
            prompt = f"""從以下內容中抽取與 "{objective.title}" 相關的結構化資訊。

任務描述: {objective.description}

內容:
標題: {result.title}
摘要: {result.summary}
詳細內容: {content_sample}

請抽取關鍵資料並以JSON格式返回，包含但不限於：
- 關鍵事實
- 數據和統計
- 時間資訊
- 相關人物或組織
- 重要發現或結論

JSON格式示例：
{{
    "key_facts": ["事實1", "事實2"],
    "data_points": {{"指標": "數值"}},
    "timeline": {{"時間": "事件"}},
    "entities": {{"類型": ["實體1", "實體2"]}},
    "conclusions": ["結論1", "結論2"]
}}"""

            response = await self._call_llm_api(prompt)
            if response:
                try:
                    return json.loads(response.strip())
                except json.JSONDecodeError:
                    logger.warning(f"LLM返回非JSON格式，跳過結構化抽取")
                    return None
            
        except Exception as e:
            logger.error(f"LLM結構化抽取失敗: {e}")
        
        return None
    
    async def _generate_final_summary(self, crawl_results: List[CrawlPageResult], objective: TaskObjectiveV3) -> str:
        """生成最終摘要"""
        try:
            successful_results = [r for r in crawl_results if r.success and r.is_helpful]
            
            if not successful_results:
                return "未找到相關有用資訊"
            
            # 選取最相關的結果
            top_results = sorted(successful_results, key=lambda x: x.relevance_score, reverse=True)[:10]
            
            summaries = [f"• {r.title}: {r.summary}" for r in top_results if r.summary]
            combined_summaries = "\n".join(summaries)
            
            prompt = f"""基於以下爬蟲結果，為任務 "{objective.title}" 生成一份全面的摘要報告。

任務描述: {objective.description}

關鍵發現:
{combined_summaries}

請生成一份結構化的摘要報告，包含：
1. 執行摘要
2. 主要發現
3. 關鍵數據
4. 結論和建議

長度約500-800字。"""

            response = await self._call_llm_api(prompt)
            return response or "無法生成摘要"
            
        except Exception as e:
            logger.error(f"生成最終摘要失敗: {e}")
            return "摘要生成失敗"
    
    async def _call_llm_api(self, prompt: str) -> Optional[str]:
        """調用LLM API"""
        try:
            import httpx
            
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.3
                }
                
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.llm_config.api_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"LLM API調用失敗: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"LLM API調用異常: {e}")
        
        return None

# 便利函數
async def quick_smart_crawl(
    title: str,
    description: str,
    initial_keywords: Optional[List[str]] = None,
    llm_config: Optional[LLMConfig] = None,
    max_iterations: int = 3,
    target_confidence: float = 0.85,
    output_format: str = "structured"
) -> SmartCrawlResult:
    """快速執行智能搜索爬蟲"""
    
    if llm_config is None:
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1",
            api_token="sk-test-token"
        )
    
    objective = TaskObjectiveV3(
        title=title,
        description=description,
        initial_keywords=initial_keywords or [],
        max_iterations=max_iterations,
        target_confidence=target_confidence,
        output_format=output_format
    )
    
    crawler = SmartSearchCrawler(llm_config)
    return await crawler.execute_smart_crawl(objective)
