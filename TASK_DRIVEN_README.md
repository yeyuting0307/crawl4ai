# 任務驅動、自適應、語意理解型爬蟲系統

## 🚀 系統簡介

這是一個基於 Crawl4AI 的全新任務驅動爬蟲系統，具備以下核心能力：

### 🎯 核心功能

1. **自動站點發現** (Discovery Layer)
   - 根據任務目標自動搜尋相關網站
   - LLM 驅動的搜尋策略生成
   - 智慧過濾和網站評分

2. **智慧爬蟲** (Crawl Layer)
   - 使用 AdaptiveCrawler 自動判斷爬取深度
   - BestFirstCrawlingStrategy + 關鍵字評分
   - 語意理解導向的頁面選擇

3. **語意抽取** (LLM Extraction)
   - 本地 HuggingFace 模型支援
   - 結構化資料抽取
   - 自然語言摘要生成

4. **靈活配置**
   - 支援手動追加 URL
   - 可自定義抽取 Schema
   - 多種輸出格式

## 📋 應用場景

### ✅ 金融資訊分析
```bash
# NVIDIA 股價預測分析
crwl task --title "NVIDIA 股價預測分析" \
          --description "收集專家預測、財務分析和市場觀點" \
          --keywords "NVDA,股價,預測,AI晶片" \
          --output-format structured
```

### ✅ 產業研究
```bash
# AI 產業趨勢研究
crwl task --title "AI 半導體產業趨勢" \
          --description "研究 AI 半導體市場趨勢和發展" \
          --keywords "AI,半導體,市場趨勢" \
          --output-format summary
```

### ✅ 品牌監測
```bash
# Tesla 品牌聲量監測
crwl task --title "Tesla 品牌聲量監測" \
          --description "監測 Tesla 在媒體的報導和反應" \
          --keywords "Tesla,電動車,馬斯克" \
          --additional-urls "https://tesla.com,https://ir.tesla.com"
```

### ✅ 學術文獻追蹤
```bash
# 量子計算研究追蹤
crwl task --title "量子計算研究進展" \
          --description "追蹤量子計算領域最新研究成果" \
          --keywords "量子計算,qubit,quantum" \
          --output-format summary
```

## 🛠️ 安裝和配置

### 1. 系統要求
- Python 3.8+
- Crawl4AI 環境
- 本地 LLM 服務（可選）

### 2. 本地 LLM 配置

系統支援您的本地 HuggingFace 模型：
```
模型路徑: /Users/mike/.cache/huggingface/hub/models--InferenceIllusionist--gpt-oss-20b-MLX-4bit
```

#### 啟動本地 LLM 服務
```bash
# 使用 vllm 或其他 OpenAI 相容服務
# 範例配置：
# 服務地址: http://127.0.0.1:8080/v1
# API Token: local-mlx
# 模型名稱: gpt-oss-20b-mlx-4bit
```

### 3. 快速開始

#### 使用 CLI
```bash
# 基本使用
crwl task --title "您的任務標題" \
          --description "任務描述" \
          --keywords "關鍵字1,關鍵字2"

# 查看更多範例
crwl task-example
```

#### 使用 Python API
```python
import asyncio
from crawl4ai import quick_crawl_task, LLMConfig

async def main():
    # 配置 LLM
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx"
    )
    
    # 執行任務
    result = await quick_crawl_task(
        title="NVIDIA 股價分析",
        description="收集 NVIDIA 股價預測和分析",
        llm_config=llm_config,
        keywords=["NVDA", "股價", "預測"],
        output_format="structured"
    )
    
    print(f"爬取頁面: {result.crawled_pages}")
    print(f"信心度: {result.confidence_score:.2%}")

asyncio.run(main())
```

## 📊 輸出格式

### 結構化資料 (structured)
```json
{
  "source_url": "https://example.com",
  "extracted_at": "2025-01-17T10:30:00",
  "data": {
    "title": "NVIDIA Q4 財報分析",
    "date": "2025-01-15",
    "key_points": ["營收成長 25%", "AI 晶片需求強勁"],
    "data_points": ["股價目標 $150", "EPS 預估 $2.5"],
    "predictions": ["2025年持續上漲"],
    "sentiment": "positive",
    "confidence": 0.85
  }
}
```

### 摘要報告 (summary)
```markdown
# NVIDIA 股價分析 2025

## 執行摘要
基於爬取的內容分析，NVIDIA 股價顯示出積極的市場趨勢...

## 關鍵發現
- AI 晶片需求持續增長
- 資料中心業務表現強勁
- 遊戲市場穩定復甦

## 重要觀點和預測
- 短期內預計穩定增長
- 長期前景樂觀
- 主要風險來自市場波動

## 結論和建議
綜合分析顯示積極信號...
```

## 🎛️ 高級配置

