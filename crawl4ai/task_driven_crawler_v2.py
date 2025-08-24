import asyncio
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from urllib.parse import urlparse, urljoin
import re
import httpx
import hashlib
from email.utils import parsedate_to_datetime

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, CacheMode
from .extraction_strategy import LLMExtractionStrategy
from .adaptive_crawler import AdaptiveCrawler, AdaptiveConfig, EmbeddingStrategy
from .models import CrawlResult
from .utils import perform_completion_with_backoff

# 配置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class TaskObjective:
    """任務目標定義"""
    title: str
    description: str
    keywords: List[str] = field(default_factory=list)
    target_domains: List[str] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=list)
    output_format: str = "structured"  # "structured" 或 "summary"
    schema: Optional[Dict] = None
    max_results: int = 50
    time_priority: bool = True  # 新增：是否啟用時間優先度
    max_search_depth: int = 5  # 增強：提高預設搜索深度到5層
    max_search_breadth: int = 10  # 新增：每層最大頁面數
    enable_content_summary: bool = True  # 新增：是否生成內容摘要
    enable_dynamic_search: bool = True  # 新增：是否啟用動態搜索
    search_strictness: str = "strict"  # 新增：搜索嚴格度 ("strict", "moderate", "relaxed")
    
    def to_search_query(self) -> str:
        """轉換為搜尋查詢"""
        query_parts = [self.title, self.description]
        if self.keywords:
            query_parts.extend(self.keywords)
        return " ".join(query_parts)

@dataclass
class PageInfo:
    """頁面資訊"""
    url: str
    title: str = ""
    content: str = ""
    summary: str = ""  # 新增：內容摘要
    publish_date: Optional[datetime] = None  # 新增：發布時間
    time_score: float = 0.0  # 新增：時間權重分數
    relevance_score: float = 0.0
    depth: int = 0  # 新增：搜索深度
    parent_url: str = ""  # 新增：父頁面URL
    found_via: str = ""  # 新增：發現方式（search/link/subpage）
    is_helpful: bool = False  # 新增：對爬蟲目標是否有幫助
    helpfulness_score: float = 0.0  # 新增：幫助度分數 (0-1)
    helpfulness_reason: str = ""  # 新增：幫助度評估原因
    extracted_at: datetime = field(default_factory=datetime.now)

@dataclass 
class DiscoveryConfig:
    """站點發現配置"""
    search_engines: List[str] = field(default_factory=lambda: ["google", "bing"])
    max_sites_per_engine: int = 10
    enable_domain_filter: bool = True
    enable_content_type_filter: bool = True
    search_api_key: Optional[str] = None
    search_engine_id: Optional[str] = None
    enable_subpage_search: bool = True  # 新增：是否啟用子頁面搜索
    enable_site_search: bool = True  # 新增：是否啟用站內搜索
    time_decay_hours: int = 168  # 新增：時間衰減週期（小時），預設一週

@dataclass
class TaskResult:
    """任務執行結果"""
    task_id: str
    objective: TaskObjective
    discovered_urls: List[str] = field(default_factory=list)
    crawled_pages: int = 0
    extracted_data: List[Dict] = field(default_factory=list)
    page_summaries: List[Dict] = field(default_factory=list)  # 新增：頁面摘要列表
    summary: str = ""
    confidence_score: float = 0.0
    execution_time: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str = "initialized"
    error_messages: List[str] = field(default_factory=list)
    search_stats: Dict[str, Any] = field(default_factory=dict)  # 新增：搜索統計信息
    helpfulness_stats: Dict[str, Any] = field(default_factory=dict)  # 新增：幫助度統計
    search_stats: Dict[str, Any] = field(default_factory=dict)  # 新增：搜索統計信息

