#!/usr/bin/env python3
"""
測試任務驅動爬蟲的簡化腳本
"""

import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_task_crawler():
    """測試任務驅動爬蟲"""
    try:
        # 導入必要模組
        from crawl4ai.task_driven_crawler_v2 import quick_crawl_task
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入任務驅動爬蟲模組")
        
        # 配置 LLM
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("✅ LLM 配置完成")
        
        # 執行簡單任務
        print("🚀 開始執行台積電股價分析任務...")
        
        result = await quick_crawl_task(
            title="台積電股價分析",
            description="收集台積電最新股價分析、專家預測和市場觀點",
            llm_config=llm_config,
            keywords=["TSM", "台積電", "股價", "半導體", "預測"],
            output_format="structured",
            additional_urls=[],
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
            print(f"抽取資料: {len(result.extracted_data)} 條")
            
        if result.summary:
            print(f"摘要長度: {len(result.summary)} 字元")
            print(f"摘要預覽: {result.summary[:200]}...")
            
        print(f"\n💾 結果保存在: ./crawl_results")
        
        return result
        
    except ImportError as e:
        print(f"❌ 導入錯誤: {e}")
        return None
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 台積電股價分析 - 任務驅動爬蟲測試\n")
    
    # 檢查本地 LLM 是否運行
    try:
        import httpx
        response = httpx.get("http://127.0.0.1:1234/v1/models", timeout=5.0)
        if response.status_code == 200:
            print("✅ 本地 LLM 服務正常運行")
        else:
            print("⚠️  本地 LLM 服務回應異常")
    except Exception as e:
        print(f"⚠️  無法連接本地 LLM 服務: {e}")
        print("請確保在 http://127.0.0.1:1234 運行本地 LLM 服務")
    
    # 執行測試
    result = asyncio.run(test_task_crawler())
    
    if result:
        print("\n🎉 測試完成！")
    else:
        print("\n💥 測試失敗！")
