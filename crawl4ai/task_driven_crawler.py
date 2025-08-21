import asyncio
import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urlparse
import re

from .async_webcrawler import AsyncWebCrawler
from .async_configs import CrawlerRunConfig, LLMConfig
from .extraction_strategy import LLMExtractionStrategy
from .adaptive_crawler import AdaptiveCrawler, AdaptiveConfig, EmbeddingStrategy
from .models import CrawlResult
from .utils import perform_completion_with_backoff

@dataclass
class TaskObjective:
    """任務目標定義"""
    title: str  # 任務標題
    description: str  # 詳細描述
    keywords: List[str] = field(default_factory=list)  # 關鍵字
    target_domains: List[str] = field(default_factory=list)  # 指定域名
    exclude_domains: List[str] = field(default_factory=list)  # 排除域名
    output_format: str = "structured"  # "structured" 或 "summary"
    schema: Optional[Dict] = None  # 結構化輸出 schema
    max_results: int = 50  # 最大結果數
    
    def to_search_query(self) -> str:
        """轉換為搜尋查詢"""
        query_parts = [self.title, self.description]
        if self.keywords:
            query_parts.extend(self.keywords)
        return " ".join(query_parts)

@dataclass 
class DiscoveryConfig:
    """站點發現配置"""
    search_engines: List[str] = field(default_factory=lambda: ["google", "bing"])
    max_sites_per_engine: int = 10
    enable_domain_filter: bool = True
    enable_content_type_filter: bool = True
    search_api_key: Optional[str] = None
    search_engine_id: Optional[str] = None
    
@dataclass
class ExtractionConfig:
    """抽取配置"""
    llm_config: LLMConfig
    extraction_mode: str = "adaptive"  # "adaptive", "schema", "summary"
    chunk_size: int = 4000
    overlap_size: int = 200
    temperature: float = 0.1
    
@dataclass
class TaskDrivenConfig:
    """任務驅動爬蟲總配置"""
    objective: TaskObjective
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    adaptive: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    extraction: Optional[ExtractionConfig] = None
    additional_urls: List[str] = field(default_factory=list)  # 手動追加 URL
    output_dir: str = "./crawl_results"
    save_intermediate: bool = True

@dataclass
class CrawlSession:
    """爬取會話狀態"""
    session_id: str
    objective: TaskObjective
    discovered_urls: List[str] = field(default_factory=list)
    seed_urls: List[str] = field(default_factory=list)
    crawled_results: List[CrawlResult] = field(default_factory=list)
    extracted_data: List[Dict] = field(default_factory=list)
    summary: str = ""
    confidence_score: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "initialized"
    error_log: List[str] = field(default_factory=list)
    
    def save(self, filepath: Union[str, Path]):
        """保存會話狀態"""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 轉換為可序列化的格式
        data = asdict(self)
        data['start_time'] = self.start_time.isoformat()
        data['end_time'] = self.end_time.isoformat() if self.end_time else None
        
        # 處理 CrawlResult 對象
        data['crawled_results'] = [self._crawl_result_to_dict(r) for r in self.crawled_results]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _crawl_result_to_dict(self, result: CrawlResult) -> Dict:
        """轉換 CrawlResult 為字典"""
        return {
            'url': result.url,
            'success': result.success,
            'content': result.markdown.raw_markdown if hasattr(result, 'markdown') and result.markdown else "",
            'metadata': result.metadata if hasattr(result, 'metadata') else {},
            'timestamp': datetime.now().isoformat()
        }