class SmartSearchEngine:
    """智慧搜索引擎 - 處理子頁面和站內搜索"""
    
    def __init__(self, llm_config: LLMConfig, discovery_config: DiscoveryConfig):
        self.llm_config = llm_config
        self.config = discovery_config
        self.visited_urls = set()
        self.search_cache = {}  # URL -> 搜索結果快取
        
    async def smart_crawl_site(
        self, 
        base_url: str, 
        objective: TaskObjective, 
        crawler: AsyncWebCrawler
    ) -> List[PageInfo]:
        """智慧爬取網站，包含子頁面搜索和站內搜索，支援動態深度調整"""
        logger.info(f"開始智慧爬取: {base_url}")
        
        pages = []
        queue = [(base_url, 0, "")]  # (url, depth, parent_url)
        consecutive_unhelpful_count = 0  # 連續無幫助頁面計數
        max_dynamic_depth = objective.max_search_depth  # 動態最大深度
        
        while queue and len(pages) < objective.max_results:
            current_url, depth, parent_url = queue.pop(0)
            
            # 檢查動態深度限制
            if depth > max_dynamic_depth:
                continue
                
            # 檢查是否已訪問
            if current_url in self.visited_urls:
                continue
                
            self.visited_urls.add(current_url)
            
            try:
                # 爬取當前頁面
                page_info = await self._crawl_single_page(
                    current_url, objective, crawler, depth, parent_url
                )
                
                if page_info:
                    # 先評估頁面幫助度
                    await self._evaluate_page_helpfulness(page_info, objective)
                    
                    # 根據幫助度重新生成摘要（如果需要更詳細的摘要）
                    if page_info.is_helpful and objective.enable_content_summary:
                        page_info.summary = await self._generate_content_summary(
                            page_info.content, objective, page_info
                        )
                    
                    pages.append(page_info)
                    
                    # 動態深度調整邏輯
                    if page_info.is_helpful:
                        # 發現有幫助的頁面，重置計數並增加深度
                        consecutive_unhelpful_count = 0
                        if max_dynamic_depth < objective.max_search_depth + 2:
                            max_dynamic_depth += 2  # 動態增加2層深度
                            logger.info(f"發現有幫助頁面，動態增加搜索深度至 {max_dynamic_depth}")
                    else:
                        # 無幫助頁面，增加計數
                        consecutive_unhelpful_count += 1
                        
                        # 如果在深度2連續2個無幫助頁面，停止深入搜索
                        if depth >= 2 and consecutive_unhelpful_count >= 2:
                            logger.info(f"深度 {depth} 連續 {consecutive_unhelpful_count} 個無幫助頁面，停止深入搜索")
                            continue
                    
                    # 如果當前頁面相關度高或有幫助，搜索子頁面
                    if (page_info.relevance_score > 0.5 or page_info.is_helpful) and depth < max_dynamic_depth:
                        subpages = await self._find_relevant_subpages(
                            current_url, objective, crawler, depth + 1
                        )
                        
                        # 按時間和相關度排序子頁面
                        subpages.sort(key=lambda p: (p.time_score, p.relevance_score), reverse=True)
                        
                        # 添加到隊列（限制數量）
                        for subpage in subpages[:objective.max_search_breadth]:
                            if subpage.url not in self.visited_urls:
                                queue.append((subpage.url, depth + 1, current_url))
                
            except Exception as e:
                logger.error(f"爬取 {current_url} 失敗: {e}")
                continue
        
        # 按時間優先度排序結果
        if objective.time_priority:
            pages.sort(key=lambda p: (p.time_score, p.relevance_score), reverse=True)
        
        logger.info(f"完成智慧爬取，共獲得 {len(pages)} 個頁面")
        return pages
    
    async def _crawl_single_page(
        self, 
        url: str, 
        objective: TaskObjective, 
        crawler: AsyncWebCrawler, 
        depth: int = 0, 
        parent_url: str = ""
    ) -> Optional[PageInfo]:
        """爬取單個頁面並分析"""
        try:
            # 基本爬取配置
            config = CrawlerRunConfig(
                word_count_threshold=10,
                cache_mode=CacheMode.BYPASS
            )
            
            result = await crawler.arun(url=url, config=config)
            
            # 動態處理結果，避免類型檢查問題
            crawl_result = None
            try:
                # 嘗試多種可能的結果結構
                if hasattr(result, 'results'):
                    crawl_result = getattr(result, 'results')[0]
                elif hasattr(result, '_results'):
                    crawl_result = getattr(result, '_results')[0]
                else:
                    crawl_result = result
            except:
                crawl_result = result
            
            if not crawl_result or not getattr(crawl_result, 'success', False):
                return None
            
            # 提取內容
            content = ""
            try:
                markdown = getattr(crawl_result, 'markdown', None)
                if markdown:
                    content = getattr(markdown, 'raw_markdown', '') or ""
            except:
                content = ""
            
            if not content or len(content.strip()) < 50:
                return None
            
            # 建立頁面資訊
            page_info = PageInfo(
                url=url,
                title=self._extract_title(crawl_result),
                content=content,
                depth=depth,
                parent_url=parent_url,
                found_via="direct" if depth == 0 else "subpage"
            )
            
            # 計算相關度分數
            page_info.relevance_score = await self._calculate_relevance(
                page_info.content, objective
            )
            
            # 提取和計算時間分數
            page_info.publish_date = self._extract_publish_date(crawl_result)
            page_info.time_score = self._calculate_time_score(
                page_info.publish_date, self.config.time_decay_hours
            )
            
            # 生成內容摘要
            if objective.enable_content_summary:
                page_info.summary = await self._generate_content_summary(
                    page_info.content, objective
                )
            
            return page_info
            
        except Exception as e:
            logger.error(f"爬取頁面 {url} 失敗: {e}")
            return None
    
    async def _find_relevant_subpages(
        self, 
        base_url: str, 
        objective: TaskObjective, 
        crawler: AsyncWebCrawler, 
        depth: int
    ) -> List[PageInfo]:
        """尋找相關子頁面"""
        subpages = []
        
        try:
            # 1. 嘗試站內搜索
            if self.config.enable_site_search:
                search_urls = await self._try_site_search(base_url, objective)
                for search_url in search_urls[:5]:  # 限制數量
                    if search_url not in self.visited_urls:
                        page_info = await self._crawl_single_page(
                            search_url, objective, crawler, depth, base_url
                        )
                        if page_info:
                            page_info.found_via = "site_search"
                            subpages.append(page_info)
            
            # 2. 解析頁面連結
            if self.config.enable_subpage_search:
                link_urls = await self._extract_relevant_links(base_url, objective, crawler)
                for link_url in link_urls[:objective.max_search_breadth]:
                    if link_url not in self.visited_urls:
                        page_info = await self._crawl_single_page(
                            link_url, objective, crawler, depth, base_url
                        )
                        if page_info:
                            page_info.found_via = "link_analysis"
                            subpages.append(page_info)
                            
        except Exception as e:
            logger.error(f"搜索子頁面失敗 {base_url}: {e}")
        
        return subpages
    
    async def _try_site_search(self, base_url: str, objective: TaskObjective) -> List[str]:
        """增強版站內搜索 - 使用LLM判斷搜索需求並執行動態搜索"""
        search_urls = []
        
        if not objective.enable_dynamic_search:
            return search_urls
        
        try:
            # 第一步：使用LLM判斷是否需要在此網站進行搜索
            search_decision = await self._llm_decide_search_strategy(base_url, objective)
            
            if not search_decision.get('should_search', False):
                logger.info(f"LLM判斷 {base_url} 不需要進行站內搜索")
                return search_urls
            
            logger.info(f"LLM判斷 {base_url} 需要進行站內搜索，策略: {search_decision.get('strategy', 'keyword_search')}")
            
            # 第二步：執行動態搜索
            if search_decision.get('strategy') == 'direct_navigation':
                # 直接導航到特定頁面
                target_paths = search_decision.get('target_paths', [])
                search_urls.extend(await self._try_direct_navigation(base_url, target_paths))
            
            elif search_decision.get('strategy') == 'keyword_search':
                # 關鍵字搜索
                search_keywords = search_decision.get('search_keywords', objective.keywords)
                search_urls.extend(await self._try_keyword_search(base_url, search_keywords))
            
            elif search_decision.get('strategy') == 'interactive_search':
                # 互動式搜索（模擬點擊和輸入）
                search_urls.extend(await self._try_interactive_search(base_url, objective))
            
            # 第三步：驗證搜索結果品質
            if search_urls:
                verified_urls = await self._verify_search_results(search_urls, objective)
                return verified_urls
            
        except Exception as e:
            logger.error(f"增強版站內搜索失敗 {base_url}: {e}")
        
        return search_urls
    
    async def _llm_decide_search_strategy(self, base_url: str, objective: TaskObjective) -> Dict[str, Any]:
        """使用LLM判斷搜索策略"""
        try:
            # 先快速爬取首頁內容進行分析
            async with AsyncWebCrawler(verbose=False) as crawler:
                config = CrawlerRunConfig(word_count_threshold=10, cache_mode=CacheMode.BYPASS)
                result = await crawler.arun(url=base_url, config=config)
                
                # 動態處理結果，避免類型檢查問題
                crawl_result = None
                try:
                    if hasattr(result, 'results'):
                        crawl_result = getattr(result, 'results')[0]
                    elif hasattr(result, '_results'):
                        crawl_result = getattr(result, '_results')[0]
                    else:
                        crawl_result = result
                except:
                    crawl_result = result
                
                if not crawl_result or not getattr(crawl_result, 'success', False):
                    return {'should_search': False}
                
                # 安全地獲取頁面內容
                page_content = ""
                try:
                    if hasattr(crawl_result, 'markdown'):
                        page_content = str(getattr(crawl_result, 'markdown', ''))[:3000]
                    elif hasattr(crawl_result, 'cleaned_html'):
                        page_content = str(getattr(crawl_result, 'cleaned_html', ''))[:3000]
                    else:
                        page_content = "無法獲取頁面內容"
                except Exception as e:
                    logger.warning(f"獲取頁面內容失敗: {e}")
                    page_content = "內容獲取錯誤"
                
            prompt = f"""分析以下網站首頁內容，判斷是否需要進行站內搜索來完成任務目標。

網站: {base_url}
任務目標: {objective.title}
任務描述: {objective.description}
關鍵字: {', '.join(objective.keywords)}

網站內容（前3000字）:
{page_content}

請根據以下判斷criteria分析：
1. 網站是否包含與任務相關的內容
2. 首頁是否已提供足夠資訊，還是需要深入搜索
3. 網站是否有搜索功能或明確的導航結構
4. 任務關鍵字在網站中的覆蓋程度

請用JSON格式回應，包含：
{{
    "should_search": true/false,
    "confidence": 0.0-1.0,
    "strategy": "keyword_search/direct_navigation/interactive_search/none",
    "reasoning": "判斷理由",
    "search_keywords": ["關鍵字1", "關鍵字2"],
    "target_paths": ["/path1", "/path2"],
    "expected_depth": 1-5
}}

搜索策略說明：
- keyword_search: 使用關鍵字在搜索框中搜索
- direct_navigation: 直接訪問特定路徑或頁面
- interactive_search: 需要模擬點擊和互動
- none: 不需要搜索
"""

            response = await self._call_llm_api(prompt)
            if response:
                try:
                    decision = json.loads(response.strip())
                    return decision
                except json.JSONDecodeError:
                    logger.warning(f"LLM回應JSON解析失敗: {response[:200]}")
            
            return {'should_search': False}
            
        except Exception as e:
            logger.error(f"LLM搜索策略判斷失敗: {e}")
            return {'should_search': False}
    
    async def _try_keyword_search(self, base_url: str, keywords: List[str]) -> List[str]:
        """嘗試關鍵字搜索"""
        search_urls = []
        domain = urlparse(base_url).netloc
        
        # 擴展的搜索URL模式
        search_patterns = [
            f"https://{domain}/search?q={{query}}",
            f"https://{domain}/search?query={{query}}",
            f"https://{domain}/?s={{query}}",
            f"https://{domain}/search/?q={{query}}",
            f"https://{domain}/search.php?q={{query}}",
            f"https://{domain}/search.html?q={{query}}",
            f"https://{domain}/site-search?query={{query}}",
            f"http://{domain}/search?q={{query}}",  # HTTP 版本
        ]
        
        # 為每個關鍵字組合嘗試搜索
        for i, keyword in enumerate(keywords[:3]):  # 限制前3個關鍵字
            query = keyword.replace(' ', '+')
            
            for pattern in search_patterns:
                search_url = None  # 初始化變量
                try:
                    search_url = pattern.format(query=query)
                    
                    # 驗證搜索頁面是否存在且返回有效內容
                    async with httpx.AsyncClient(timeout=15) as client:
                        response = await client.get(search_url, follow_redirects=True)
                        if response.status_code == 200 and len(response.text) > 1000:
                            # 檢查是否真的是搜索結果頁面
                            if self._is_search_results_page(response.text, keyword):
                                search_urls.append(search_url)
                                logger.info(f"找到有效搜索URL: {search_url}")
                                break  # 找到一個有效搜索就繼續下一個關鍵字
                                
                except Exception as e:
                    logger.debug(f"搜索URL測試失敗 {search_url or 'unknown'}: {e}")
                    continue
        
        return search_urls
    
    async def _try_direct_navigation(self, base_url: str, target_paths: List[str]) -> List[str]:
        """嘗試直接導航到特定路徑"""
        navigation_urls = []
        
        for path in target_paths:
            try:
                # 構建完整URL
                if path.startswith('/'):
                    full_url = urljoin(base_url, path)
                elif path.startswith('http'):
                    full_url = path
                else:
                    full_url = urljoin(base_url, '/' + path)
                
                # 驗證URL是否有效
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.head(full_url)
                    if response.status_code == 200:
                        navigation_urls.append(full_url)
                        logger.info(f"成功導航到: {full_url}")
                        
            except Exception as e:
                logger.debug(f"直接導航失敗 {path}: {e}")
                continue
        
        return navigation_urls
    
    async def _try_interactive_search(self, base_url: str, objective: TaskObjective) -> List[str]:
        """嘗試互動式搜索（模擬用戶行為）"""
        try:
            # 這裡可以整合 Playwright 或 Selenium 來模擬真實用戶互動
            # 現階段先實現基本的互動邏輯
            
            interactive_urls = []
            
            # 使用 AsyncWebCrawler 的 JavaScript 執行功能
            js_code = f"""
            // 嘗試找到搜索框並輸入關鍵字
            const searchKeywords = {json.dumps(objective.keywords[:2])};
            const searchSelectors = [
                'input[type="search"]',
                'input[name*="search"]',
                'input[id*="search"]',
                'input[placeholder*="搜"]',
                'input[placeholder*="Search"]'
            ];
            
            let searchResults = [];
            
            for (let keyword of searchKeywords) {{
                for (let selector of searchSelectors) {{
                    const searchInput = document.querySelector(selector);
                    if (searchInput) {{
                        searchInput.value = keyword;
                        
                        // 嘗試找到搜索按鈕
                        const submitSelectors = [
                            'button[type="submit"]',
                            'input[type="submit"]',
                            'button:contains("搜索")',
                            'button:contains("Search")',
                            '.search-button',
                            '#search-button'
                        ];
                        
                        for (let submitSelector of submitSelectors) {{
                            const submitBtn = document.querySelector(submitSelector);
                            if (submitBtn) {{
                                // 模擬點擊（實際環境中會觸發導航）
                                const form = searchInput.closest('form');
                                if (form) {{
                                    const action = form.action || window.location.href;
                                    const method = form.method || 'GET';
                                    searchResults.push({{
                                        action: action,
                                        keyword: keyword,
                                        method: method
                                    }});
                                }}
                                break;
                            }}
                        }}
                        break;
                    }}
                }}
            }}
            
            return searchResults;
            """
            
            async with AsyncWebCrawler(verbose=False) as crawler:
                config = CrawlerRunConfig(
                    js_code=js_code,
                    word_count_threshold=10,
                    cache_mode=CacheMode.BYPASS
                )
                result = await crawler.arun(url=base_url, config=config)
                
                # 解析 JavaScript 執行結果
                crawl_result = None
                try:
                    if hasattr(result, 'results'):
                        crawl_result = getattr(result, 'results')[0]
                    elif hasattr(result, '_results'):
                        crawl_result = getattr(result, '_results')[0]
                    else:
                        crawl_result = result
                except:
                    crawl_result = result
                
                if crawl_result and hasattr(crawl_result, 'js_execution_result'):
                    js_result = getattr(crawl_result, 'js_execution_result', None)
                    if js_result and isinstance(js_result, list):
                        for search_info in js_result:
                            if isinstance(search_info, dict) and 'action' in search_info:
                                search_url = search_info['action']
                                keyword = search_info.get('keyword', '')
                                
                                # 構建搜索URL
                                if '?' in search_url:
                                    search_url += f"&q={keyword}"
                                else:
                                    search_url += f"?q={keyword}"
                                
                                interactive_urls.append(search_url)
            
            return interactive_urls
            
        except Exception as e:
            logger.error(f"互動式搜索失敗 {base_url}: {e}")
            return []
    
    def _is_search_results_page(self, html_content: str, keyword: str) -> bool:
        """判斷是否為搜索結果頁面"""
        # 檢查常見的搜索結果頁面特徵
        search_indicators = [
            'search results',
            '搜索結果',
            '搜尋結果', 
            f'results for {keyword}',
            f'{keyword} 的搜索結果',
            'results found',
            '找到.*結果',
            'search-result',
            'search_result'
        ]
        
        html_lower = html_content.lower()
        return any(indicator.lower() in html_lower for indicator in search_indicators)
    
    async def _verify_search_results(self, search_urls: List[str], objective: TaskObjective) -> List[str]:
        """驗證搜索結果的品質"""
        verified_urls = []
        
        for url in search_urls:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        # 簡單的內容相關性檢查
                        content = response.text.lower()
                        keyword_matches = sum(1 for keyword in objective.keywords 
                                            if keyword.lower() in content)
                        
                        # 如果匹配到至少一個關鍵字，認為是有效的搜索結果
                        if keyword_matches > 0:
                            verified_urls.append(url)
                            
            except Exception as e:
                logger.debug(f"搜索結果驗證失敗 {url}: {e}")
                continue
        
        logger.info(f"驗證了 {len(search_urls)} 個搜索URL，其中 {len(verified_urls)} 個有效")
        return verified_urls
    
    async def _call_llm_api(self, prompt: str) -> Optional[str]:
        """調用LLM API的通用方法"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.2
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
                    return None
                    
        except Exception as e:
            logger.error(f"LLM API調用異常: {e}")
            return None
    
    async def _extract_relevant_links(
        self, 
        base_url: str, 
        objective: TaskObjective, 
        crawler: AsyncWebCrawler
    ) -> List[str]:
        """從頁面提取相關連結"""
        try:
            # 如果已經爬取過，從快取獲取
            if base_url in self.search_cache:
                return self.search_cache[base_url]
            
            config = CrawlerRunConfig(
                word_count_threshold=10,
                cache_mode=CacheMode.BYPASS
            )
            
            result = await crawler.arun(url=base_url, config=config)
            
            # 動態處理結果
            crawl_result = None
            try:
                if hasattr(result, '_results'):
                    crawl_result = getattr(result, '_results')[0]
                else:
                    crawl_result = result
            except:
                crawl_result = result
            
            if not crawl_result or not getattr(crawl_result, 'success', False):
                return []
            
            relevant_links = []
            
            # 從爬取結果提取連結
            try:
                links = getattr(crawl_result, 'links', None)
                if links:
                    if isinstance(links, dict):
                        internal_links = links.get('internal', [])
                    else:
                        internal_links = getattr(links, 'internal', [])
                    
                    # 分析連結相關性
                    for link_data in internal_links:
                        if isinstance(link_data, dict):
                            link_url = link_data.get('href', '')
                            link_text = link_data.get('text', '')
                            link_title = link_data.get('title', '')
                        else:
                            link_url = getattr(link_data, 'href', '')
                            link_text = getattr(link_data, 'text', '')
                            link_title = getattr(link_data, 'title', '')
                        
                        if link_url and self._is_relevant_link(link_url, link_text, link_title, objective):
                            full_url = urljoin(base_url, link_url)
                            relevant_links.append(full_url)
            except Exception as e:
                logger.error(f"處理連結時出錯: {e}")
            
            # 快取結果
            self.search_cache[base_url] = relevant_links
            return relevant_links
            
        except Exception as e:
            logger.error(f"提取連結失敗 {base_url}: {e}")
            return []
    
    def _is_relevant_link(
        self, 
        url: str, 
        text: str, 
        title: str, 
        objective: TaskObjective
    ) -> bool:
        """判斷連結是否相關"""
        if not url:
            return False
        
        # 排除明顯不相關的連結
        exclude_patterns = [
            r'\/contact', r'\/about', r'\/privacy', r'\/terms',
            r'\/login', r'\/register', r'\/cart', r'\/checkout',
            r'\.pdf$', r'\.jpg$', r'\.png$', r'\.gif$', r'\.zip$'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url.lower()):
                return False
        
        # 檢查關鍵字匹配
        check_text = f"{url} {text} {title}".lower()
        
        # 檢查是否包含目標關鍵字
        for keyword in objective.keywords:
            if keyword.lower() in check_text:
                return True
        
        # 檢查是否包含時間相關關鍵字（提高時效性內容優先級）
        time_keywords = ['news', 'update', 'latest', 'recent', '2024', '2025', 'today']
        for time_keyword in time_keywords:
            if time_keyword in check_text:
                return True
        
        return False
    
    def _extract_title(self, crawl_result) -> str:
        """提取頁面標題"""
        if hasattr(crawl_result, 'metadata') and crawl_result.metadata:
            title = crawl_result.metadata.get('title', '')
            if title:
                return title
        
        # 從內容中提取標題
        if hasattr(crawl_result, 'markdown') and crawl_result.markdown:
            content = getattr(crawl_result.markdown, 'raw_markdown', '') or ""
            # 簡單提取第一個標題
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('#') and len(line) > 2:
                    return line.lstrip('#').strip()
        
        return ""
    
    def _extract_publish_date(self, crawl_result) -> Optional[datetime]:
        """提取發布時間"""
        try:
            # 從 metadata 提取
            if hasattr(crawl_result, 'metadata') and crawl_result.metadata:
                # 檢查多種可能的日期欄位
                date_fields = ['publishedTime', 'datePublished', 'dateModified', 'pubDate', 'date']
                for field in date_fields:
                    date_str = crawl_result.metadata.get(field)
                    if date_str:
                        return self._parse_date_string(date_str)
            
            # 從內容中提取
            if hasattr(crawl_result, 'markdown') and crawl_result.markdown:
                content = getattr(crawl_result.markdown, 'raw_markdown', '') or ""
                date_match = self._extract_date_from_content(content)
                if date_match:
                    return date_match
            
        except Exception as e:
            logger.debug(f"提取日期失敗: {e}")
        
        return None
    
    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """解析日期字串"""
        try:
            # 嘗試多種格式
            date_formats = [
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S",
                "%d/%m/%Y",
                "%m/%d/%Y",
                "%B %d, %Y",
                "%d %B %Y"
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            # 嘗試使用 parsedate_to_datetime (RFC 2822 格式)
            try:
                return parsedate_to_datetime(date_str)
            except:
                pass
                
        except Exception:
            pass
        
        return None
    
    def _extract_date_from_content(self, content: str) -> Optional[datetime]:
        """從內容中提取日期"""
        # 常見的日期模式
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}/\d{1,2}/\d{4})',  # MM/DD/YYYY or DD/MM/YYYY
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
            r'(\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                for match in matches:
                    date_str = match if isinstance(match, str) else " ".join(match)
                    parsed = self._parse_date_string(date_str)
                    if parsed:
                        return parsed
        
        return None
    
    async def _evaluate_page_helpfulness(self, page_info: PageInfo, objective: TaskObjective) -> None:
        """評估頁面對爬蟲目標的幫助度"""
        try:
            prompt = f"""
