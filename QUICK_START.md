# 任務驅動爬蟲 - 快速入門

## 🚀 5分鐘開始使用

### 1. 確認環境
```bash
# 確認 crawl4ai 已安裝
python -c "import crawl4ai; print('✅ 環境正常')"
```

### 2. 啟動本地 LLM（可選）
```bash
# 如果您有本地 LLM 服務，請確保運行在：
# http://127.0.0.1:8080/v1
# 
# 沒有 LLM 服務？系統會使用模擬回應進行測試
```

### 3. 立即開始

#### 方法一：CLI 快速使用
```bash
# 股價分析範例
crwl task --title "台積電股價分析" \
          --description "收集台積電最新股價分析和預測" \
          --keywords "台積電,TSM,股價,半導體"

# 產業研究範例  
crwl task --title "AI產業趨勢" \
          --description "研究人工智慧產業發展趨勢" \
          --keywords "AI,人工智慧,機器學習,趨勢" \
          --output-format summary
```

#### 方法二：Python 程式
```python
import asyncio
from crawl4ai import quick_crawl_task

async def main():
    # 簡單任務
    result = await quick_crawl_task(
        title="Netflix 股價分析",
        description="收集 Netflix 相關投資分析",
        keywords=["Netflix", "NFLX", "串流", "股價"]
    )
    
    print(f"✅ 完成！爬取了 {result.crawled_pages} 個頁面")
    print(f"📊 信心度: {result.confidence_score:.1%}")
    print(f"📁 結果儲存在: {result.output_files}")

# 執行
asyncio.run(main())
```

### 4. 查看結果
```bash
# 系統會自動創建輸出資料夾
ls ./crawl_results/

# 檢視摘要報告
cat ./crawl_results/task_*_summary.md

# 檢視結構化資料
cat ./crawl_results/task_*_data.jsonl
```

### 5. 更多範例
```bash
# 查看內建範例
crwl task-example

# 運行完整範例集
python examples/task_driven_examples.py
```

## 📋 常用命令參考

### 基本格式
```bash
crwl task --title "任務標題" \
          --description "詳細描述任務目標" \
          --keywords "關鍵字1,關鍵字2,關鍵字3"
```

### 常用選項
```bash
--output-format structured    # 輸出結構化 JSON 資料
--output-format summary      # 輸出 Markdown 摘要報告  
--max-pages 20              # 最多爬取 20 個頁面
--additional-urls "url1,url2" # 手動添加特定網址
--verbose                   # 顯示詳細執行過程
```

### 完整範例
```bash
crwl task \
  --title "蘋果財報分析" \
  --description "分析蘋果最新季度財報，包括營收、獲利和未來展望" \
  --keywords "Apple,AAPL,財報,營收,iPhone" \
  --additional-urls "https://investor.apple.com" \
  --output-format structured \
  --max-pages 15 \
  --verbose
```

## 🎯 實用技巧

### 關鍵字設計
- ✅ 使用具體術語：「台積電」而非「科技公司」
- ✅ 包含英文關鍵字：「TSMC, 台積電」
- ✅ 混合不同層次：「股價, 投資, 分析, 預測」

### 任務描述最佳實踐
- ✅ 明確說明想要什麼資訊
- ✅ 提到資料的用途或背景
- ✅ 指定時間範圍（如「最新」、「2025年」）

### 輸出格式選擇
- 📊 `structured` → 需要後續程式處理的結構化資料
- 📝 `summary` → 人類閱讀的摘要報告

## ⚡ 快速測試

```bash
# 最簡單的測試
crwl task --title "今日科技新聞" --description "收集今日重要科技新聞" --keywords "科技,新聞"

# 確認系統正常
crwl task-example
```

## 🆘 遇到問題？

### 檢查清單
1. ✅ Python 環境是否正確
2. ✅ 網路連接是否正常  
3. ✅ 關鍵字是否具體
4. ✅ 描述是否清楚

### 快速除錯
```bash
# 啟用詳細模式
crwl task --title "測試" --description "測試任務" --keywords "test" --verbose

# 檢查輸出檔案
ls -la ./crawl_results/
```

---

**🎊 恭喜！您現在可以開始使用智慧任務驅動爬蟲了！**

更多詳細功能請參考：[完整文檔](TASK_DRIVEN_README.md)
