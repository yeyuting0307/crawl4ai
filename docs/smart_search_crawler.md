# 智能搜索爬蟲系統

## 概述

智能搜索爬蟲系統是一個基於Google Search API和Crawl4AI的進階爬蟲解決方案，透過LLM驅動的關鍵字生成和迭代優化，實現高品質的網站內容搜索和分析。

## 系統架構

```
智能搜索爬蟲系統
├── Google Search API 整合
│   ├── 關鍵字搜索
│   ├── 結果篩選
│   └── 批量搜索
├── LLM驅動的關鍵字優化
│   ├── 初始關鍵字生成
│   ├── 基於結果的關鍵字優化
│   └── 迭代式關鍵字擴展
├── 智能爬蟲引擎
│   ├── Crawl4AI整合
│   ├── 內容品質評估
│   └── 相關度分析
└── 報表生成系統
    ├── Markdown報表
    ├── 詳細分析
    └── 改進建議
```

## 主要特色

### 1. LLM驅動的關鍵字生成
- **智能關鍵字推薦**: 基於任務目標自動生成多元化關鍵字
- **動態關鍵字優化**: 根據搜索結果和爬蟲成果迭代優化關鍵字
- **上下文感知**: 考慮任務特性和目標群體特徵

### 2. Google Search API整合
- **高品質搜索結果**: 利用Google自定義搜索API獲取相關網站
- **地區化搜索**: 支援台灣地區優化（zh-TW, TW）
- **批量搜索**: 高效處理多個關鍵字搜索請求

### 3. 迭代式信心度優化
- **信心度追蹤**: 每次迭代評估並追蹤信心度變化
- **自適應停止**: 達到目標信心度時自動停止
- **品質保證**: 確保爬蟲結果符合品質標準

### 4. 智能內容分析
- **相關度評估**: AI驅動的內容相關度分析
- **結構化抽取**: 支援JSON格式結構化資料抽取
- **摘要生成**: 自動生成高品質內容摘要

## 核心模組

### 1. Google Search Integration (`google_search_integration.py`)

```python
from crawl4ai.google_search_integration import GoogleSearchAPI, IntelligentKeywordGenerator

# 初始化Google搜索API
search_api = GoogleSearchAPI(api_key="YOUR_API_KEY", search_engine_id="YOUR_ENGINE_ID")

# 智能關鍵字生成
keyword_gen = IntelligentKeywordGenerator(llm_api_key="YOUR_LLM_KEY")
keywords = await keyword_gen.generate_initial_keywords(
    task_description="研究台灣電商市場趨勢"
)
```

**主要功能**:
- `GoogleSearchAPI`: Google自定義搜索API封裝
- `IntelligentKeywordGenerator`: LLM驅動的關鍵字生成器
- `SearchResult`: 搜索結果資料結構
- `GoogleSearchConfig`: 搜索配置管理

### 2. Smart Search Crawler (`smart_search_crawler.py`)

```python
from crawl4ai.smart_search_crawler import SmartSearchCrawler, TaskObjectiveV3

# 定義任務目標
objective = TaskObjectiveV3(
    title="台灣電商市場分析",
    description="分析台灣電商市場的最新趨勢和發展機會",
    initial_keywords=["台灣電商", "線上購物", "電子商務"],
    target_confidence=0.85,
    max_iterations=3
)

# 執行智能爬蟲
crawler = SmartSearchCrawler(
    google_api_key="YOUR_GOOGLE_API_KEY",
    google_engine_id="YOUR_ENGINE_ID",
    llm_api_key="YOUR_LLM_KEY"
)

result = await crawler.execute_smart_crawl(objective)
```

**主要功能**:
- `SmartSearchCrawler`: 主要爬蟲引擎
- `TaskObjectiveV3`: 任務目標定義
- `IterationResult`: 迭代結果追蹤
- `SmartCrawlResult`: 完整爬蟲結果

### 3. Report Generator (`smart_crawl_report.py`)

```python
from crawl4ai.smart_crawl_report import generate_crawl_report

# 生成詳細報表
report_path = generate_crawl_report(
    result=crawl_result,
    output_dir="reports"
)
print(f"報表已生成: {report_path}")
```

**主要功能**:
- 生成詳細的Markdown格式分析報表
- 包含執行摘要、迭代詳情、品質分析
- 提供改進建議和優化方向