### 自定義任務目標
```python
from crawl4ai import TaskObjective, TaskDrivenCrawler

objective = TaskObjective(
    title="品牌監測任務",
    description="監測品牌在網路上的聲量",
    keywords=["品牌名稱", "產品"],
    target_domains=["news.com", "finance.com"],  # 指定域名
    exclude_domains=["spam.com"],  # 排除域名
    output_format="structured",
    schema={  # 自定義 schema
        "type": "object",
        "properties": {
            "headline": {"type": "string"},
            "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"]},
            "impact_score": {"type": "number"}
        }
    },
    max_results=50
)

crawler = TaskDrivenCrawler(llm_config)
result = await crawler.execute_task(objective)
```

### 配置選項
```python
from crawl4ai import DiscoveryConfig, AdaptiveConfig

# 站點發現配置
discovery_config = DiscoveryConfig(
    search_engines=["google", "bing"],
    max_sites_per_engine=10,
    enable_domain_filter=True,
    enable_content_type_filter=True
)

# 自適應爬取配置
adaptive_config = AdaptiveConfig(
    strategy="embedding",  # 使用語意策略
    max_pages=20,
    confidence_threshold=0.7,
    embedding_model="sentence-transformers/all-MiniLM-L6-v2"
)
```

## 📈 系統架構

```
任務輸入 → 站點發現 → 智慧爬取 → 語意抽取 → 結果輸出
    ↓           ↓           ↓           ↓           ↓
 任務目標    候選網站    網頁內容    結構化資料    JSON/摘要
 關鍵字      自動過濾    自適應深度   LLM 理解     儲存檔案
 額外 URL    域名評分    語意相關    Schema 抽取   結果展示
```

### 資料流程
1. **Discovery 層** → 根據任務目標產生關鍵字 → 搜尋 API → 候選網址
2. **Crawl 層** → AdaptiveCrawler → BestFirstStrategy → 關鍵頁面
3. **Extraction 層** → LLM 分析 → Schema 抽取 → 結構化輸出

## 🔧 故障排除

### 常見問題

#### 1. LLM 連接失敗
```bash
# 檢查 LLM 服務是否運行
curl http://127.0.0.1:8080/v1/models

# 檢查配置
crwl task --llm-base-url "http://localhost:8080/v1" --verbose
```

#### 2. 網站發現結果少
- 調整關鍵字組合
- 檢查 `target_domains` 設定
- 增加 `max_sites_per_engine`

#### 3. 爬取信心度低
- 增加 `max_pages` 設定
- 調整 `confidence_threshold`
- 檢查關鍵字相關性

#### 4. 抽取結果品質差
- 優化任務描述
- 調整自定義 Schema
- 檢查 LLM 模型性能

### 除錯模式
```bash
# 啟用詳細輸出
crwl task --title "測試任務" --description "測試" --verbose

# 檢查中間結果
ls ./crawl_results/  # 查看輸出檔案
```

## 📁 輸出檔案結構

```
crawl_results/
├── task_20250117_143022_final.json      # 完整任務結果
├── task_20250117_143022_data.jsonl      # 結構化資料 (每行一個 JSON)
├── task_20250117_143022_summary.md      # 摘要報告
└── task_20250117_143022_discovery.json  # 中間結果 (可選)
```

## 🎯 最佳實踐

### 任務設計
1. **明確的任務標題** - 簡潔但具體描述目標
2. **詳細的任務描述** - 提供足夠上下文
3. **精準的關鍵字** - 使用領域相關術語
4. **合適的輸出格式** - 結構化資料用於後續分析，摘要用於人閱讀

### 效能優化
1. **限制爬取範圍** - 使用 `target_domains` 和 `max_pages`
2. **增量處理** - 分批處理大型任務
3. **快取利用** - 重複任務會利用快取
4. **並行處理** - 系統自動並行爬取多個 URL

### 資料品質
1. **Schema 設計** - 根據需求設計合適的資料結構
2. **關鍵字組合** - 使用同義詞和相關術語
3. **來源多樣性** - 添加權威網站到 `additional_urls`
4. **結果驗證** - 檢查信心度和資料完整性

## 🤝 貢獻和支援

### 開發指南
```bash
# 開發環境設定
git clone <repository>
cd crawl4ai
pip install -e .

# 運行測試
python examples/task_driven_examples.py
```

### 問題回報
如遇到問題，請提供：
- 任務配置
- 錯誤訊息
- 系統環境資訊
- 重現步驟

## 📚 延伸閱讀

- [Crawl4AI 文檔](https://crawl4ai.com/docs)
- [自適應爬蟲原理](docs/adaptive_crawling.md)
- [LLM 整合指南](docs/llm_integration.md)
- [Schema 設計最佳實踐](docs/schema_design.md)

---

**🎉 享受智慧爬蟲的強大功能！**

這個系統將傳統爬蟲、AI 語意理解和任務導向結合，為您提供前所未有的網路資訊收集體驗。
