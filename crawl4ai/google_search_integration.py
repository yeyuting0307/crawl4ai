"""
Google Search API 集成模組
提供基於Google Search API的智能搜索功能
"""

import os
import asyncio
import json
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import httpx
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """搜索結果"""
    title: str
    url: str
    snippet: str
    display_url: str
    search_rank: int
    search_query: str
    found_at: datetime = field(default_factory=datetime.now)

@dataclass
class GoogleSearchConfig:
    """Google Search 配置"""
    api_key: str
    search_engine_id: str = "017576662512468239146:omuauf_lfve"  # 預設搜索引擎ID
    max_results_per_query: int = 10
    language: str = "zh-TW"  # 繁體中文
    country: str = "TW"      # 台灣
    safe_search: str = "active"
    timeout: int = 30

class GoogleSearchAPI:
    """Google Search API 包裝器"""
    
    def __init__(self, config: GoogleSearchConfig):
        self.config = config
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        
    async def search(self, query: str, num_results: Optional[int] = None) -> List[SearchResult]:
        """執行搜索查詢"""
        try:
            num_results = num_results or self.config.max_results_per_query
            
            params = {
                'key': self.config.api_key,
                'cx': self.config.search_engine_id,
                'q': query,
                'num': min(num_results, 10),  # Google API最多每次10個結果
                'lr': f'lang_{self.config.language.split("-")[0]}',
                'gl': self.config.country,
                'safe': self.config.safe_search
            }
            
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()
                
                results = []
                if 'items' in data:
                    for i, item in enumerate(data['items'], 1):
                        result = SearchResult(
                            title=item.get('title', ''),
                            url=item.get('link', ''),
                            snippet=item.get('snippet', ''),
                            display_url=item.get('displayLink', ''),
                            search_rank=i,
                            search_query=query
                        )
                        results.append(result)
                
                logger.info(f"Google搜索 '{query}' 返回 {len(results)} 個結果")
                return results
                
        except Exception as e:
            logger.error(f"Google搜索失敗 '{query}': {e}")
            return []
    
    async def batch_search(self, queries: List[str], max_results_per_query: Optional[int] = None) -> Dict[str, List[SearchResult]]:
        """批量搜索多個關鍵字"""
        results = {}
        
        for query in queries:
            try:
                search_results = await self.search(query, max_results_per_query)
                results[query] = search_results
                # 避免過於頻繁的API調用
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"批量搜索失敗 '{query}': {e}")
                results[query] = []
        
        return results

class IntelligentKeywordGenerator:
    """智能關鍵字生成器"""
    
    def __init__(self, llm_config):
        self.llm_config = llm_config
    
    async def generate_initial_keywords(self, title: str, description: str, existing_keywords: Optional[List[str]] = None) -> List[str]:
        """生成初始搜索關鍵字"""
        try:
            existing_kw_text = f"已有關鍵字: {', '.join(existing_keywords)}" if existing_keywords else ""
            
            prompt = f"""你是一個專業的搜索策略專家。根據以下任務資訊，生成5-8個最有效的搜索關鍵字。

任務標題: {title}
任務描述: {description}
{existing_kw_text}

請考慮以下搜索策略：
1. 包含核心概念關鍵字
2. 包含相關的專業術語
3. 包含可能的變體和同義詞
4. 如果與台灣相關，加入地理相關關鍵字
5. 包含時效性關鍵字（如"2024", "最新", "趨勢"等）
6. 避免過於寬泛的關鍵字

請只返回關鍵字列表，每行一個，不要其他說明："""

            response = await self._call_llm_api(prompt)
            if response:
                keywords = [kw.strip() for kw in response.strip().split('\n') if kw.strip()]
                # 過濾掉已存在的關鍵字
                if existing_keywords:
                    keywords = [kw for kw in keywords if kw not in existing_keywords]
                
                logger.info(f"生成了 {len(keywords)} 個新關鍵字")
                return keywords[:8]  # 限制最多8個關鍵字
            
        except Exception as e:
            logger.error(f"生成關鍵字失敗: {e}")
        
        return []
    
    async def refine_keywords_based_on_results(self, 
                                             title: str, 
                                             description: str, 
                                             previous_keywords: List[str],
                                             crawled_results: List[Dict],
                                             current_confidence: float) -> List[str]:
        """根據爬蟲結果優化關鍵字"""
        try:
            # 分析當前結果的品質
            helpful_results = [r for r in crawled_results if r.get('is_helpful', False)]
            coverage_analysis = self._analyze_content_coverage(crawled_results, previous_keywords)
            
            prompt = f"""基於以下資訊，建議3-5個新的搜索關鍵字來改善搜索結果品質：

任務標題: {title}
任務描述: {description}
已使用關鍵字: {', '.join(previous_keywords)}
當前信心度: {current_confidence:.2%}

爬蟲結果分析:
- 總頁面數: {len(crawled_results)}
- 有用頁面數: {len(helpful_results)}
- 內容覆蓋分析: {coverage_analysis}

請分析當前結果的不足之處，並建議新的關鍵字來：
1. 補強缺失的主題面向
2. 提高搜索結果的相關性
3. 獲取更權威的資料來源
4. 找到更新的資訊

請只返回新關鍵字列表，每行一個："""

            response = await self._call_llm_api(prompt)
            if response:
                keywords = [kw.strip() for kw in response.strip().split('\n') if kw.strip()]
                # 確保不重複已有關鍵字
                new_keywords = [kw for kw in keywords if kw not in previous_keywords]
                
                logger.info(f"基於結果分析生成了 {len(new_keywords)} 個優化關鍵字")
                return new_keywords[:5]  # 限制最多5個新關鍵字
            
        except Exception as e:
            logger.error(f"優化關鍵字失敗: {e}")
        
        return []
    
    def _analyze_content_coverage(self, results: List[Dict], keywords: List[str]) -> str:
        """分析內容覆蓋情況"""
        if not results:
            return "無可分析內容"
        
        keyword_coverage = {}
        for keyword in keywords:
            coverage_count = 0
            for result in results:
                content = f"{result.get('title', '')} {result.get('summary', '')}".lower()
                if keyword.lower() in content:
                    coverage_count += 1
            keyword_coverage[keyword] = coverage_count / len(results)
        
        # 找出覆蓋率低的關鍵字
        low_coverage = [k for k, v in keyword_coverage.items() if v < 0.3]
        high_coverage = [k for k, v in keyword_coverage.items() if v > 0.7]
        
        analysis = f"高覆蓋關鍵字: {', '.join(high_coverage) if high_coverage else '無'}, "
        analysis += f"低覆蓋關鍵字: {', '.join(low_coverage) if low_coverage else '無'}"
        
        return analysis
    
    async def _call_llm_api(self, prompt: str) -> Optional[str]:
        """調用LLM API"""
        try:
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
                    data = response.json()
                    return data['choices'][0]['message']['content']
                else:
                    logger.error(f"LLM API調用失敗: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"LLM API調用異常: {e}")
        
        return None

def create_google_search_config_from_env() -> GoogleSearchConfig:
    """從環境變數創建Google Search配置"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("請在.env檔案中設置GOOGLE_API_KEY")
    
    return GoogleSearchConfig(
        api_key=api_key,
        search_engine_id=os.getenv("GOOGLE_SEARCH_ENGINE_ID", "017576662512468239146:omuauf_lfve"),
        max_results_per_query=int(os.getenv("GOOGLE_MAX_RESULTS", "10")),
        language=os.getenv("GOOGLE_LANGUAGE", "zh-TW"),
        country=os.getenv("GOOGLE_COUNTRY", "TW")
    )