## 使用範例

### 基本使用

```python
import asyncio
from crawl4ai.smart_search_crawler import SmartSearchCrawler, TaskObjectiveV3

async def basic_example():
    # 1. 定義任務目標
    objective = TaskObjectiveV3(
        title="AI技術趨勢研究",
        description="收集和分析2024年人工智能技術的最新發展趨勢",
        initial_keywords=["AI趨勢", "人工智能", "機器學習"],
        target_confidence=0.8,
        max_iterations=2,
        output_format="summary"
    )
    
    # 2. 初始化爬蟲
    crawler = SmartSearchCrawler(
        google_api_key="your_google_api_key",
        google_engine_id="your_search_engine_id", 
        llm_api_key="your_llm_api_key"
    )
    
    # 3. 執行智能爬蟲
    result = await crawler.execute_smart_crawl(objective)
    
    # 4. 生成報表
    from crawl4ai.smart_crawl_report import generate_crawl_report
    report_path = generate_crawl_report(result)
    
    print(f"任務完成！信心度: {result.final_confidence:.2%}")
    print(f"報表位置: {report_path}")

# 執行範例
asyncio.run(basic_example())
```

### 結構化資料抽取

```python
async def structured_data_example():
    objective = TaskObjectiveV3(
        title="台灣新創公司資料收集",
        description="收集台灣新創公司的基本資料，包括公司名稱、領域、資金等",
        initial_keywords=["台灣新創", "startup", "創業公司"],
        output_format="structured",
        structured_schema={
            "company_name": "公司名稱",
            "industry": "產業領域", 
            "funding": "資金狀況",
            "description": "公司描述"
        },
        target_confidence=0.85
    )
    
    crawler = SmartSearchCrawler(
        google_api_key="your_api_key",
        google_engine_id="your_engine_id",
        llm_api_key="your_llm_key"
    )
    
    result = await crawler.execute_smart_crawl(objective)
    
    # 輸出結構化資料
    for item in result.structured_data:
        print(f"公司: {item.get('company_name', 'N/A')}")
        print(f"領域: {item.get('industry', 'N/A')}")
        print(f"資金: {item.get('funding', 'N/A')}")
        print("---")

asyncio.run(structured_data_example())
```

## 配置說明

### 環境變數設定

創建 `.env` 檔案：

```env
# Google Custom Search API
GOOGLE_SEARCH_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id

# LLM API (支援OpenAI相容介面)  
LLM_API_KEY=your_llm_api_key
LLM_BASE_URL=https://api.openai.com/v1  # 可選，預設OpenAI

# 爬蟲設定
DEFAULT_MAX_ITERATIONS=3
DEFAULT_TARGET_CONFIDENCE=0.8
DEFAULT_MAX_PAGES=20
```

### Google Custom Search API設定

