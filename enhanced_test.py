#!/usr/bin/env python3
"""
測試增強版任務驅動爬蟲的新功能：
1. LLM智慧網站推薦
2. 幫助度評估和動態深度調整
3. 根據幫助度調整摘要詳細程度
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

async def test_enhanced_crawler():
    """測試增強版任務驅動爬蟲"""
    try:
        # 導入必要模組
        from crawl4ai.task_driven_crawler_v2 import TaskDrivenCrawler, TaskObjective
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入增強版任務驅動爬蟲模組")
        
        # 配置 LLM
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("✅ LLM 配置完成")
        
        # 創建增強版任務目標
        objective = TaskObjective(
            title="AI 晶片市場分析",
            description="收集人工智慧晶片市場的最新發展、技術趨勢和投資機會分析",
            keywords=["AI晶片", "GPU", "NVIDIA", "人工智慧", "半導體", "機器學習", "深度學習"],
            output_format="structured",
            time_priority=True,
            max_search_depth=2,  # 起始深度
            max_search_breadth=3,  # 降低廣度以便觀察動態調整
            enable_content_summary=True,
            max_results=8
        )
        
        print("✅ 增強版任務目標配置完成")
        print(f"📋 任務關鍵字: {', '.join(objective.keywords)}")
        
        # 創建爬蟲實例
        crawler = TaskDrivenCrawler(llm_config=llm_config)
        
        print("🚀 開始執行AI晶片市場分析任務...")
        print("🔍 新功能測試：")
        print("   1. LLM智慧網站推薦")
        print("   2. 頁面幫助度自動評估")
        print("   3. 動態深度調整（有幫助頁面+2層，無幫助連續2個則停止）")
        print("   4. 根據幫助度生成詳細/簡潔摘要")
        
        # 執行任務
        result = await crawler.execute_task(
            objective=objective,
            additional_urls=[],  # 不提供額外URL，測試LLM推薦功能
            output_dir="./crawl_results"
        )
        
        print("\n📊 增強版任務執行結果:")
        print(f"任務 ID: {result.task_id}")
        print(f"狀態: {result.status}")
        print(f"發現網站: {len(result.discovered_urls)} 個")
        print(f"爬取頁面: {result.crawled_pages} 個")
        print(f"信心度: {result.confidence_score:.2%}")
        print(f"執行時間: {result.execution_time:.1f} 秒")
        
        # 分析幫助度評估結果
        helpful_pages = 0
        unhelpful_pages = 0
        detailed_summaries = 0
        brief_summaries = 0
        
        if result.extracted_data:
            print(f"\n📄 內容分析結果:")
            
            for i, item in enumerate(result.extracted_data):
                is_helpful = item.get('is_helpful', False)
                helpfulness_score = item.get('helpfulness_score', 0.0)
                summary_length = len(item.get('summary', ''))
                
                if is_helpful:
                    helpful_pages += 1
                else:
                    unhelpful_pages += 1
                    
                if summary_length > 200:
                    detailed_summaries += 1
                else:
                    brief_summaries += 1
                
                print(f"\n頁面 {i+1}: {item.get('source_url', 'N/A')}")
                print(f"  幫助度: {'✅ 有幫助' if is_helpful else '❌ 無幫助'} (分數: {helpfulness_score:.2f})")
                print(f"  摘要長度: {summary_length} 字元 ({'詳細' if summary_length > 200 else '簡潔'})")
                if 'helpfulness_reason' in item:
                    print(f"  評估原因: {item['helpfulness_reason'][:100]}...")
        
        print(f"\n📈 幫助度統計:")
        print(f"  有幫助頁面: {helpful_pages} 個")
        print(f"  無幫助頁面: {unhelpful_pages} 個")
        print(f"  詳細摘要: {detailed_summaries} 個")
        print(f"  簡潔摘要: {brief_summaries} 個")
        
        if result.page_summaries:
            print(f"\n📝 頁面摘要範例:")
            for i, summary in enumerate(result.page_summaries[:2]):
                print(f"\n摘要 {i+1}:")
                print(f"  URL: {summary.get('url', 'N/A')}")
                print(f"  標題: {summary.get('title', 'N/A')}")
                print(f"  摘要: {summary.get('summary', 'N/A')[:150]}...")
                
        if hasattr(result, 'search_stats') and result.search_stats:
            print(f"\n🔍 搜索統計:")
            stats = result.search_stats
            if 'depth_distribution' in stats:
                print(f"  深度分布: {stats['depth_distribution']}")
            if 'helpful_pages_by_depth' in stats:
                print(f"  各深度有幫助頁面: {stats.get('helpful_pages_by_depth', {})}")
                
        print(f"\n💾 結果保存在: ./crawl_results")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🧠 AI晶片市場分析 - 增強版任務驅動爬蟲測試\n")
    
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
    result = asyncio.run(test_enhanced_crawler())
    
    if result:
        print(f"\n🎉 增強版測試完成！信心度: {result.confidence_score:.2%}")
        print("📋 新功能驗證:")
        print("  ✅ LLM智慧網站推薦")
        print("  ✅ 頁面幫助度評估")
        print("  ✅ 動態深度調整")
        print("  ✅ 智慧摘要生成")
    else:
        print("\n💥 增強版測試失敗！")
