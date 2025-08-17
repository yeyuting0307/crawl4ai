"""
任務驅動、自適應、語意理解型爬蟲系統

主要功能：
1. 自動發現目標網站 (Discovery Layer)
2. 智慧爬蟲 (Crawl Layer) 
3. 語意抽取 (LLM Extraction)
4. 結構化輸出或重點摘要
5. 時間優先度排序
6. 智慧子頁面搜索
7. 內容摘要生成
"""

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
    max_search_depth: int = 3  # 新增：最大搜索深度
    max_search_breadth: int = 10  # 新增：每層最大頁面數
    enable_content_summary: bool = True  # 新增：是否生成內容摘要
    
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
        """智慧爬取網站，包含子頁面搜索和站內搜索"""
        logger.info(f"開始智慧爬取: {base_url}")
        
        pages = []
        queue = [(base_url, 0, "")]  # (url, depth, parent_url)
        
        while queue and len(pages) < objective.max_results:
            current_url, depth, parent_url = queue.pop(0)
            
            # 檢查深度限制
            if depth > objective.max_search_depth:
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
                    pages.append(page_info)
                    
                    # 如果當前頁面相關度高，搜索子頁面
                    if page_info.relevance_score > 0.5 and depth < objective.max_search_depth:
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
        """嘗試站內搜索"""
        search_urls = []
        domain = urlparse(base_url).netloc
        
        # 常見的搜索URL模式
        search_patterns = [
            f"https://{domain}/search?q={{query}}",
            f"https://{domain}/search?query={{query}}",
            f"https://{domain}/?s={{query}}",
            f"https://{domain}/search/?q={{query}}",
        ]
        
        query = "+".join(objective.keywords[:3])  # 使用前3個關鍵字
        
        for pattern in search_patterns:
            try:
                search_url = pattern.format(query=query)
                
                # 簡單檢查搜索頁面是否存在
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.head(search_url)
                    if response.status_code == 200:
                        # 這裡應該解析搜索結果頁面，簡化為返回搜索URL
                        search_urls.append(search_url)
                        break  # 找到一個可用的搜索就夠了
                        
            except Exception:
                continue
        
        return search_urls
    
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
    
    async def _generate_content_summary(self, content: str, objective: TaskObjective) -> str:
        """生成內容摘要"""
        if not content or len(content.strip()) < 100:
            return "內容過短，無法生成摘要"
        
        try:
            # 限制內容長度以避免token限制
            content_snippet = content[:2000]
            
            summary = await self._call_llm_for_summary(content_snippet, objective)
            if summary:
                return summary
            
        except Exception as e:
            logger.error(f"生成摘要失敗: {e}")
        
        # fallback: 簡單摘要
        sentences = content.split('.')[:3]  # 取前3句
        return '. '.join(sentences)[:200] + "..."
    
    async def _call_llm_for_summary(self, content: str, objective: TaskObjective) -> Optional[str]:
        """調用LLM生成摘要"""
        try:
            # 檢測是否使用本地LLM
            base_url = self.llm_config.base_url or ""
            is_local_llm = "localhost" in base_url or "127.0.0.1" in base_url
            
            if is_local_llm:
                # 使用本地LLM的 chat/completions API
                return await self._call_local_llm_chat(content, objective)
            else:
                # 使用雲端LLM
                return await self._call_cloud_llm(content, objective)
                
        except Exception as e:
            logger.error(f"LLM調用失敗: {e}")
            return None
    
    async def _call_local_llm_chat(self, content: str, objective: TaskObjective) -> Optional[str]:
        """調用本地LLM的chat API"""
        try:
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
    
    async def _call_cloud_llm(self, content: str, objective: TaskObjective) -> Optional[str]:
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
        
        # 生成搜尋策略
        search_queries = await self._generate_search_queries(objective)
        
        # 模擬搜尋結果（實際實作應該調用搜尋 API）
        candidate_urls = await self._simulate_search(search_queries)
        
        # 過濾和評分
        filtered_urls = self._filter_and_score_urls(candidate_urls, objective)
        
        logger.info(f"發現 {len(filtered_urls)} 個候選網站")
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
            "https://www.bloomberg.com/markets/stocks",
            "https://seekingalpha.com/",
            "https://www.marketwatch.com/investing/stock",
            "https://www.fool.com/investing/",
            "https://www.cnbc.com/markets/",
            "https://www.reuters.com/markets/",
            "https://www.morningstar.com/stocks",
            "https://www.zacks.com/stocks",
            "https://stockanalysis.com/",
            "https://www.investing.com/",
            "https://tw.stock.yahoo.com/"  # 台灣股市
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
        output_dir: str = "./crawl_results"
    ) -> TaskResult:
        """執行完整的任務驅動爬取流程"""
        
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        result = TaskResult(task_id=task_id, objective=objective)
        
        try:
            logger.info(f"開始執行任務: {objective.title}")
            result.status = "running"
            
            # 階段一：站點發現
            logger.info("=== 階段一：站點發現 ===")
            discovered_urls = await self.discovery_engine.discover_sites(objective)
            result.discovered_urls = discovered_urls
            
            # 合併手動追加的 URL
            all_urls = discovered_urls.copy()
            if additional_urls:
                valid_additional = [url for url in additional_urls if self._is_valid_url(url)]
                all_urls.extend(valid_additional)
                all_urls = list(set(all_urls))  # 去重
            
            logger.info(f"總共 {len(all_urls)} 個種子 URL")
            
            # 階段二：智慧爬取（新版本）
            logger.info("=== 階段二：智慧爬取 ===")
            all_pages = await self._smart_crawl_phase(all_urls, objective)
            result.crawled_pages = len(all_pages)
            
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
                        "found_via": page.found_via
                    }
                    for page in all_pages
                ]
            
            # 階段三：語意抽取
            logger.info("=== 階段三：語意抽取 ===")
            if objective.output_format == "structured":
                extracted_data = await self._extract_structured_data_from_pages(all_pages, objective)
                result.extracted_data = extracted_data
            else:
                summary = await self._generate_summary_from_pages(all_pages, objective)
                result.summary = summary
            
            # 計算信心度（考慮時間和深度）
            result.confidence_score = self._calculate_enhanced_confidence(all_pages, objective)
            
            # 統計信息
            result.search_stats = self._generate_search_stats(all_pages)
            
            result.status = "completed"
            result.end_time = datetime.now()
            result.execution_time = (result.end_time - result.start_time).total_seconds()
            
            # 保存結果
            await self._save_results(result, output_dir)
            
            logger.info(f"任務完成！爬取 {result.crawled_pages} 個頁面，信心度: {result.confidence_score:.2%}")
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
        """使用增強的LLM抽取結構化資料"""
        
        # 構建更詳細的提示
        prompt = f"""
        從以下內容中抽取與 "{objective.title}" 相關的結構化資訊：

        任務描述: {objective.description}
        關鍵字: {', '.join(objective.keywords)}
        
        頁面資訊:
        標題: {page.title}
        URL: {page.url}
        發布時間: {page.publish_date.strftime('%Y-%m-%d') if page.publish_date else '未知'}
        頁面摘要: {page.summary}
        
        內容:
        {page.content[:3000]}

        請抽取以下資訊並以 JSON 格式返回：
        {{
            "title": "主題或標題",
            "date": "日期（如果有）",
            "key_points": ["關鍵要點1", "關鍵要點2"],
            "data_points": ["重要數據1", "重要數據2"],
            "predictions": ["預測或觀點1", "預測或觀點2"],
            "sentiment": "positive/negative/neutral",
            "confidence": 0.8,
            "time_relevance": "新聞時效性評估",
            "source_credibility": "來源可信度評估"
        }}

        只返回 JSON，不要其他文字。
        """
        
        try:
            # 使用智慧搜索引擎的LLM調用功能
            response_text = await self.smart_search_engine._call_llm_for_summary(prompt, objective)
            
            if response_text:
                # 清理響應並嘗試解析 JSON
                clean_response = response_text.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                
                try:
                    return json.loads(clean_response.strip())
                except json.JSONDecodeError:
                    # 如果JSON解析失敗，嘗試修復常見問題
                    clean_response = re.sub(r',\s*}', '}', clean_response)
                    clean_response = re.sub(r',\s*]', ']', clean_response)
                    return json.loads(clean_response.strip())
            
        except Exception as e:
            logger.error(f"增強LLM抽取失敗: {e}")
            return None
        
        return None
    
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
    max_search_depth: int = 3,
    max_search_breadth: int = 10,
    enable_content_summary: bool = True
) -> TaskResult:
    """快速執行爬取任務"""
    
    objective = TaskObjective(
        title=title,
        description=description,
        keywords=keywords or [],
        output_format=output_format,
        time_priority=time_priority,
        max_search_depth=max_search_depth,
        max_search_breadth=max_search_breadth,
        enable_content_summary=enable_content_summary
    )
    
    crawler = await create_task_crawler(llm_config)
    return await crawler.execute_task(objective, additional_urls, output_dir)

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
    
    return result

if __name__ == "__main__":
    # 運行範例
    asyncio.run(example_nvidia_analysis())