class SiteDiscoveryEngine:
    """站點發現引擎 - 自動找到相關網站"""
    
    def __init__(self, config: DiscoveryConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        self.logger = logging.getLogger(__name__)
        
    async def discover_sites(self, objective: TaskObjective) -> List[str]:
        """根據任務目標發現相關網站"""
        self.logger.info(f"開始站點發現: {objective.title}")
        
        # 第一步：LLM 生成搜尋策略
        search_strategy = await self._generate_search_strategy(objective)
        
        # 第二步：執行多引擎搜尋
        candidate_urls = await self._execute_search(search_strategy)
        
        # 第三步：過濾和去重
        filtered_urls = await self._filter_urls(candidate_urls, objective)
        
        self.logger.info(f"發現 {len(filtered_urls)} 個候選網站")
        return filtered_urls
    
    async def _generate_search_strategy(self, objective: TaskObjective) -> Dict[str, List[str]]:
        """使用 LLM 生成針對性的搜尋策略"""
        prompt = f"""
        基於以下任務目標，生成多個搜尋查詢來找到最相關的網站：

        任務標題: {objective.title}
        任務描述: {objective.description}
        關鍵字: {', '.join(objective.keywords)}
        目標域名: {', '.join(objective.target_domains) if objective.target_domains else '不限'}

        請生成 5-8 個不同的搜尋查詢，每個查詢應該從不同角度探索這個主題。
        包括：
        1. 直接關鍵字搜尋
        2. 專業術語搜尋  
        3. 新聞和報告搜尋
        4. 分析和預測搜尋
        5. 官方和權威來源搜尋

        返回 JSON 格式：
        {{
            "primary_queries": ["查詢1", "查詢2", ...],
            "news_queries": ["新聞查詢1", "新聞查詢2", ...],
            "analysis_queries": ["分析查詢1", "分析查詢2", ...],
            "official_queries": ["官方查詢1", "官方查詢2", ...]
        }}
        """
        
        try:
            response = await perform_completion_with_backoff(
                provider=self.llm_config.provider,
                prompt_with_variables=prompt,
                api_token=self.llm_config.api_token,
                base_url=self.llm_config.base_url,
                json_response=True,
                temperature=0.2
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            self.logger.error(f"生成搜尋策略失敗: {e}")
            # 回退到基本策略
            return {
                "primary_queries": [objective.to_search_query()],
                "news_queries": [f"{objective.title} news"],
                "analysis_queries": [f"{objective.title} analysis report"],
                "official_queries": [f"official {objective.title}"]
            }
    
    async def _execute_search(self, strategy: Dict[str, List[str]]) -> List[str]:
        """執行搜尋並收集候選 URL"""
        all_urls = []
        
        for category, queries in strategy.items():
            for query in queries:
                # 這裡模擬搜尋結果 - 實際應該調用搜尋 API
                urls = await self._search_with_engine(query)
                all_urls.extend(urls)
                
                # 避免過度搜尋
                await asyncio.sleep(0.5)
        
        return list(set(all_urls))  # 去重
    
    async def _search_with_engine(self, query: str) -> List[str]:
        """使用搜尋引擎 API 搜尋（模擬實作）"""
        # 實際實作應該調用 Google/Bing API
        # 這裡返回模擬結果
        
        self.logger.debug(f"搜尋查詢: {query}")
        
        # 模擬一些財經相關網站的結果
        mock_results = [
            "https://finance.yahoo.com/quote/NVDA",
            "https://www.bloomberg.com/quote/NVDA:US", 
            "https://seekingalpha.com/symbol/NVDA",
            "https://www.marketwatch.com/investing/stock/nvda",
            "https://www.fool.com/investing/stock-market/market-sectors/technology/semiconductor-stocks/nvidia-stock/",
            "https://www.cnbc.com/quotes/NVDA",
            "https://www.reuters.com/markets/companies/NVDA.O",
            "https://www.morningstar.com/stocks/xnas/nvda/quote",
            "https://investor.nvidia.com/",
            "https://www.zacks.com/stock/quote/NVDA"
        ]
        
        # 返回前幾個結果
        return mock_results[:self.config.max_sites_per_engine]
    
    async def _filter_urls(self, urls: List[str], objective: TaskObjective) -> List[str]:
        """過濾和評分 URL"""
        filtered_urls = []
        
        for url in urls:
            # 基本過濾
            if not self._is_valid_url(url):
                continue
                
            # 域名過濾
            if not self._check_domain_filter(url, objective):
                continue
                
            # 內容類型過濾（檢查是否為 HTML 頁面）
            if self.config.enable_content_type_filter and not self._is_html_url(url):
                continue
                
            filtered_urls.append(url)
        
        # 去重並排序
        filtered_urls = list(set(filtered_urls))
        
        # 根據 URL 結構進行簡單評分排序
        scored_urls = [(url, self._score_url(url, objective)) for url in filtered_urls]
        scored_urls.sort(key=lambda x: x[1], reverse=True)
        
        return [url for url, score in scored_urls]
    
    def _is_valid_url(self, url: str) -> bool:
        """檢查 URL 是否有效"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except:
            return False
    
    def _check_domain_filter(self, url: str, objective: TaskObjective) -> bool:
        """檢查域名過濾條件"""
        if not self.config.enable_domain_filter:
            return True
            
        domain = urlparse(url).netloc.lower()
        
        # 檢查排除域名
        for exclude_domain in objective.exclude_domains:
            if exclude_domain.lower() in domain:
                return False
        
        # 檢查目標域名（如果指定）
        if objective.target_domains:
            for target_domain in objective.target_domains:
                if target_domain.lower() in domain:
                    return True
            return False
        
        return True
    
    def _is_html_url(self, url: str) -> bool:
        """簡單檢查是否為 HTML 頁面"""
        # 排除明顯的非 HTML 檔案
        excluded_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                              '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3', '.zip']
        
        url_lower = url.lower()
        return not any(url_lower.endswith(ext) for ext in excluded_extensions)
    
    def _score_url(self, url: str, objective: TaskObjective) -> float:
        """根據 URL 特徵評分"""
        score = 0.5  # 基礎分數
        
        url_lower = url.lower()
        path = urlparse(url).path.lower()
        
        # 關鍵字匹配
        for keyword in objective.keywords:
            if keyword.lower() in url_lower:
                score += 0.2
        
        # 路徑特徵加分
        valuable_paths = ['/news/', '/analysis/', '/report/', '/research/', '/quote/', '/stock/']
        for path_pattern in valuable_paths:
            if path_pattern in path:
                score += 0.1
        
        # 權威域名加分
        authority_domains = ['bloomberg.com', 'reuters.com', 'wsj.com', 'ft.com', 
                           'cnbc.com', 'marketwatch.com', 'finance.yahoo.com']
        domain = urlparse(url).netloc.lower()
        for auth_domain in authority_domains:
            if auth_domain in domain:
                score += 0.3
                break
        
        return min(score, 1.0)

class TaskDrivenCrawler:
    """任務驅動爬蟲主類"""
    
    def __init__(self, config: TaskDrivenConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.session: Optional[CrawlSession] = None
        
        # 檢查必要的配置
        if not config.extraction:
            raise ValueError("必須提供 extraction 配置")
        
        # 初始化組件
        self.discovery_engine = SiteDiscoveryEngine(
            config.discovery, 
            config.extraction.llm_config
        )
        
        # 建立輸出目錄
        Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    
    async def execute_task(self) -> CrawlSession:
        """執行完整的任務驅動爬取流程"""
        session_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session = CrawlSession(
            session_id=session_id,
            objective=self.config.objective
        )
        
        try:
            self.session.status = "discovering"
            self.logger.info(f"開始執行任務: {self.config.objective.title}")
            
            # 第一階段：站點發現
            await self._discovery_phase()
            
            # 第二階段：智慧爬取
            self.session.status = "crawling"
            await self._crawling_phase()
            
            # 第三階段：語意抽取
            self.session.status = "extracting" 
            await self._extraction_phase()
            
            # 第四階段：結果整合
            self.session.status = "finalizing"
            await self._finalization_phase()
            
            self.session.status = "completed"
            self.session.end_time = datetime.now()
            
            # 保存最終結果
            await self._save_results()
            
            self.logger.info(f"任務完成，信心度: {self.session.confidence_score:.2%}")
            return self.session
            
        except Exception as e:
            if self.session:
                self.session.status = "failed"
                self.session.error_log.append(str(e))
            self.logger.error(f"任務執行失敗: {e}")
            raise
    
    def _ensure_session(self) -> CrawlSession:
        """確保 session 存在"""
        if not self.session:
            raise RuntimeError("Session 未初始化")
        return self.session
    
    def _ensure_extraction_config(self) -> ExtractionConfig:
        """確保 extraction config 存在"""
        if not self.config.extraction:
            raise RuntimeError("Extraction 配置未設定")
        return self.config.extraction
    
    async def _discovery_phase(self):
        """階段一：站點發現"""
        session = self._ensure_session()
            
        self.logger.info("=== 階段一：站點發現 ===")
        
        # 自動發現網站
        discovered_urls = await self.discovery_engine.discover_sites(self.config.objective)
        session.discovered_urls = discovered_urls
        
        # 合併手動追加的 URL
        additional_urls = [url for url in self.config.additional_urls 
                          if self._is_valid_additional_url(url)]
        
        # 合併並去重
        all_urls = list(set(discovered_urls + additional_urls))
        session.seed_urls = all_urls
        
        self.logger.info(f"發現網站: {len(discovered_urls)} 個")
        self.logger.info(f"手動追加: {len(additional_urls)} 個") 
        self.logger.info(f"總種子 URL: {len(all_urls)} 個")
        
        # 保存中間結果
        if self.config.save_intermediate:
            await self._save_intermediate_results("discovery")
        """階段一：站點發現"""
        if not self.session:
            raise RuntimeError("Session 未初始化")
            
        self.logger.info("=== 階段一：站點發現 ===")
        
        # 自動發現網站
        discovered_urls = await self.discovery_engine.discover_sites(self.config.objective)
        self.session.discovered_urls = discovered_urls
        
        # 合併手動追加的 URL
        additional_urls = [url for url in self.config.additional_urls 
                          if self._is_valid_additional_url(url)]
        
        # 合併並去重
        all_urls = list(set(discovered_urls + additional_urls))
        self.session.seed_urls = all_urls
        
        self.logger.info(f"發現網站: {len(discovered_urls)} 個")
        self.logger.info(f"手動追加: {len(additional_urls)} 個") 
        self.logger.info(f"總種子 URL: {len(all_urls)} 個")
        
        # 保存中間結果
        if self.config.save_intermediate:
            await self._save_intermediate_results("discovery")
    
    async def _crawling_phase(self):
        """階段二：智慧爬取"""
        self.logger.info("=== 階段二：智慧爬取 ===")
        
        if not self.session.seed_urls:
            raise ValueError("沒有可用的種子 URL")
        
        # 配置自適應爬蟲
        adaptive_config = self.config.adaptive
        adaptive_config.strategy = "embedding"  # 使用語意策略
        adaptive_config.embedding_llm_config = {
            'provider': self.config.extraction.llm_config.provider,
            'api_token': self.config.extraction.llm_config.api_token,
            'base_url': self.config.extraction.llm_config.base_url
        }
        
        # 為每個種子 URL 執行自適應爬取
        all_results = []
        
        async with AsyncWebCrawler() as crawler:
            for i, seed_url in enumerate(self.session.seed_urls):
                self.logger.info(f"爬取種子 URL {i+1}/{len(self.session.seed_urls)}: {seed_url}")
                
                try:
                    # 建立自適應爬蟲實例
                    adaptive_crawler = AdaptiveCrawler(
                        crawler=crawler,
                        config=adaptive_config,
                        strategy=EmbeddingStrategy(
                            embedding_model=adaptive_config.embedding_model,
                            llm_config=adaptive_config.embedding_llm_config
                        )
                    )
                    
                    # 執行自適應爬取
                    crawl_state = await adaptive_crawler.digest(
                        start_url=seed_url,
                        query=self.config.objective.to_search_query()
                    )
                    
                    # 收集結果
                    all_results.extend(crawl_state.knowledge_base)
                    self.session.confidence_score = max(
                        self.session.confidence_score, 
                        crawl_state.metrics.get('confidence', 0)
                    )
                    
                    self.logger.info(f"從 {seed_url} 爬取了 {len(crawl_state.knowledge_base)} 個頁面")
                    
                except Exception as e:
                    self.session.error_log.append(f"爬取 {seed_url} 失敗: {str(e)}")
                    self.logger.error(f"爬取 {seed_url} 失敗: {e}")
                    continue
        
        self.session.crawled_results = all_results
        self.logger.info(f"總共爬取了 {len(all_results)} 個頁面")
        
        # 保存中間結果
        if self.config.save_intermediate:
            await self._save_intermediate_results("crawling")
    
    async def _extraction_phase(self):
        """階段三：語意抽取"""
        self.logger.info("=== 階段三：語意抽取 ===")
        
        if not self.session.crawled_results:
            self.logger.warning("沒有爬取結果可供抽取")
            return
        
        # 根據輸出格式選擇抽取策略
        if self.config.objective.output_format == "structured":
            await self._extract_structured_data()
        else:
            await self._extract_summary()
        
        # 保存中間結果
        if self.config.save_intermediate:
            await self._save_intermediate_results("extraction")
    
    async def _extract_structured_data(self):
        """抽取結構化資料"""
        if not self.config.objective.schema:
            # 自動生成 schema
            schema = await self._generate_schema()
        else:
            schema = self.config.objective.schema
        
        extracted_items = []
        
        # 建立 LLM 抽取策略
        extraction_strategy = LLMExtractionStrategy(
            llm_config=self.config.extraction.llm_config,
            schema=schema,
            extraction_type="schema",
            instruction=f"從內容中抽取與 '{self.config.objective.title}' 相關的資訊"
        )
        
        # 對每個爬取結果進行抽取
        for result in self.session.crawled_results:
            if not result.success:
                continue
                
            try:
                content = result.markdown.raw_markdown if hasattr(result, 'markdown') and result.markdown else ""
                if not content:
                    continue
                
                # 執行 LLM 抽取
                extracted = await extraction_strategy.aextract(content)
                
                if extracted:
                    # 添加源 URL 資訊
                    item = {
                        "source_url": result.url,
                        "extracted_at": datetime.now().isoformat(),
                        "data": extracted
                    }
                    extracted_items.append(item)
                    
            except Exception as e:
                self.session.error_log.append(f"抽取 {result.url} 失敗: {str(e)}")
                self.logger.error(f"抽取 {result.url} 失敗: {e}")
                continue
        
        self.session.extracted_data = extracted_items
        self.logger.info(f"成功抽取了 {len(extracted_items)} 條結構化資料")
    
    async def _extract_summary(self):
        """生成摘要"""
        # 合併所有內容
        all_content = []
        for result in self.session.crawled_results:
            if result.success and hasattr(result, 'markdown') and result.markdown:
                content = result.markdown.raw_markdown or ""
                if content:
                    all_content.append(f"來源: {result.url}\n{content}")
        
        if not all_content:
            self.session.summary = "無可用內容生成摘要"
            return
        
        # 分塊處理長內容
        combined_content = "\n\n".join(all_content)
        
        # 使用 LLM 生成摘要
        prompt = f"""
        基於以下爬取的內容，生成關於 "{self.config.objective.title}" 的詳細摘要和重點分析：

        任務描述: {self.config.objective.description}

        內容:
        {combined_content[:20000]}  # 限制長度避免超過 token 限制

        請提供：
        1. 執行摘要（2-3 段）
        2. 關鍵發現和數據點
        3. 重要觀點和預測
        4. 結論和建議

        請以清晰、有條理的方式組織回應。
        """
        
        try:
            response = await perform_completion_with_backoff(
                provider=self.config.extraction.llm_config.provider,
                prompt_with_variables=prompt,
                api_token=self.config.extraction.llm_config.api_token,
                base_url=self.config.extraction.llm_config.base_url,
                temperature=self.config.extraction.temperature
            )
            
            self.session.summary = response.choices[0].message.content
            
        except Exception as e:
            self.session.error_log.append(f"生成摘要失敗: {str(e)}")
            self.session.summary = f"摘要生成失敗: {e}"
            self.logger.error(f"生成摘要失敗: {e}")
    
    async def _generate_schema(self) -> Dict:
        """自動生成結構化抽取 schema"""
        prompt = f"""
        基於以下任務目標，設計一個 JSON schema 來抽取相關的結構化資訊：

        任務標題: {self.config.objective.title}
        任務描述: {self.config.objective.description}
        關鍵字: {', '.join(self.config.objective.keywords)}

        請設計一個包含以下要素的 schema：
        1. 關鍵數據和指標
        2. 日期和時間資訊
        3. 來源和作者資訊
        4. 重要觀點和預測

        返回有效的 JSON schema 格式，包含 type, properties 等標準欄位。
        """
        
        try:
            response = await perform_completion_with_backoff(
                provider=self.config.extraction.llm_config.provider,
                prompt_with_variables=prompt,
                api_token=self.config.extraction.llm_config.api_token,
                base_url=self.config.extraction.llm_config.base_url,
                json_response=True,
                temperature=0.1
            )
            
            content = response.choices[0].message.content
            return json.loads(content)
            
        except Exception as e:
            self.logger.error(f"生成 schema 失敗: {e}")
            # 回退到基本 schema
            return {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "標題或主題"},
                    "content": {"type": "string", "description": "主要內容"},
                    "date": {"type": "string", "description": "日期"},
                    "source": {"type": "string", "description": "來源"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "關鍵要點"
                    }
                }
            }
    
    async def _finalization_phase(self):
        """階段四：結果整合和後處理"""
        self.logger.info("=== 階段四：結果整合 ===")
        
        # 計算最終信心度
        if self.session.extracted_data:
            self.session.confidence_score = min(
                self.session.confidence_score + 0.1,  # 成功抽取資料給予加分
                1.0
            )
        
        # 生成執行報告
        execution_report = {
            "task_title": self.config.objective.title,
            "execution_time": (self.session.end_time or datetime.now() - self.session.start_time).total_seconds(),
            "sites_discovered": len(self.session.discovered_urls),
            "pages_crawled": len(self.session.crawled_results),
            "data_extracted": len(self.session.extracted_data),
            "confidence_score": self.session.confidence_score,
            "has_summary": bool(self.session.summary),
            "error_count": len(self.session.error_log)
        }
        
        self.session.metadata = execution_report
        self.logger.info(f"任務執行報告: {execution_report}")
    
    def _is_valid_additional_url(self, url: str) -> bool:
        """驗證手動追加的 URL"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except:
            return False
    
    async def _save_intermediate_results(self, phase: str):
        """保存中間結果"""
        filename = f"{self.session.session_id}_{phase}.json"
        filepath = Path(self.config.output_dir) / filename
        self.session.save(filepath)
        self.logger.debug(f"保存中間結果: {filepath}")
    
    async def _save_results(self):
        """保存最終結果"""
        # 保存完整會話
        session_file = Path(self.config.output_dir) / f"{self.session.session_id}_final.json"
        self.session.save(session_file)
        
        # 保存結構化資料（如果有）
        if self.session.extracted_data:
            data_file = Path(self.config.output_dir) / f"{self.session.session_id}_data.jsonl"
            with open(data_file, 'w', encoding='utf-8') as f:
                for item in self.session.extracted_data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 保存摘要（如果有）
        if self.session.summary:
            summary_file = Path(self.config.output_dir) / f"{self.session.session_id}_summary.md"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"# {self.config.objective.title}\n\n")
                f.write(f"**任務描述:** {self.config.objective.description}\n\n")
                f.write(f"**執行時間:** {self.session.start_time}\n\n")
                f.write(f"**信心度:** {self.session.confidence_score:.2%}\n\n")
                f.write("## 摘要\n\n")
                f.write(self.session.summary)
        
        self.logger.info(f"結果已保存到: {self.config.output_dir}")

# 便利函數
async def create_task_crawler(
    title: str,
    description: str,
    llm_config: LLMConfig,
    keywords: List[str] = None,
    output_format: str = "structured",
    additional_urls: List[str] = None,
    max_pages: int = 20
) -> TaskDrivenCrawler:
    """快速建立任務驅動爬蟲"""
    
    objective = TaskObjective(
        title=title,
        description=description,
        keywords=keywords or [],
        output_format=output_format
    )
    
    adaptive_config = AdaptiveConfig(
        max_pages=max_pages,
        confidence_threshold=0.7,
        strategy="embedding"
    )
    
    extraction_config = ExtractionConfig(
        llm_config=llm_config,
        extraction_mode="adaptive"
    )
    
    config = TaskDrivenConfig(
        objective=objective,
        adaptive=adaptive_config,
        extraction=extraction_config,
        additional_urls=additional_urls or []
    )
    
    return TaskDrivenCrawler(config)

# 範例使用方式
async def example_nvidia_stock_analysis():
    """範例：NVDA 股價預測分析"""
    
    # 配置本地 LLM
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx",
        model="gpt-oss-20b-mlx-4bit"
    )
    
    # 建立任務驅動爬蟲
    crawler = await create_task_crawler(
        title="NVDA 股價預測分析 2025",
        description="收集和分析關於 NVIDIA (NVDA) 股價的專家預測、財務分析和市場觀點",
        llm_config=llm_config,
        keywords=["NVDA", "NVIDIA", "股價預測", "財務分析", "AI 晶片", "GPU"],
        output_format="structured",
        additional_urls=[
            "https://investor.nvidia.com/",
            "https://finance.yahoo.com/quote/NVDA"
        ],
        max_pages=30
    )
    
    # 執行任務
    session = await crawler.execute_task()
    
    print(f"任務完成！信心度: {session.confidence_score:.2%}")
    print(f"爬取頁面: {len(session.crawled_results)}")
    print(f"抽取資料: {len(session.extracted_data)}")
    
    return session

if __name__ == "__main__":
    # 運行範例
    asyncio.run(example_nvidia_stock_analysis())