請評估以下網頁內容對指定任務目標的幫助程度：

任務目標：
- 標題: {objective.title}
- 描述: {objective.description}
- 關鍵字: {', '.join(objective.keywords)}

網頁資訊：
- URL: {page_info.url}
- 標題: {page_info.title}
- 內容摘要: {page_info.summary[:500]}...

請從以下角度評估：
1. 內容相關性：是否直接相關於任務目標
2. 資訊價值：是否提供有用的數據、分析或見解
3. 時效性：資訊是否具有時效性價值
4. 完整性：資訊是否足夠完整有用

請返回JSON格式評估結果：
{{
    "is_helpful": true/false,
    "helpfulness_score": 0.0-1.0,
    "reason": "評估原因說明"
}}

只返回JSON，不要其他文字。
"""

            # 調用LLM進行評估
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.1
                }
                
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.llm_config.api_token}"},
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('choices') and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # 解析JSON回應
                        try:
                            evaluation = json.loads(content)
                            
                            page_info.is_helpful = evaluation.get('is_helpful', False)
                            page_info.helpfulness_score = evaluation.get('helpfulness_score', 0.0)
                            page_info.helpfulness_reason = evaluation.get('reason', '')
                            
                            logger.info(f"頁面幫助度評估 {page_info.url}: {page_info.helpfulness_score:.2f} ({'有幫助' if page_info.is_helpful else '無幫助'})")
                            
                        except json.JSONDecodeError:
                            # 如果JSON解析失敗，使用預設值
                            page_info.is_helpful = page_info.relevance_score > 0.6
                            page_info.helpfulness_score = page_info.relevance_score
                            page_info.helpfulness_reason = "LLM評估解析失敗，使用相關度作為參考"
                else:
                    # API調用失敗，使用相關度作為後備
                    page_info.is_helpful = page_info.relevance_score > 0.6
                    page_info.helpfulness_score = page_info.relevance_score
                    page_info.helpfulness_reason = "LLM API調用失敗，使用相關度作為後備評估"
                    
        except Exception as e:
            logger.error(f"評估頁面幫助度失敗: {e}")
            # 發生錯誤時的後備邏輯
            page_info.is_helpful = page_info.relevance_score > 0.6
            page_info.helpfulness_score = page_info.relevance_score
            page_info.helpfulness_reason = f"評估失敗: {str(e)}"
    
    def _calculate_time_score(self, publish_date: Optional[datetime], decay_hours: int) -> float:
        """計算時間權重分數"""
        if not publish_date:
            return 0.1  # 無日期的內容給予較低分數
        
        now = datetime.now()
        
        # 確保 publish_date 是 naive datetime（無時區信息）
        if publish_date.tzinfo is not None:
            publish_date = publish_date.replace(tzinfo=None)
        
        hours_diff = (now - publish_date).total_seconds() / 3600
        
        if hours_diff < 0:
            # 未來日期，可能是錯誤，給予中等分數
            return 0.5
        
        # 使用指數衰減函數
        # 在 decay_hours 內的內容獲得較高分數
        decay_factor = 2.0 / decay_hours  # 在衰減期內降到約 0.1
        time_score = max(0.05, min(1.0, 1.0 * (1.0 / (1.0 + decay_factor * hours_diff))))
        
        return time_score
    
    async def _calculate_relevance(self, content: str, objective: TaskObjective) -> float:
        """計算內容相關度"""
        if not content:
            return 0.0
        
        content_lower = content.lower()
        
        # 基於關鍵字的簡單相關度計算
        keyword_matches = 0
        total_keywords = len(objective.keywords) if objective.keywords else 1
        
        for keyword in objective.keywords:
            if keyword.lower() in content_lower:
                keyword_matches += 1
        
        keyword_score = keyword_matches / total_keywords
        
        # 檢查標題和描述中的關鍵詞
        title_desc = f"{objective.title} {objective.description}".lower()
        title_words = title_desc.split()
        
        title_matches = 0
        for word in title_words:
            if len(word) > 3 and word in content_lower:
                title_matches += 1
        
        title_score = min(1.0, title_matches / max(1, len(title_words)))
        
        # 綜合分數
        relevance = (keyword_score * 0.7 + title_score * 0.3)
        return min(1.0, relevance)
    
    async def _generate_content_summary(self, content: str, objective: TaskObjective, page_info: Optional[PageInfo] = None) -> str:
        """生成內容摘要，根據頁面幫助度動態調整詳細程度"""
        if not content or len(content.strip()) < 100:
            return "內容過短，無法生成摘要"
        
        try:
            # 根據幫助度決定內容長度和摘要詳細程度
            is_helpful = getattr(page_info, 'is_helpful', False) if page_info else False
            helpfulness_score = getattr(page_info, 'helpfulness_score', 0.0) if page_info else 0.0
            
            if is_helpful or helpfulness_score > 0.7:
                # 有幫助的內容：使用更多內容，生成詳細摘要
                content_snippet = content[:4000]  # 增加內容長度
                summary_type = "detailed"
            else:
                # 一般內容：使用較少內容，生成簡潔摘要
                content_snippet = content[:2000]
                summary_type = "brief"
            
            summary = await self._call_llm_for_summary(content_snippet, objective, summary_type)
            if summary:
                return summary
            
        except Exception as e:
            logger.error(f"生成摘要失敗: {e}")
        
        # fallback: 簡單摘要
        sentences = content.split('.')[:3]  # 取前3句
        return '. '.join(sentences)[:200] + "..."
    
    async def _call_llm_for_summary(self, content: str, objective: TaskObjective, summary_type: str = "brief") -> Optional[str]:
        """調用LLM生成摘要"""
        try:
            # 檢測是否使用本地LLM
            base_url = self.llm_config.base_url or ""
            is_local_llm = "localhost" in base_url or "127.0.0.1" in base_url
            
            if is_local_llm:
                # 使用本地LLM的 chat/completions API
                return await self._call_local_llm_chat(content, objective, summary_type)
            else:
                # 使用雲端LLM
                return await self._call_cloud_llm(content, objective, summary_type)
                
        except Exception as e:
            logger.error(f"LLM調用失敗: {e}")
            return None
    
    async def _call_local_llm_chat(self, content: str, objective: TaskObjective, summary_type: str = "brief") -> Optional[str]:
        """調用本地LLM的chat API，支援不同摘要詳細程度"""
        try:
            # 根據摘要類型調整prompt
            if summary_type == "detailed":
                prompt = f"""請為以下內容生成詳細摘要，重點關注與"{objective.title}"相關的信息：

內容：
{content}

要求：
1. 摘要控制在200-300字
2. 詳細分析關鍵信息、數據和觀點
3. 包含重要的細節和背景資訊
4. 分析可能的影響和意義
5. 保持客觀和準確
6. 使用繁體中文
7. 使用markdown格式加強可讀性

詳細摘要："""
            else:
                prompt = f"""請為以下內容生成簡潔摘要，重點關注與"{objective.title}"相關的信息：

內容：
{content}

要求：
1. 摘要控制在100字以內
2. 重點突出關鍵信息和數據
3. 保持客觀和準確
4. 使用繁體中文

摘要："""

            payload = {
                "model": getattr(self.llm_config, 'model', None) or "openai/gpt-oss-20b",
                "messages": [
                    {"role": "system", "content": "你是一個專業的內容分析師，擅長生成簡潔準確的摘要。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 150,
                "stream": False
            }
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("choices") and len(result["choices"]) > 0:
                        summary = result["choices"][0]["message"]["content"].strip()
                        return summary
                
        except Exception as e:
            logger.error(f"本地LLM調用失敗: {e}")
        
        return None
    
    async def _call_cloud_llm(self, content: str, objective: TaskObjective, summary_type: str = "brief") -> Optional[str]:
        """調用雲端LLM"""
        try:
            # 這裡可以實現OpenAI或其他雲端LLM的調用
            # 目前返回None，使用fallback
            return None
        except Exception as e:
            logger.error(f"雲端LLM調用失敗: {e}")
            return None

class SiteDiscoveryEngine:
    """站點發現引擎"""
    
    def __init__(self, config: DiscoveryConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config
        
    async def discover_sites(self, objective: TaskObjective) -> List[str]:
        """根據任務目標發現相關網站"""
        logger.info(f"開始站點發現: {objective.title}")
        
        # 第一步：LLM智慧推薦相關網站
        llm_recommended_urls = await self._llm_recommend_websites(objective)
        logger.info(f"LLM推薦了 {len(llm_recommended_urls)} 個網站")
        
        # 生成搜尋策略
        search_queries = await self._generate_search_queries(objective)
        
        # 模擬搜尋結果（實際實作應該調用搜尋 API）
        candidate_urls = await self._simulate_search(search_queries)
        
        # 合併LLM推薦和搜尋結果
        all_candidate_urls = list(set(llm_recommended_urls + candidate_urls))
        
        # 過濾和評分
        filtered_urls = self._filter_and_score_urls(all_candidate_urls, objective)
        
        logger.info(f"總共發現 {len(filtered_urls)} 個候選網站 (包含LLM推薦 {len(llm_recommended_urls)} 個)")
        return filtered_urls
    
    async def _generate_search_queries(self, objective: TaskObjective) -> List[str]:
        """生成搜尋查詢"""
        # 基本查詢
        base_queries = [
            objective.to_search_query(),
            f"{objective.title} news",
            f"{objective.title} analysis",
            f"{objective.title} report"
        ]
        
        # 添加關鍵字組合
        for keyword in objective.keywords:
            base_queries.append(f"{keyword} {objective.title}")
        
        return base_queries[:8]  # 限制查詢數量
    
    async def _simulate_search(self, queries: List[str]) -> List[str]:
        """模擬搜尋（實際應該調用搜尋 API）"""
        # 通用財經網站範例 - 使用通用模板而非特定股票
        financial_sites = [
            "https://finance.yahoo.com/",
        ]
        
        return financial_sites
    
    def _filter_and_score_urls(self, urls: List[str], objective: TaskObjective) -> List[str]:
        """過濾和評分 URL"""
        filtered_urls = []
        
        for url in urls:
            if self._is_valid_url(url) and self._passes_domain_filter(url, objective):
                filtered_urls.append(url)
        
        # 去重並限制數量
        unique_urls = list(set(filtered_urls))
        return unique_urls[:self.config.max_sites_per_engine]
    
    async def _llm_recommend_websites(self, objective: TaskObjective) -> List[str]:
        """使用LLM推薦相關網站"""
        try:
            prompt = f"""
