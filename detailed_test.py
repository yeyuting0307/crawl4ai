#!/usr/bin/env python3
"""
詳細測試任務驅動爬蟲
"""

import asyncio
import sys
import os
import logging

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 設定詳細日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def detailed_test():
    """詳細測試任務驅動爬蟲"""
    try:
        # 導入必要模組
        from crawl4ai.task_driven_crawler_v2 import TaskDrivenCrawler, TaskObjective
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入任務驅動爬蟲模組")
        
        # 配置 LLM
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("✅ LLM 配置完成")
        
        # 創建任務目標
        objective = TaskObjective(
            title="台積電股價分析",
            description="收集台積電最新股價分析、專家預測和市場觀點",
            keywords=["TSM", "台積電", "stock", "semiconductor"],
            output_format="structured",
            time_priority=True,
            max_search_depth=2,  # 降低深度避免過度爬取
            max_search_breadth=5,  # 降低廣度
            enable_content_summary=True,
            max_results=10  # 限制結果數量
        )
        
        print("✅ 任務目標配置完成")
        
        # 創建爬蟲實例
        crawler = TaskDrivenCrawler(llm_config=llm_config)
        
        print("🚀 開始執行台積電股價分析任務...")
        
        # 執行任務 - 手動提供一些台積電相關的種子URL
        seed_urls = [
            "https://finance.yahoo.com/quote/TSM",  # Yahoo Finance TSM頁面
            "https://www.investing.com/equities/taiwan-semiconductor-manufacturing",
        ]
        
        result = await crawler.execute_task(
            objective=objective,
            additional_urls=seed_urls,
            output_dir="./crawl_results"
        )
        
        print("\n📊 任務執行結果:")
        print(f"任務 ID: {result.task_id}")
        print(f"狀態: {result.status}")
        print(f"發現網站: {len(result.discovered_urls)} 個")
        print(f"爬取頁面: {result.crawled_pages} 個")
        print(f"信心度: {result.confidence_score:.2%}")
        print(f"執行時間: {result.execution_time:.1f} 秒")
        
        if result.extracted_data:
            print(f"\n📄 抽取資料: {len(result.extracted_data)} 條")
            # 顯示前2條資料的詳細內容
            for i, item in enumerate(result.extracted_data[:2]):
                print(f"\n資料 {i+1}:")
                print(f"  來源: {item.get('source_url', 'N/A')}")
                if 'data' in item:
                    data = item['data']
                    if isinstance(data, dict):
                        for key, value in list(data.items())[:5]:
                            print(f"  {key}: {str(value)[:150]}...")
                    
        if result.page_summaries:
            print(f"\n📝 頁面摘要: {len(result.page_summaries)} 個")
            for i, summary in enumerate(result.page_summaries[:2]):
                print(f"\n摘要 {i+1}: {summary[:200]}...")
                
        if result.summary:
            print(f"\n📋 總摘要:")
            print(f"{result.summary[:400]}...")
            
        print(f"\n💾 結果保存在: ./crawl_results")
        
        # 顯示錯誤訊息（如果有）
        if result.error_messages:
            print(f"\n⚠️  錯誤訊息:")
            for error in result.error_messages:
                print(f"  - {error}")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 台積電股價分析 - 詳細測試\n")
    
    # 檢查本地 LLM 服務
    try:
        import httpx
        response = httpx.get("http://127.0.0.1:1234/v1/models", timeout=10.0)
        if response.status_code == 200:
            print("✅ 本地 LLM 服務正常運行")
            models = response.json()
            if 'data' in models and len(models['data']) > 0:
                print(f"✅ 可用模型: {models['data'][0].get('id', 'unknown')}")
        else:
            print("⚠️  本地 LLM 服務回應異常")
    except Exception as e:
        print(f"⚠️  無法連接本地 LLM 服務: {e}")
        print("請確保在 http://127.0.0.1:1234 運行本地 LLM 服務")
    
    # 執行測試
    result = asyncio.run(detailed_test())
    
    if result:
        print(f"\n🎉 測試完成！信心度: {result.confidence_score:.2%}")
    else:
        print("\n💥 測試失敗！")