1. 前往 [Google Cloud Console](https://console.cloud.google.com/)
2. 啟用 Custom Search API
3. 創建自定義搜索引擎 at [https://cse.google.com/](https://cse.google.com/)
4. 獲取 API Key 和 Search Engine ID

### TaskObjectiveV3 參數說明

| 參數 | 類型 | 說明 | 預設值 |
|------|------|------|--------|
| `title` | str | 任務標題 | 必填 |
| `description` | str | 任務描述 | 必填 |
| `initial_keywords` | List[str] | 初始關鍵字 | 必填 |
| `target_confidence` | float | 目標信心度 (0-1) | 0.8 |
| `max_iterations` | int | 最大迭代次數 | 3 |
| `max_total_pages` | int | 最大總頁面數 | 20 |
| `max_search_results_per_keyword` | int | 每關鍵字最大搜索結果 | 10 |
| `enable_keyword_refinement` | bool | 啟用關鍵字優化 | True |
| `output_format` | str | 輸出格式 ("summary"/"structured") | "summary" |
| `structured_schema` | Dict | 結構化資料架構 | None |
| `time_priority` | bool | 時間優先模式 | False |

## 進階功能

### 1. 自定義LLM配置

```python
# 使用自定義LLM端點
crawler = SmartSearchCrawler(
    google_api_key="your_api_key",
    google_engine_id="your_engine_id",
    llm_api_key="your_llm_key",
    llm_base_url="https://your-custom-llm-endpoint.com/v1"
)
```

### 2. 批量任務處理

```python
async def batch_crawl_example():
    objectives = [
        TaskObjectiveV3(title="AI趨勢", description="...", initial_keywords=["AI"]),
        TaskObjectiveV3(title="區塊鏈", description="...", initial_keywords=["blockchain"]),
        TaskObjectiveV3(title="物聯網", description="...", initial_keywords=["IoT"])
    ]
    
    crawler = SmartSearchCrawler(...)
    
    results = []
    for objective in objectives:
        result = await crawler.execute_smart_crawl(objective)
        results.append(result)
        
        # 生成個別報表
        generate_crawl_report(result, f"reports/{objective.title}")
    
    return results
```

### 3. 性能監控

```python
# 啟用詳細日誌
import logging
logging.basicConfig(level=logging.INFO)

# 監控爬蟲性能
result = await crawler.execute_smart_crawl(objective)

print(f"執行時間: {result.execution_time:.1f}秒")
print(f"總頁面: {result.total_pages_crawled}")
print(f"成功率: {len([p for iter in result.iterations for p in iter.crawled_pages if p.success]) / result.total_pages_crawled:.1%}")
```

## 最佳實踐

### 1. 關鍵字策略
- **多樣性**: 使用不同類型的關鍵字（通用詞、專業詞、長尾詞）
- **階段性**: 初始關鍵字保持簡潔，讓系統自動擴展
- **本地化**: 針對台灣市場使用繁體中文關鍵字

### 2. 信心度設定
- **一般任務**: 0.7-0.8 已足夠
- **高精度要求**: 0.85-0.9
- **快速探索**: 0.6-0.7

### 3. 迭代次數控制
- **簡單任務**: 1-2 次迭代
- **複雜研究**: 3-5 次迭代
- **深度分析**: 5+ 次迭代

### 4. 結構化資料設計
- **欄位明確**: 每個欄位都要有清楚的說明
- **類型一致**: 確保資料類型的一致性
- **容錯設計**: 允許部分欄位為空

## 故障排除

### 常見問題

#### 1. Google API配額不足
```
錯誤: Daily Limit Exceeded
解決: 檢查Google Cloud Console中的API配額設定
```

#### 2. LLM API連接失敗
```python
# 測試LLM連接
from crawl4ai.google_search_integration import IntelligentKeywordGenerator

generator = IntelligentKeywordGenerator(
    llm_api_key="your_key",
    llm_base_url="your_endpoint"  # 確認端點正確
)

# 測試簡單請求
keywords = await generator.generate_initial_keywords("test task")
```

#### 3. 爬蟲成功率低
- 檢查目標網站的反爬蟲機制
- 調整爬蟲延遲設定
- 使用代理伺服器

#### 4. 信心度無法提升
- 增加迭代次數
- 優化初始關鍵字
- 檢查LLM配置

### 日誌分析

啟用詳細日誌以進行問題診斷：

```python
import logging

# 設定日誌級別
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 執行爬蟲並查看詳細日誌
result = await crawler.execute_smart_crawl(objective)
```

## 效能優化

### 1. 並發控制
```python
# 調整並發數量
crawler = SmartSearchCrawler(
    google_api_key="...",
    google_engine_id="...",
    llm_api_key="...",
    max_concurrent_crawls=5  # 調整並發數
)
```

### 2. 快取策略
```python
# 啟用搜索結果快取
objective = TaskObjectiveV3(
    ...,
    enable_cache=True,  # 啟用快取
    cache_duration=3600  # 快取時間（秒）
)
```

### 3. 時間優先模式
```python
# 優先考慮執行時間
objective = TaskObjectiveV3(
    ...,
    time_priority=True,  # 時間優先
    max_execution_time=300  # 最大執行時間（秒）
)
```

## 版本更新

### v1.0.0 (Current)
- ✅ Google Search API整合
- ✅ LLM驅動的關鍵字生成
- ✅ 迭代式信心度優化
- ✅ 智能內容分析
- ✅ Markdown報表生成
- ✅ 結構化資料抽取

### v1.1.0 (計劃中)
- 🔄 多語言支援
- 🔄 視覺化報表
- 🔄 API介面
- 🔄 資料庫整合

## 支援與聯繫

如有問題或建議，請聯繫開發團隊或查看專案文檔。

## 授權

此專案採用MIT授權協議。