根據以下任務內容，請推薦5-10個最相關的網站URL，這些網站應該能夠提供該主題的最新資訊和深度分析。

任務標題: {objective.title}
任務描述: {objective.description}
關鍵字: {', '.join(objective.keywords)}

請考慮以下因素：
1. 網站的權威性和可信度
2. 是否會有最新的相關資訊
3. 內容的深度和專業性
4. 針對該主題的專門報導

請直接返回網站URL列表，每行一個，格式如下：
https://example1.com
https://example2.com
...

只返回URL，不要其他解釋文字。
"""

            logger.info("正在請求LLM推薦相關網站...")
            
            # 直接調用chat API
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.3
                }
                
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.llm_config.api_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('choices') and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # 解析URL列表
                        urls = []
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.startswith('http'):
                                urls.append(line)
                        
                        logger.info(f"LLM推薦了 {len(urls)} 個網站")
                        return urls[:10]  # 限制最多10個
                
                logger.warning("LLM未返回有效的網站推薦")
                return []
            
        except Exception as e:
            logger.error(f"LLM網站推薦失敗: {e}")
            return []
    
    def _is_valid_url(self, url: str) -> bool:
        """檢查 URL 是否有效"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme in ['http', 'https'] and parsed.netloc)
        except:
            return False
    
    def _passes_domain_filter(self, url: str, objective: TaskObjective) -> bool:
        """檢查域名過濾條件"""
        if not self.config.enable_domain_filter:
            return True
            
        domain = urlparse(url).netloc.lower()
        
        # 檢查排除域名
        for exclude_domain in objective.exclude_domains:
            if exclude_domain.lower() in domain:
                return False
        
        # 如果指定目標域名，只允許目標域名
        if objective.target_domains:
            return any(target_domain.lower() in domain for target_domain in objective.target_domains)
        
        return True

class TaskDrivenCrawler:
    """任務驅動爬蟲主類"""
    
    def __init__(self, llm_config: LLMConfig):
        self.llm_config = llm_config
        self.discovery_config = DiscoveryConfig()
        self.adaptive_config = AdaptiveConfig(
            strategy="embedding",
            max_pages=20,
            confidence_threshold=0.7,
            embedding_llm_config={
                'provider': llm_config.provider,
                'api_token': llm_config.api_token,
                'base_url': llm_config.base_url
            }
        )
        
        self.discovery_engine = SiteDiscoveryEngine(self.discovery_config, llm_config)
        self.smart_search_engine = SmartSearchEngine(llm_config, self.discovery_config)
        
    async def execute_task(
        self,
        objective: TaskObjective,
        additional_urls: Optional[List[str]] = None,
        output_dir: str = "./crawl_results",
        target_confidence: float = 0.8,  # 新增：目標信心度
        max_iterations: int = 3  # 新增：最大迭代次數
    ) -> TaskResult:
        """執行完整的任務驅動爬取流程，包含動態信心度提升機制"""
        
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = TaskResult(task_id=task_id, objective=objective)
        
        try:
            logger.info(f"開始執行任務: {objective.title}")
            logger.info(f"目標信心度: {target_confidence:.1%}，最大迭代次數: {max_iterations}")
            result.status = "running"
            
            all_crawled_pages = []
            iteration = 0
            current_confidence = 0.0
            
            # 初始URL集合
            current_urls = await self.discovery_engine.discover_sites(objective)
            if additional_urls:
                valid_additional = [url for url in additional_urls if self._is_valid_url(url)]
                current_urls.extend(valid_additional)
                current_urls = list(set(current_urls))
            
            result.discovered_urls = current_urls.copy()
            
            while iteration < max_iterations and current_confidence < target_confidence:
                iteration += 1
                logger.info(f"=== 第 {iteration} 輪迭代 (目標信心度: {target_confidence:.1%}) ===")
                
                if iteration == 1:
                    logger.info("=== 階段一：站點發現 ===")
                    logger.info(f"總共 {len(current_urls)} 個種子 URL")
                else:
                    logger.info(f"=== 動態URL擴展 (第{iteration}輪) ===")
                    logger.info(f"當前信心度: {current_confidence:.1%}，需要提升至: {target_confidence:.1%}")
                
                # 智慧爬取階段
                logger.info("=== 階段二：智慧爬取 ===")
                iteration_pages = await self._smart_crawl_phase(current_urls, objective)
                all_crawled_pages.extend(iteration_pages)
                
                # 語意抽取階段
                logger.info("=== 階段三：語意抽取 ===")
                await self._extract_data_from_pages(all_crawled_pages, objective, result)
                
                # 計算當前信心度
                current_confidence = self._calculate_enhanced_confidence(all_crawled_pages, objective)
                logger.info(f"第 {iteration} 輪完成，當前信心度: {current_confidence:.2%}")
                
                # 檢查是否需要繼續迭代
                if current_confidence >= target_confidence:
                    logger.info(f"🎉 達到目標信心度 {target_confidence:.1%}！")
                    break
                elif iteration >= max_iterations:
                    logger.info(f"⚠️  達到最大迭代次數 {max_iterations}，停止搜索")
                    break
                elif self._should_stop_iteration(all_crawled_pages, iteration, objective):
                    logger.info("📊 滿足停止條件，結束迭代")
                    break
                else:
                    # 動態追加新的URL
                    logger.info("🔍 信心度未達標，請求LLM推薦更多相關網站...")
                    new_urls = await self._get_dynamic_urls(objective, all_crawled_pages, current_confidence)
                    
                    if new_urls:
                        # 過濾掉已經爬取過的URL
                        crawled_urls = {page.url for page in all_crawled_pages}
                        fresh_urls = [url for url in new_urls if url not in crawled_urls]
                        
                        if fresh_urls:
                            current_urls = fresh_urls
                            result.discovered_urls.extend(fresh_urls)
                            logger.info(f"📈 追加 {len(fresh_urls)} 個新URL進行下一輪爬取")
                        else:
                            logger.info("❌ 無新URL可用，停止迭代")
                            break
                    else:
                        logger.info("❌ LLM未推薦新URL，停止迭代")
                        break
            
            # 最終處理
            result.crawled_pages = len(all_crawled_pages)
            result.confidence_score = current_confidence
            
            # 生成頁面摘要
            if objective.enable_content_summary:
                result.page_summaries = [
                    {
                        "url": page.url,
                        "title": page.title,
                        "summary": page.summary,
                        "publish_date": page.publish_date.isoformat() if page.publish_date else None,
                        "time_score": page.time_score,
                        "relevance_score": page.relevance_score,
                        "depth": page.depth,
                        "found_via": page.found_via,
                        "is_helpful": getattr(page, 'is_helpful', False),
                        "helpfulness_score": getattr(page, 'helpfulness_score', 0.0),
                        "helpfulness_reason": getattr(page, 'helpfulness_reason', '')
                    }
                    for page in all_crawled_pages
                ]
            
            # 生成最終摘要
            if objective.output_format == "summary":
                summary = await self._generate_summary_from_pages(all_crawled_pages, objective)
                result.summary = summary
            
            # 統計信息
            result.search_stats = self._generate_search_stats(all_crawled_pages)
            result.helpfulness_stats = self._generate_helpfulness_stats(all_crawled_pages)
            
            result.status = "completed"
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            # 保存結果
            await self._save_results(result, output_dir)
            
            logger.info(f"任務完成！爬取 {result.crawled_pages} 個頁面，最終信心度: {result.confidence_score:.2%}")
            return result
            
        except Exception as e:
            result.status = "failed"
            result.error_messages.append(str(e))
            logger.error(f"任務執行失敗: {e}")
            raise
    
    async def _smart_crawl_phase(self, urls: List[str], objective: TaskObjective) -> List[PageInfo]:
        """執行智慧爬取階段"""
        all_pages = []
        
        async with AsyncWebCrawler() as crawler:
            for i, url in enumerate(urls[:5]):  # 限制處理的 URL 數量
                logger.info(f"智慧爬取網站 {i+1}/{min(len(urls), 5)}: {url}")
                
                try:
                    # 使用智慧搜索引擎進行深度爬取
                    site_pages = await self.smart_search_engine.smart_crawl_site(
                        url, objective, crawler
                    )
                    
                    if site_pages:
                        all_pages.extend(site_pages)
                        logger.info(f"從 {url} 獲得 {len(site_pages)} 個頁面")
                
                except Exception as e:
                    logger.error(f"智慧爬取 {url} 失敗: {e}")
                    continue
        
        # 根據時間和相關度進行最終排序
        if objective.time_priority:
            # 綜合時間分數和相關度分數
            all_pages.sort(
                key=lambda p: (p.time_score * 0.6 + p.relevance_score * 0.4), 
                reverse=True
            )
        else:
            all_pages.sort(key=lambda p: p.relevance_score, reverse=True)
        
        # 限制最終結果數量
        final_pages = all_pages[:objective.max_results]
        
        logger.info(f"智慧爬取完成，共獲得 {len(final_pages)} 個優質頁面")
        return final_pages
    
    async def _extract_structured_data_from_pages(self, pages: List[PageInfo], objective: TaskObjective) -> List[Dict]:
        """從頁面信息中抽取結構化資料"""
        if not pages:
            return []
        
        extracted_items = []
        
        for page in pages:
            if not page.content:
                continue
                
            try:
                # 使用 LLM 抽取結構化數據
                extracted = await self._extract_with_llm_enhanced(page, objective)
                
                if extracted:
                    item = {
                        "source_url": page.url,
                        "title": page.title,
                        "summary": page.summary,
                        "publish_date": page.publish_date.isoformat() if page.publish_date else None,
                        "time_score": page.time_score,
                        "relevance_score": page.relevance_score,
                        "depth": page.depth,
                        "found_via": page.found_via,
                        "extracted_at": datetime.now().isoformat(),
                        "data": extracted
                    }
                    extracted_items.append(item)
                    
            except Exception as e:
                logger.error(f"抽取 {page.url} 失敗: {e}")
                continue
        
        logger.info(f"成功抽取了 {len(extracted_items)} 條結構化資料")
        return extracted_items
    
    async def _extract_with_llm_enhanced(self, page: PageInfo, objective: TaskObjective) -> Optional[Dict]:
        """使用增強的LLM抽取結構化資料，包含重試機制和JSON修復"""
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 構建更嚴格的提示，確保JSON格式正確
                prompt = f"""從以下內容中抽取與 "{objective.title}" 相關的結構化資訊。

任務描述: {objective.description}
關鍵字: {', '.join(objective.keywords)}

頁面資訊:
標題: {page.title}
URL: {page.url}
發布時間: {page.publish_date.strftime('%Y-%m-%d') if page.publish_date else '未知'}
頁面摘要: {page.summary}

內容:
{page.content[:3000]}

請嚴格按照以下JSON格式返回，注意所有字串必須用雙引號包圍，不要包含未轉義的換行符：

{{
    "title": "主題或標題",
    "date": "日期格式YYYY-MM-DD或未知",
    "key_points": ["關鍵要點1", "關鍵要點2", "關鍵要點3"],
    "data_points": ["重要數據1", "重要數據2"],
    "predictions": ["預測或觀點1", "預測或觀點2"],
    "sentiment": "positive或negative或neutral",
    "confidence": 0.8,
    "time_relevance": "高或中或低",
    "source_credibility": "高或中或低"
}}

重要：只返回有效的JSON格式，不要包含任何其他文字、解釋或markdown格式。"""

                # 調用LLM
                response_text = await self._call_llm_with_retry(prompt, objective)
                
                if response_text:
                    # 多層次清理和修復JSON
                    parsed_json = self._robust_json_parse(response_text)
                    if parsed_json:
                        # 驗證JSON結構的完整性
                        if self._validate_extracted_data(parsed_json):
                            return parsed_json
                
                logger.warning(f"第 {attempt + 1} 次抽取嘗試失敗，重試...")
                
            except Exception as e:
                logger.error(f"第 {attempt + 1} 次抽取失敗: {e}")
                
        # 所有重試失敗，返回基本結構
        logger.warning(f"LLM抽取最終失敗，返回基本結構")
        return self._create_fallback_extraction(page)
    
    async def _call_llm_with_retry(self, prompt: str, objective: TaskObjective) -> Optional[str]:
        """帶重試的LLM調用"""
        try:
            # 使用更嚴格的參數控制JSON輸出
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.1,  # 降低溫度確保一致性
                    "top_p": 0.9,
                    "frequency_penalty": 0.1
                }
                
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.llm_config.api_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('choices') and len(result['choices']) > 0:
                        return result['choices'][0]['message']['content'].strip()
                        
        except Exception as e:
            logger.error(f"LLM調用失敗: {e}")
            
        return None
    
    def _robust_json_parse(self, response_text: str) -> Optional[Dict]:
        """強化的JSON解析，包含多種修復策略"""
        try:
            # 第一步：基本清理
            clean_response = response_text.strip()
            
            # 移除markdown標記
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            elif clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            
            clean_response = clean_response.strip()
            
            # 第二步：尝试直接解析
            try:
                return json.loads(clean_response)
            except json.JSONDecodeError as e:
                logger.debug(f"直接解析失敗: {e}")
            
            # 第三步：修復常見JSON問題
            # 移除末尾多餘的逗號
            clean_response = re.sub(r',\s*}', '}', clean_response)
            clean_response = re.sub(r',\s*]', ']', clean_response)
            
            # 修復未轉義的換行符
            clean_response = clean_response.replace('\n', '\\n').replace('\r', '\\r')
            
            # 修復未轉義的引號
            clean_response = re.sub(r'(?<!\\)"(?=.*")', '\\"', clean_response)
            
            try:
                return json.loads(clean_response)
            except json.JSONDecodeError as e:
                logger.debug(f"修復後解析失敗: {e}")
            
            # 第四步：嘗試提取JSON片段
            json_match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"JSON解析錯誤: {e}")
            return None
    
    def _validate_extracted_data(self, data: Dict) -> bool:
        """驗證抽取資料的完整性"""
        required_fields = ['title', 'key_points', 'sentiment', 'confidence']
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"缺少必要欄位: {field}")
                return False
        
        # 確保列表欄位是真的列表
        list_fields = ['key_points', 'data_points', 'predictions']
        for field in list_fields:
            if field in data and not isinstance(data[field], list):
                data[field] = [str(data[field])] if data[field] else []
        
        # 確保confidence是數字
        if not isinstance(data.get('confidence'), (int, float)):
            data['confidence'] = 0.5
        
        return True
    
    def _create_fallback_extraction(self, page: PageInfo) -> Dict:
        """創建後備抽取結果"""
        return {
            "title": page.title or "無標題",
            "date": page.publish_date.strftime('%Y-%m-%d') if page.publish_date else "未知",
            "key_points": [f"頁面內容摘要: {page.summary[:100]}..."] if page.summary else ["無關鍵要點"],
            "data_points": [],
            "predictions": [],
            "sentiment": "neutral",
            "confidence": 0.3,  # 低信心度反映這是後備結果
            "time_relevance": "未評估",
            "source_credibility": "未評估"
        }
    
    async def _generate_summary_from_pages(self, pages: List[PageInfo], objective: TaskObjective) -> str:
        """從頁面信息生成摘要"""
        if not pages:
            return "無可用內容生成摘要"
        
        # 準備摘要內容
        summary_parts = []
        summary_parts.append(f"# {objective.title} 智慧分析報告\n")
        summary_parts.append(f"**生成時間:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        summary_parts.append(f"**分析頁面數:** {len(pages)}\n")
        
        # 按時間分組分析
        recent_pages = [p for p in pages if p.time_score > 0.5]
        older_pages = [p for p in pages if p.time_score <= 0.5]
        
        if recent_pages:
            summary_parts.append(f"\n## 最新資訊 ({len(recent_pages)} 個來源)\n")
            for page in recent_pages[:5]:  # 只顯示前5個
                summary_parts.append(f"- **{page.title}** ([來源]({page.url}))")
                if page.summary:
                    summary_parts.append(f"  {page.summary}\n")
                if page.publish_date:
                    summary_parts.append(f"  *發布時間: {page.publish_date.strftime('%Y-%m-%d')}*\n")
        
        if older_pages:
            summary_parts.append(f"\n## 背景資訊 ({len(older_pages)} 個來源)\n")
            # 只顯示最相關的幾個
            older_pages.sort(key=lambda p: p.relevance_score, reverse=True)
            for page in older_pages[:3]:
                summary_parts.append(f"- **{page.title}** ([來源]({page.url}))")
                if page.summary:
                    summary_parts.append(f"  {page.summary}\n")
        
        # 深度搜索統計
        depth_stats = {}
        for page in pages:
            depth_stats[page.depth] = depth_stats.get(page.depth, 0) + 1
        
        summary_parts.append(f"\n## 搜索統計\n")
        summary_parts.append(f"- 搜索深度分佈: {dict(depth_stats)}")
        summary_parts.append(f"- 平均相關度: {sum(p.relevance_score for p in pages) / len(pages):.2f}")
        summary_parts.append(f"- 平均時間分數: {sum(p.time_score for p in pages) / len(pages):.2f}")
        
        return "\n".join(summary_parts)
    
    def _calculate_enhanced_confidence(self, pages: List[PageInfo], objective: TaskObjective) -> float:
        """計算增強的信心度分數"""
        if not pages:
            return 0.0
        
        # 基礎分數：頁面數量
        quantity_score = min(1.0, len(pages) / 10)  # 10個頁面為滿分
        
        # 相關度分數
        avg_relevance = sum(p.relevance_score for p in pages) / len(pages)
        
        # 時間新鮮度分數
        avg_time_score = sum(p.time_score for p in pages) / len(pages)
        
        # 深度覆蓋分數（深度越大，覆蓋越全面）
        max_depth = max(p.depth for p in pages) if pages else 0
        depth_score = min(1.0, max_depth / objective.max_search_depth)
        
        # 來源多樣性分數
        unique_domains = len(set(urlparse(p.url).netloc for p in pages))
        diversity_score = min(1.0, unique_domains / 3)  # 3個不同域名為滿分
        
        # 綜合計算
        confidence = (
            quantity_score * 0.25 +
            avg_relevance * 0.35 +
            avg_time_score * 0.2 +
            depth_score * 0.1 +
            diversity_score * 0.1
        )
        
        return min(1.0, confidence)
    
    def _generate_search_stats(self, pages: List[PageInfo]) -> Dict[str, Any]:
        """生成搜索統計信息"""
        if not pages:
            return {}
        
        stats = {
            "total_pages": len(pages),
            "avg_relevance_score": sum(p.relevance_score for p in pages) / len(pages),
            "avg_time_score": sum(p.time_score for p in pages) / len(pages),
            "depth_distribution": {},
            "found_via_distribution": {},
            "domain_distribution": {},
            "date_range": {
                "earliest": None,
                "latest": None,
                "with_dates": 0
            }
        }
        
        # 深度分佈
        for page in pages:
            depth = page.depth
            stats["depth_distribution"][depth] = stats["depth_distribution"].get(depth, 0) + 1
        
        # 發現方式分佈
        for page in pages:
            found_via = page.found_via
            stats["found_via_distribution"][found_via] = stats["found_via_distribution"].get(found_via, 0) + 1
        
        # 域名分佈
        for page in pages:
            domain = urlparse(page.url).netloc
            stats["domain_distribution"][domain] = stats["domain_distribution"].get(domain, 0) + 1
        
        # 日期範圍
        dated_pages = [p for p in pages if p.publish_date]
        if dated_pages:
            dates = [p.publish_date for p in dated_pages if p.publish_date is not None]
            if dates:
                stats["date_range"]["earliest"] = min(dates).isoformat()
                stats["date_range"]["latest"] = max(dates).isoformat()
                stats["date_range"]["with_dates"] = len(dated_pages)
        
        return stats
    
    async def _call_llm_simple(self, prompt: str, objective: Optional[TaskObjective] = None) -> Optional[str]:
        """簡化的 LLM 調用"""
        try:
            # 創建一個臨時的objective如果沒有提供
            if objective is None:
                objective = TaskObjective(title="通用查詢", description="LLM調用")
            
            # 使用智慧搜索引擎的LLM調用
            return await self.smart_search_engine._call_llm_for_summary(prompt, objective)
            
        except Exception as e:
            logger.error(f"LLM調用失敗: {e}")
            return None
    
    def _is_valid_url(self, url: str) -> bool:
        """檢查 URL 是否有效"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme in ['http', 'https'] and parsed.netloc)
        except:
            return False
    
    async def _save_results(self, result: TaskResult, output_dir: str):
        """保存結果"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存主要結果
        result_file = output_path / f"{result.task_id}_result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            # 轉換為可序列化格式
            result_dict = asdict(result)
            result_dict['start_time'] = result.start_time.isoformat()
            result_dict['end_time'] = result.end_time.isoformat() if result.end_time else None
            json.dump(result_dict, f, indent=2, ensure_ascii=False)
        
        # 保存結構化資料
        if result.extracted_data:
            data_file = output_path / f"{result.task_id}_data.jsonl"
            with open(data_file, 'w', encoding='utf-8') as f:
                for item in result.extracted_data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        # 保存頁面摘要
        if result.page_summaries:
            summaries_file = output_path / f"{result.task_id}_summaries.json"
            with open(summaries_file, 'w', encoding='utf-8') as f:
                json.dump(result.page_summaries, f, indent=2, ensure_ascii=False)
        
        # 保存摘要
        if result.summary:
            summary_file = output_path / f"{result.task_id}_summary.md"
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(f"# {result.objective.title}\n\n")
                f.write(f"**執行時間:** {result.start_time}\n\n")
                f.write(f"**信心度:** {result.confidence_score:.2%}\n\n")
                f.write("## 摘要\n\n")
                f.write(result.summary)
        
        # 保存搜索統計
        if result.search_stats:
            stats_file = output_path / f"{result.task_id}_stats.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(result.search_stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"結果已保存到: {output_dir}")

    # 新增的輔助方法
    async def _extract_data_from_pages(self, pages: List[PageInfo], objective: TaskObjective, result: TaskResult) -> None:
        """從頁面中抽取結構化資料"""
        extracted_data = []
        
        for page in pages:
            try:
                # 使用增強的LLM抽取
                extracted = await self._extract_with_llm_enhanced(page, objective)
                if extracted:
                    # 添加頁面元信息
                    extracted['source_url'] = page.url
                    extracted['extracted_at'] = page.extracted_at.isoformat()
                    extracted['is_helpful'] = getattr(page, 'is_helpful', False)
                    extracted['helpfulness_score'] = getattr(page, 'helpfulness_score', 0.0)
                    extracted['helpfulness_reason'] = getattr(page, 'helpfulness_reason', '')
                    extracted_data.append(extracted)
            except Exception as e:
                logger.error(f"抽取頁面 {page.url} 資料失敗: {e}")
        
        result.extracted_data = extracted_data
        logger.info(f"成功抽取了 {len(extracted_data)} 條結構化資料")
    
    def _should_stop_iteration(self, pages: List[PageInfo], iteration: int, objective: TaskObjective) -> bool:
        """增強版停止條件判斷 - 根據搜索嚴格度調整"""
        if not pages:
            return True
        
        # 根據搜索嚴格度調整參數
        strictness = getattr(objective, 'search_strictness', 'moderate')
        
        if strictness == "strict":
            recent_check_pages = 15  # 嚴格模式：檢查最近15頁
            confidence_check_pages = 25  # 嚴格模式：檢查最近25頁信心度
            min_confidence_improvement = 0.08  # 需要8%的信心度提升
            max_unhelpful_ratio = 0.2  # 最多允許20%的無幫助頁面
        elif strictness == "relaxed":
            recent_check_pages = 30  # 寬鬆模式：檢查最近30頁
            confidence_check_pages = 40  # 寬鬆模式：檢查最近40頁信心度
            min_confidence_improvement = 0.03  # 需要3%的信心度提升
            max_unhelpful_ratio = 0.4  # 最多允許40%的無幫助頁面
        else:  # moderate
            recent_check_pages = 20  # 中等模式：檢查最近20頁
            confidence_check_pages = 30  # 中等模式：檢查最近30頁信心度
            min_confidence_improvement = 0.05  # 需要5%的信心度提升
            max_unhelpful_ratio = 0.3  # 最多允許30%的無幫助頁面
        
        # 條件1：檢查最近頁面的幫助度比例
        recent_pages = pages[-recent_check_pages:]
        if len(recent_pages) >= recent_check_pages:
            helpful_recent = sum(1 for p in recent_pages if getattr(p, 'is_helpful', False))
            unhelpful_ratio = 1 - (helpful_recent / len(recent_pages))
            
            if unhelpful_ratio > max_unhelpful_ratio:
                logger.info(f"停止條件：最近{recent_check_pages}個頁面中{unhelpful_ratio:.1%}無幫助（超過{max_unhelpful_ratio:.1%}閾值）")
                return True
        
        # 條件2：檢查信心度增長趨勢
        if len(pages) >= confidence_check_pages:
            early_confidence = self._calculate_enhanced_confidence(pages[:confidence_check_pages//2], objective)
            recent_confidence = self._calculate_enhanced_confidence(pages[-confidence_check_pages//2:], objective)
            confidence_improvement = recent_confidence - early_confidence
            
            if confidence_improvement < min_confidence_improvement:
                logger.info(f"停止條件：信心度提升僅{confidence_improvement:.2%}（低於{min_confidence_improvement:.1%}閾值）")
                return True
        
        # 條件3：動態搜索特定條件
        if getattr(objective, 'enable_dynamic_search', True):
            # 如果啟用動態搜索，增加更嚴格的條件
            
            # 檢查深度分佈 - 如果深度過深但收益遞減
            depth_distribution = {}
            for page in pages:
                depth = getattr(page, 'depth', 0)
                if depth not in depth_distribution:
                    depth_distribution[depth] = {'total': 0, 'helpful': 0}
                depth_distribution[depth]['total'] += 1
                if getattr(page, 'is_helpful', False):
                    depth_distribution[depth]['helpful'] += 1
            
            # 如果深度3以上的頁面幫助度低於20%，停止深入
            deep_pages = [info for depth, info in depth_distribution.items() if depth >= 3]
            if deep_pages:
                total_deep = sum(info['total'] for info in deep_pages)
                helpful_deep = sum(info['helpful'] for info in deep_pages)
                if total_deep >= 10 and (helpful_deep / total_deep) < 0.2:
                    logger.info(f"停止條件：深度3+頁面幫助度過低（{helpful_deep}/{total_deep} = {helpful_deep/total_deep:.1%}）")
                    return True
        
        # 條件4：檢查關鍵字覆蓋停滯
        if len(pages) >= 20:
            # 分析關鍵字在內容中的覆蓋情況
            early_pages = pages[:len(pages)//2]
            recent_pages = pages[len(pages)//2:]
            
            def get_keyword_coverage(page_list):
                all_content = " ".join([getattr(p, 'content', '')[:500] for p in page_list])
                covered = sum(1 for kw in objective.keywords if kw.lower() in all_content.lower())
                return covered / len(objective.keywords) if objective.keywords else 0
            
            early_coverage = get_keyword_coverage(early_pages)
            recent_coverage = get_keyword_coverage(recent_pages)
            
            # 如果關鍵字覆蓋沒有改善且低於閾值，停止
            if early_coverage > 0 and recent_coverage <= early_coverage and recent_coverage < 0.7:
                logger.info(f"停止條件：關鍵字覆蓋停滯（早期:{early_coverage:.1%}，近期:{recent_coverage:.1%}）")
                return True
        
        return False
    
    async def _llm_recommend_websites(self, task_title: str, keywords: List[str], max_sites: int = 5, content_gaps: str = "", current_confidence: float = 0.0) -> List[str]:
        """請LLM推薦相關網站 - 增強台灣本地化"""
        try:
            # 檢測任務是否與台灣/中文相關
            taiwan_related = any(keyword in task_title.lower() + ' '.join(keywords).lower() 
                               for keyword in ['台灣', '臺灣', '中文', '繁體', '中華民國', '新台幣', 'taiwan', 'tw'])
            
            base_prompt = f"""針對任務「{task_title}」，請推薦 {max_sites} 個最權威且相關的網站URL。

關鍵字: {', '.join(keywords)}
當前信心度: {current_confidence:.1%}
{f"內容缺口分析: {content_gaps}" if content_gaps else ""}

請推薦能提供以下類型資訊的權威網站：
1. 官方網站或政府機構
2. 權威新聞媒體
3. 專業分析機構
4. 學術或研究機構
5. 產業專家部落格"""

            # 根據是否與台灣相關調整prompt
            if taiwan_related:
                specific_prompt = f"""{base_prompt}

**特別要求（台灣相關任務）：**
- 優先推薦台灣本地網站（.tw 域名）
- 包含台灣政府機構、在地媒體、本土企業網站
- 推薦順序：台灣官方網站 > 台灣媒體 > 台灣學術機構 > 國際權威網站
- 建議包含：政府網站(.gov.tw)、新聞媒體(.com.tw)、教育機構(.edu.tw)

要求：
- 只返回URL列表，每行一個
- 至少 {max(2, max_sites//2)} 個台灣本地網站
- 確保網站的權威性和可信度
- 優先選擇繁體中文內容"""
            else:
                specific_prompt = f"""{base_prompt}

要求：
- 只返回URL列表，每行一個
- 優先選擇可能包含最新和詳細資訊的網站
- 確保網站的權威性和可信度
- 考慮地理相關性和語言適配性"""

            prompt = specific_prompt

            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
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
                    content = data['choices'][0]['message']['content']
                    
                    # 解析URL
                    urls = []
                    for line in content.strip().split('\n'):
                        line = line.strip()
                        if line.startswith('http'):
                            urls.append(line)
                    
                    logger.info(f"LLM推薦了 {len(urls)} 個網站")
                    return urls[:max_sites]
                else:
                    logger.error(f"LLM API調用失敗: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"LLM網站推薦失敗: {e}")
        
        return []
    
    async def _get_dynamic_urls(self, objective: TaskObjective, crawled_pages: List[PageInfo], current_confidence: float) -> List[str]:
        """根據已爬取內容動態生成新的URL"""
        try:
            # 分析內容缺口
            content_gaps = self._analyze_content_gaps(crawled_pages, objective)
            
            # 請求LLM推薦新的URL
            new_urls = await self._llm_recommend_websites(
                objective.title,
                objective.keywords,
                max_sites=3,  # 每次只追加少量URL避免過度擴張
                content_gaps=content_gaps,
                current_confidence=current_confidence
            )
            
            return new_urls
        except Exception as e:
            logger.error(f"動態URL生成失敗: {e}")
            return []
    
    def _analyze_content_gaps(self, pages: List[PageInfo], objective: TaskObjective) -> str:
        """分析已爬取內容的缺口"""
        try:
            helpful_pages = [p for p in pages if getattr(p, 'is_helpful', False)]
            
            if not helpful_pages:
                return "缺乏相關內容，需要尋找更多基礎資料"
            
            # 簡單的關鍵詞覆蓋分析
            all_content = " ".join([p.content[:1000] for p in helpful_pages])
            covered_keywords = []
            missing_keywords = []
            
            for keyword in objective.keywords:
                if keyword.lower() in all_content.lower():
                    covered_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)
            
            gaps = []
            if missing_keywords:
                gaps.append(f"缺少關鍵字：{', '.join(missing_keywords)}")
            
            if len(helpful_pages) < 3:
                gaps.append("需要更多相關資料來源")
            
            return "; ".join(gaps) if gaps else "內容較為完整，需要更深入的分析"
            
        except Exception as e:
            logger.error(f"內容缺口分析失敗: {e}")
            return "需要更多相關內容"

    def _generate_helpfulness_stats(self, pages: List[PageInfo]) -> Dict[str, Any]:
        """生成幫助度統計"""
        try:
            total_pages = len(pages)
            helpful_pages = sum(1 for p in pages if getattr(p, 'is_helpful', False))
            
            helpfulness_scores = [getattr(p, 'helpfulness_score', 0.0) for p in pages]
            avg_helpfulness = sum(helpfulness_scores) / len(helpfulness_scores) if helpfulness_scores else 0.0
            
            return {
                'total_pages': total_pages,
                'helpful_pages': helpful_pages,
                'helpfulness_ratio': helpful_pages / total_pages if total_pages > 0 else 0.0,
                'avg_helpfulness_score': avg_helpfulness
            }
        except Exception as e:
            logger.error(f"幫助度統計生成失敗: {e}")
            return {}

# 便利函數
async def create_task_crawler(llm_config: LLMConfig) -> TaskDrivenCrawler:
    """建立任務驅動爬蟲"""
    return TaskDrivenCrawler(llm_config)

async def quick_crawl_task(
    title: str,
    description: str,
    llm_config: LLMConfig,
    keywords: Optional[List[str]] = None,
    output_format: str = "structured",
    additional_urls: Optional[List[str]] = None,
    output_dir: str = "./crawl_results",
    time_priority: bool = True,
    max_search_depth: int = 5,  # 提高預設搜索深度到5層
    max_search_breadth: int = 10,
    enable_content_summary: bool = True,
    enable_dynamic_search: bool = True,  # 新增：啟用動態搜索
    search_strictness: str = "strict",  # 新增：嚴格搜索模式
    target_confidence: float = 0.8,  # 新增：目標信心度
    max_iterations: int = 3  # 新增：最大迭代次數
) -> TaskResult:
    """快速執行爬取任務，支援動態信心度提升和智慧搜索"""
    
    objective = TaskObjective(
        title=title,
        description=description,
        keywords=keywords or [],
        output_format=output_format,
        time_priority=time_priority,
        max_search_depth=max_search_depth,
        max_search_breadth=max_search_breadth,
        enable_content_summary=enable_content_summary,
        enable_dynamic_search=enable_dynamic_search,
        search_strictness=search_strictness
    )
    
    crawler = await create_task_crawler(llm_config)
    return await crawler.execute_task(
        objective, 
        additional_urls, 
        output_dir,
        target_confidence=target_confidence,
        max_iterations=max_iterations
    )

# 範例使用
async def example_nvidia_analysis():
    """範例：NVIDIA 股價分析 - 展示新功能"""
    
    # 配置本地 LLM
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://localhost:1234/v1",  # 更新為正確的本地LLM地址
        api_token="local-token"
    )
    
    # 執行任務（使用新功能）
    result = await quick_crawl_task(
        title="台積電股價分析",
        description="收集台積電最新投資分析和預測",
        llm_config=llm_config,
        keywords=["台積電", "TSM", "股價", "半導體"],
        output_format="structured",
        additional_urls=[
            "https://investor.tsmc.com/",
            "https://finance.yahoo.com/quote/TSM"
        ],
        time_priority=True,  # 啟用時間優先度
        max_search_depth=3,  # 最大搜索深度3層
        max_search_breadth=8,  # 每層最多8個頁面
        enable_content_summary=True  # 啟用內容摘要
    )
    
    print(f"\n=== 任務執行完成 ===")
    print(f"任務 ID: {result.task_id}")
    print(f"狀態: {result.status}")
    print(f"發現網站: {len(result.discovered_urls)} 個")
    print(f"爬取頁面: {result.crawled_pages} 個")
    print(f"信心度: {result.confidence_score:.2%}")
    print(f"執行時間: {result.execution_time:.1f} 秒")
    
    if result.page_summaries:
        print(f"\n=== 頁面摘要 ===")
        for i, summary in enumerate(result.page_summaries[:3]):  # 顯示前3個
            print(f"{i+1}. {summary['title']}")
            print(f"   URL: {summary['url']}")
            print(f"   摘要: {summary['summary'][:100]}...")
            print(f"   時間分數: {summary['time_score']:.2f}")
            print(f"   相關度: {summary['relevance_score']:.2f}")
            print(f"   深度: {summary['depth']}")
            print()
    
    if result.extracted_data:
        print(f"\n=== 抽取資料預覽 ===")
        for i, item in enumerate(result.extracted_data[:2]):  # 顯示前2個
            print(f"{i+1}. {item['data'].get('title', 'N/A')}")
            print(f"   來源: {item['source_url']}")
            print(f"   關鍵點: {item['data'].get('key_points', [])}")
            print()
    
    if result.search_stats:
        print(f"\n=== 搜索統計 ===")
        stats = result.search_stats
        print(f"總頁面: {stats['total_pages']}")
        print(f"平均相關度: {stats['avg_relevance_score']:.2f}")
        print(f"平均時間分數: {stats['avg_time_score']:.2f}")
        print(f"深度分佈: {stats['depth_distribution']}")
        print(f"發現方式分佈: {stats['found_via_distribution']}")
        if stats['date_range']['with_dates'] > 0:
            print(f"日期範圍: {stats['date_range']['earliest']} ~ {stats['date_range']['latest']}")
    
    # 新增的輔助方法
    async def _extract_data_from_pages(self, pages: List[PageInfo], objective: TaskObjective, result: TaskResult) -> None:
        """從頁面中抽取結構化資料"""
        extracted_data = []
        
        for page in pages:
            try:
                # 使用增強的LLM抽取
                extracted = await self._extract_with_llm_enhanced(page, objective)
                if extracted:
                    # 添加頁面元信息
                    extracted['source_url'] = page.url
                    extracted['extracted_at'] = page.extracted_at.isoformat()
                    extracted['is_helpful'] = getattr(page, 'is_helpful', False)
                    extracted['helpfulness_score'] = getattr(page, 'helpfulness_score', 0.0)
                    extracted['helpfulness_reason'] = getattr(page, 'helpfulness_reason', '')
                    extracted_data.append(extracted)
            except Exception as e:
                logger.error(f"抽取頁面 {page.url} 資料失敗: {e}")
        
        result.extracted_data = extracted_data
        logger.info(f"成功抽取了 {len(extracted_data)} 條結構化資料")
    
    def _should_stop_iteration(self, pages: List[PageInfo], iteration: int) -> bool:
        """判斷是否應該停止迭代的條件"""
        if not pages:
            return True
        
        # 條件1：如果最近的頁面都沒有幫助內容
        recent_pages = pages[-5:]  # 檢查最近5個頁面
        helpful_recent = sum(1 for p in recent_pages if getattr(p, 'is_helpful', False))
        if len(recent_pages) >= 5 and helpful_recent == 0:
            logger.info("停止條件：最近5個頁面都無幫助內容")
            return True
        
        # 條件2：信心度增長緩慢或停滯
        if iteration >= 2:
            # 檢查前後兩輪的信心度增長
            mid_point = len(pages) // 2
            first_half_confidence = self._calculate_enhanced_confidence(pages[:mid_point], None)
            second_half_confidence = self._calculate_enhanced_confidence(pages[mid_point:], None)
            
            if second_half_confidence - first_half_confidence < 0.05:  # 增長少於5%
                logger.info("停止條件：信心度增長緩慢")
                return True
        
        # 條件3：資源耗盡限制
        total_pages = len(pages)
        if total_pages >= 50:  # 避免過度爬取
            logger.info("停止條件：達到頁面數量上限")
            return True
        
        return False
    
    async def _get_dynamic_urls(self, objective: TaskObjective, existing_pages: List[PageInfo], current_confidence: float) -> List[str]:
        """動態獲取更多相關URL"""
        try:
            # 分析現有頁面的不足之處
            analysis = self._analyze_content_gaps(existing_pages, objective)
            
            prompt = f"""基於當前爬取結果分析，任務 "{objective.title}" 的信心度只有 {current_confidence:.1%}，需要推薦更多高品質相關網站。

任務描述: {objective.description}
關鍵字: {', '.join(objective.keywords)}

當前內容分析:
{analysis}

請推薦5-8個能夠補強以下方面的權威網站URL：
1. 提供更深入的專業分析
2. 包含最新的市場數據和趨勢
3. 權威機構或專家觀點
4. 技術細節和發展前景

要求：
- 只返回URL列表，每行一個
- 選擇該領域最權威的網站
- 優先推薦可能包含具體數據和分析的頁面
- 避免推薦已爬取過的域名

URL列表："""

            async with httpx.AsyncClient() as client:
                payload = {
                    "model": "openai/gpt-oss-20b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 400,
                    "temperature": 0.3
                }
                
                response = await client.post(
                    f"{self.llm_config.base_url}/chat/completions",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.llm_config.api_token}"},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('choices') and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content'].strip()
                        
                        # 解析URL列表
                        urls = []
                        for line in content.split('\n'):
                            line = line.strip()
                            if line.startswith('http'):
                                urls.append(line)
                        
                        logger.info(f"LLM推薦了 {len(urls)} 個新URL")
                        return urls[:8]  # 限制最多8個
            
            return []
            
        except Exception as e:
            logger.error(f"動態URL獲取失敗: {e}")
            return []
    
    def _analyze_content_gaps(self, pages: List[PageInfo], objective: TaskObjective) -> str:
        """分析內容缺口"""
        if not pages:
            return "無現有內容可分析"
        
        # 統計關鍵字覆蓋情況
        keyword_coverage = {}
        for keyword in objective.keywords:
            coverage_count = 0
            for page in pages:
                content_text = f"{page.title} {page.summary} {page.content[:500]}".lower()
                if keyword.lower() in content_text:
                    coverage_count += 1
            keyword_coverage[keyword] = coverage_count / len(pages)
        
        # 找出覆蓋不足的關鍵字
        low_coverage_keywords = [k for k, v in keyword_coverage.items() if v < 0.3]
        
        # 分析幫助度分佈
        helpful_count = sum(1 for p in pages if getattr(p, 'is_helpful', False))
        helpful_ratio = helpful_count / len(pages) if pages else 0
        
        analysis = f"""
當前內容分析：
- 總頁面數: {len(pages)}
- 有幫助頁面比例: {helpful_ratio:.1%}
- 關鍵字覆蓋不足: {', '.join(low_coverage_keywords) if low_coverage_keywords else '無'}
- 平均相關度: {sum(p.relevance_score for p in pages) / len(pages):.2f}
        
建議補強方向：
1. 增加專業深度分析內容
2. 尋找更多權威數據來源  
3. 補充缺失關鍵字相關內容
"""
        return analysis.strip()
    
    def _generate_helpfulness_stats(self, pages: List[PageInfo]) -> Dict[str, Any]:
        """生成幫助度統計信息"""
        if not pages:
            return {}
        
        helpful_count = sum(1 for p in pages if getattr(p, 'is_helpful', False))
        total_count = len(pages)
        avg_helpfulness = sum(getattr(p, 'helpfulness_score', 0.0) for p in pages) / total_count
        
        return {
            'total_pages': total_count,
            'helpful_pages': helpful_count,
            'unhelpful_pages': total_count - helpful_count,
            'helpfulness_ratio': helpful_count / total_count,
            'avg_helpfulness_score': avg_helpfulness,
            'helpful_pages_by_depth': self._count_helpful_by_depth(pages)
        }
    
    def _count_helpful_by_depth(self, pages: List[PageInfo]) -> Dict[int, int]:
        """統計各深度的有幫助頁面數量"""
        depth_counts = {}
        for page in pages:
            depth = page.depth
            if depth not in depth_counts:
                depth_counts[depth] = 0
            if getattr(page, 'is_helpful', False):
                depth_counts[depth] += 1
        return depth_counts

    async def generate_consolidated_report(self, jsonl_file: str, output_file: Optional[str] = None) -> str:
        """從JSONL檔案生成統整報表"""
        try:
            if not os.path.exists(jsonl_file):
                raise FileNotFoundError(f"JSONL檔案不存在: {jsonl_file}")
            
            # 讀取JSONL資料
            crawl_data = []
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        crawl_data.append(data)
                    except json.JSONDecodeError:
                        continue
            
            if not crawl_data:
                logger.warning("JSONL檔案中沒有有效資料")
                return ""
            
            # 生成報表內容
            report = await self._create_markdown_report(crawl_data)
            
            # 儲存報表
            if output_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"crawl_report_{timestamp}.md"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            logger.info(f"統整報表已生成: {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"生成統整報表失敗: {e}")
            return ""
    
    async def _create_markdown_report(self, crawl_data: List[Dict]) -> str:
        """創建Markdown格式的統整報表"""
        # 分析資料
        total_pages = len(crawl_data)
        helpful_pages = [item for item in crawl_data if item.get('is_helpful', False)]
        avg_confidence = sum(item.get('relevance_score', 0) for item in crawl_data) / total_pages if total_pages > 0 else 0
        
        # 統計資料
        domains = {}
        depths = {}
        keywords_coverage = {}
        
        for item in crawl_data:
            # 域名統計
            domain = urlparse(item.get('url', '')).netloc
            domains[domain] = domains.get(domain, 0) + 1
            
            # 深度統計
            depth = item.get('depth', 0)
            depths[depth] = depths.get(depth, 0) + 1
            
            # 關鍵字覆蓋統計
            content = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            for keyword in item.get('keywords', []):
                if keyword.lower() in content:
                    keywords_coverage[keyword] = keywords_coverage.get(keyword, 0) + 1
        
        # 找出最有價值的頁面
        valuable_pages = sorted(helpful_pages, 
                              key=lambda x: x.get('relevance_score', 0), 
                              reverse=True)[:10]
        
        # 建立報表
        report = f"""# 爬蟲任務統整報表

## 📊 執行摘要

- **爬取時間**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **總頁面數**: {total_pages}
- **有幫助頁面**: {len(helpful_pages)} ({len(helpful_pages)/total_pages*100:.1f}%)
- **平均相關度**: {avg_confidence:.2f}
- **任務信心度**: {max(item.get('relevance_score', 0) for item in crawl_data)*100:.1f}%

## 🎯 任務資訊

"""
        
        # 添加任務詳情
        if crawl_data:
            first_item = crawl_data[0]
            if 'task_title' in first_item:
                report += f"**任務標題**: {first_item['task_title']}\n\n"
            if 'task_description' in first_item:
                report += f"**任務描述**: {first_item['task_description']}\n\n"
            if 'keywords' in first_item:
                report += f"**關鍵字**: {', '.join(first_item['keywords'])}\n\n"
        
        # 網站分佈統計
        report += "## 🌐 來源網站分佈\n\n"
        sorted_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)
        for domain, count in sorted_domains[:10]:
            percentage = count / total_pages * 100
            report += f"- **{domain}**: {count} 頁 ({percentage:.1f}%)\n"
        
        # 深度分佈
        report += "\n## 📊 爬取深度分佈\n\n"
        sorted_depths = sorted(depths.items())
        for depth, count in sorted_depths:
            percentage = count / total_pages * 100
            report += f"- **第 {depth} 層**: {count} 頁 ({percentage:.1f}%)\n"
        
        # 關鍵字覆蓋
        report += "\n## 🔍 關鍵字覆蓋分析\n\n"
        sorted_keywords = sorted(keywords_coverage.items(), key=lambda x: x[1], reverse=True)
        for keyword, count in sorted_keywords:
            coverage = count / total_pages * 100
            report += f"- **{keyword}**: {count} 頁覆蓋 ({coverage:.1f}%)\n"
        
        # 最有價值的內容
        report += "\n## ⭐ 最有價值的內容\n\n"
        for i, page in enumerate(valuable_pages, 1):
            report += f"### {i}. {page.get('title', '無標題')}\n\n"
            report += f"**URL**: {page.get('url', '')}\n\n"
            report += f"**相關度**: {page.get('relevance_score', 0):.2f}\n\n"
            report += f"**摘要**: {page.get('summary', '無摘要')}\n\n"
            if page.get('found_via'):
                report += f"**發現方式**: {page.get('found_via')}\n\n"
            report += "---\n\n"
        
        # 改進建議
        report += "## 💡 內容分析與建議\n\n"
        
        # 分析覆蓋不足的關鍵字
        low_coverage_keywords = [k for k, v in keywords_coverage.items() if v < total_pages * 0.3]
        if low_coverage_keywords:
            report += f"**覆蓋不足的關鍵字**: {', '.join(low_coverage_keywords)}\n\n"
        
        # 分析幫助度分佈
        if len(helpful_pages) < total_pages * 0.5:
            report += "**建議**: 當前有幫助的內容比例較低，建議調整搜索策略或關鍵字。\n\n"
        
        # 分析深度效率
        deep_pages = [item for item in crawl_data if item.get('depth', 0) > 2]
        if deep_pages:
            deep_helpful = [item for item in deep_pages if item.get('is_helpful', False)]
            deep_efficiency = len(deep_helpful) / len(deep_pages) if deep_pages else 0
            report += f"**深度爬取效率**: 深層頁面有幫助比例為 {deep_efficiency*100:.1f}%\n\n"
        
        # 資料品質評估
        report += "## 📈 資料品質評估\n\n"
        quality_score = self._calculate_quality_score(crawl_data)
        report += f"**整體品質分數**: {quality_score:.1f}/10\n\n"
        
        # 詳細資料統計
        report += "## 📋 詳細統計資料\n\n"
        report += f"- 成功爬取頁面: {len([item for item in crawl_data if item.get('success', True)])}\n"
        report += f"- 失敗頁面: {len([item for item in crawl_data if not item.get('success', True)])}\n"
        
        # 計算包含關鍵字的頁面
        keyword_pages = 0
        for item in crawl_data:
            content_text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
            keywords = item.get('keywords', [])
            if any(kw.lower() in content_text for kw in keywords):
                keyword_pages += 1
        
        report += f"- 包含關鍵字的頁面: {keyword_pages}\n"
        report += f"- 最大爬取深度: {max(item.get('depth', 0) for item in crawl_data)}\n"
        report += f"- 平均頁面內容長度: {sum(len(str(item.get('content', ''))) for item in crawl_data) // total_pages} 字元\n"
        
        # 添加生成時間戳
        report += f"\n---\n*報表生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
        
        return report
    
    def _calculate_quality_score(self, crawl_data: List[Dict]) -> float:
        """計算資料品質分數 (0-10)"""
        if not crawl_data:
            return 0.0
        
        score = 0.0
        total_pages = len(crawl_data)
        
        # 成功率 (0-2分)
        success_rate = len([item for item in crawl_data if item.get('success', True)]) / total_pages
        score += success_rate * 2
        
        # 幫助度比例 (0-3分)
        helpful_rate = len([item for item in crawl_data if item.get('is_helpful', False)]) / total_pages
        score += helpful_rate * 3
        
        # 平均相關度 (0-3分)
        avg_relevance = sum(item.get('relevance_score', 0) for item in crawl_data) / total_pages
        score += avg_relevance * 3
        
        # 內容完整性 (0-2分)
        complete_content = len([item for item in crawl_data if item.get('summary') and len(str(item.get('summary', ''))) > 50]) / total_pages
        score += complete_content * 2
        
        return min(score, 10.0)

    return result

# 新增輔助函數用於報表生成
async def generate_report_from_jsonl(jsonl_file: str, output_file: Optional[str] = None) -> str:
    """從JSONL檔案生成報表的獨立函數"""
    try:
        from datetime import datetime
        import os
        import json
        from urllib.parse import urlparse
        
        if not os.path.exists(jsonl_file):
            raise FileNotFoundError(f"JSONL檔案不存在: {jsonl_file}")
        
        # 讀取JSONL資料
        crawl_data = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    crawl_data.append(data)
                except json.JSONDecodeError:
                    continue
        
        if not crawl_data:
            logger.warning("JSONL檔案中沒有有效資料")
            return ""
        
        # 直接調用報表生成邏輯
        report = _create_markdown_report_standalone(crawl_data)
        
        # 儲存報表
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"crawl_report_{timestamp}.md"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"統整報表已生成: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"生成統整報表失敗: {e}")
        return ""

def _create_markdown_report_standalone(crawl_data: List[Dict]) -> str:
    """創建Markdown格式的統整報表（獨立函數版本）"""
    from datetime import datetime
    from urllib.parse import urlparse
    
    # 分析資料
    total_pages = len(crawl_data)
    helpful_pages = [item for item in crawl_data if item.get('is_helpful', False)]
    avg_confidence = sum(item.get('relevance_score', 0) for item in crawl_data) / total_pages if total_pages > 0 else 0
    
    # 統計資料
    domains = {}
    depths = {}
    keywords_coverage = {}
    
    for item in crawl_data:
        # 域名統計
        domain = urlparse(item.get('url', '')).netloc
        domains[domain] = domains.get(domain, 0) + 1
        
        # 深度統計
        depth = item.get('depth', 0)
        depths[depth] = depths.get(depth, 0) + 1
        
        # 關鍵字覆蓋統計
        content = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        for keyword in item.get('keywords', []):
            if keyword.lower() in content:
                keywords_coverage[keyword] = keywords_coverage.get(keyword, 0) + 1
    
    # 找出最有價值的頁面
    valuable_pages = sorted(helpful_pages, 
                          key=lambda x: x.get('relevance_score', 0), 
                          reverse=True)[:10]
    
    # 建立報表
    report = f"""# 爬蟲任務統整報表

## 📊 執行摘要

- **爬取時間**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **總頁面數**: {total_pages}
- **有幫助頁面**: {len(helpful_pages)} ({len(helpful_pages)/total_pages*100:.1f}%)
- **平均相關度**: {avg_confidence:.2f}
- **任務信心度**: {max(item.get('relevance_score', 0) for item in crawl_data)*100:.1f}%

## 🎯 任務資訊

"""
    
    # 添加任務詳情
    if crawl_data:
        first_item = crawl_data[0]
        if 'task_title' in first_item:
            report += f"**任務標題**: {first_item['task_title']}\n\n"
        if 'task_description' in first_item:
            report += f"**任務描述**: {first_item['task_description']}\n\n"
        if 'keywords' in first_item:
            report += f"**關鍵字**: {', '.join(first_item['keywords'])}\n\n"
    
    # 網站分佈統計
    report += "## 🌐 來源網站分佈\n\n"
    sorted_domains = sorted(domains.items(), key=lambda x: x[1], reverse=True)
    for domain, count in sorted_domains[:10]:
        percentage = count / total_pages * 100
        report += f"- **{domain}**: {count} 頁 ({percentage:.1f}%)\n"
    
    # 深度分佈
    report += "\n## 📊 爬取深度分佈\n\n"
    sorted_depths = sorted(depths.items())
    for depth, count in sorted_depths:
        percentage = count / total_pages * 100
        report += f"- **第 {depth} 層**: {count} 頁 ({percentage:.1f}%)\n"
    
    # 關鍵字覆蓋
    report += "\n## 🔍 關鍵字覆蓋分析\n\n"
    sorted_keywords = sorted(keywords_coverage.items(), key=lambda x: x[1], reverse=True)
    for keyword, count in sorted_keywords:
        coverage = count / total_pages * 100
        report += f"- **{keyword}**: {count} 頁覆蓋 ({coverage:.1f}%)\n"
    
    # 最有價值的內容
    report += "\n## ⭐ 最有價值的內容\n\n"
    for i, page in enumerate(valuable_pages, 1):
        report += f"### {i}. {page.get('title', '無標題')}\n\n"
        report += f"**URL**: {page.get('url', '')}\n\n"
        report += f"**相關度**: {page.get('relevance_score', 0):.2f}\n\n"
        report += f"**摘要**: {page.get('summary', '無摘要')}\n\n"
        if page.get('found_via'):
            report += f"**發現方式**: {page.get('found_via')}\n\n"
        report += "---\n\n"
    
    # 改進建議
    report += "## 💡 內容分析與建議\n\n"
    
    # 分析覆蓋不足的關鍵字
    low_coverage_keywords = [k for k, v in keywords_coverage.items() if v < total_pages * 0.3]
    if low_coverage_keywords:
        report += f"**覆蓋不足的關鍵字**: {', '.join(low_coverage_keywords)}\n\n"
    
    # 分析幫助度分佈
    if len(helpful_pages) < total_pages * 0.5:
        report += "**建議**: 當前有幫助的內容比例較低，建議調整搜索策略或關鍵字。\n\n"
    
    # 分析深度效率
    deep_pages = [item for item in crawl_data if item.get('depth', 0) > 2]
    if deep_pages:
        deep_helpful = [item for item in deep_pages if item.get('is_helpful', False)]
        deep_efficiency = len(deep_helpful) / len(deep_pages) if deep_pages else 0
        report += f"**深度爬取效率**: 深層頁面有幫助比例為 {deep_efficiency*100:.1f}%\n\n"
    
    # 資料品質評估
    report += "## 📈 資料品質評估\n\n"
    quality_score = _calculate_quality_score_standalone(crawl_data)
    report += f"**整體品質分數**: {quality_score:.1f}/10\n\n"
    
    # 詳細資料統計
    report += "## 📋 詳細統計資料\n\n"
    report += f"- 成功爬取頁面: {len([item for item in crawl_data if item.get('success', True)])}\n"
    report += f"- 失敗頁面: {len([item for item in crawl_data if not item.get('success', True)])}\n"
    
    # 計算包含關鍵字的頁面
    keyword_pages = 0
    for item in crawl_data:
        content_text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        keywords = item.get('keywords', [])
        if any(kw.lower() in content_text for kw in keywords):
            keyword_pages += 1
    
    report += f"- 包含關鍵字的頁面: {keyword_pages}\n"
    report += f"- 最大爬取深度: {max(item.get('depth', 0) for item in crawl_data)}\n"
    report += f"- 平均頁面內容長度: {sum(len(str(item.get('content', ''))) for item in crawl_data) // total_pages} 字元\n"
    
    # 添加生成時間戳
    report += f"\n---\n*報表生成時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n"
    
    return report

def _calculate_quality_score_standalone(crawl_data: List[Dict]) -> float:
    """計算資料品質分數 (0-10)（獨立函數版本）"""
    if not crawl_data:
        return 0.0
    
    score = 0.0
    total_pages = len(crawl_data)
    
    # 成功率 (0-2分)
    success_rate = len([item for item in crawl_data if item.get('success', True)]) / total_pages
    score += success_rate * 2
    
    # 幫助度比例 (0-3分)
    helpful_rate = len([item for item in crawl_data if item.get('is_helpful', False)]) / total_pages
    score += helpful_rate * 3
    
    # 平均相關度 (0-3分)
    avg_relevance = sum(item.get('relevance_score', 0) for item in crawl_data) / total_pages
    score += avg_relevance * 3
    
    # 內容完整性 (0-2分)
    complete_content = len([item for item in crawl_data if item.get('summary') and len(str(item.get('summary', ''))) > 50]) / total_pages
    score += complete_content * 2
    
    return min(score, 10.0)

if __name__ == "__main__":
    # 運行範例 - 演示所有新功能
    async def main():
        # 建立基本LLM配置
        from crawl4ai import LLMConfig
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1",
            api_token="sk-test-token"
        )
        
        # 示例1：台灣本土任務（展示地理本地化功能）
        print("=== 示例1：台灣本土任務（地理本地化） ===")
        try:
            taiwan_task = await quick_crawl_task(
                title="台灣半導體產業發展現況",
                description="分析台灣半導體產業的最新發展趨勢、政策支持和國際競爭力",
                keywords=["台積電", "聯發科", "半導體", "台灣", "晶圓"],
                llm_config=llm_config,
                max_search_depth=3,
                enable_dynamic_search=True,
                search_strictness="moderate"
            )
            print(f"台灣任務完成：{taiwan_task.status}，信心度：{taiwan_task.confidence_score:.2%}")
        except Exception as e:
            print(f"台灣任務示例失敗：{e}")
        
        # 示例2：動態搜索示例
        print("\n=== 示例2：動態互動搜索 ===")
        try:
            dynamic_task = await quick_crawl_task(
                title="AI法規監管政策研究",
                description="研究各國AI人工智慧法規監管政策和實施情況",
                keywords=["AI法規", "人工智慧監管", "GDPR", "算法透明度"],
                llm_config=llm_config,
                max_search_depth=5,
                enable_dynamic_search=True,
                search_strictness="strict"
            )
            print(f"動態搜索任務完成：{dynamic_task.status}，信心度：{dynamic_task.confidence_score:.2%}")
        except Exception as e:
            print(f"動態搜索示例失敗：{e}")
        
        # 示例3：生成統整報表
        print("\n=== 示例3：生成統整報表 ===")
        # 假設已有JSONL檔案，生成報表
        try:
            report_file = await generate_report_from_jsonl("task_results.jsonl")
            if report_file:
                print(f"報表生成成功：{report_file}")
                # 讀取並顯示部分內容
                with open(report_file, 'r', encoding='utf-8') as f:
                    content = f.read()[:500]  # 顯示前500字元
                    print(f"報表預覽：\n{content}...")
            else:
                print("報表生成失敗或JSONL檔案不存在")
        except Exception as e:
            print(f"報表生成示例跳過：{e}")
        
        # 示例4：展示基礎功能（使用原有的nvidia示例）
        print("\n=== 示例4：基礎任務功能 ===")
        try:
            await example_nvidia_analysis()
        except Exception as e:
            print(f"基礎功能示例失敗：{e}")
    
    asyncio.run(main())
