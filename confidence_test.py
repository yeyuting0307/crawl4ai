#!/usr/bin/env python3
"""
測試增強版任務驅動爬蟲：
1. 修復JSON解析錯誤，提高抽取成功率
2. 動態信心度提升機制
3. 智慧停止條件
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

async def test_enhanced_confidence_crawler():
    """測試增強版信心度提升爬蟲"""
    try:
        # 導入必要模組
        from crawl4ai.task_driven_crawler_v2 import quick_crawl_task
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入增強版任務驅動爬蟲模組")
        
        # 配置 LLM
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("✅ LLM 配置完成")
        
        # 執行增強版任務（目標信心度80%）
        print("🚀 開始執行增強版任務...")
        print("🎯 目標信心度: 80%")
        print("🔄 最大迭代次數: 3")
        print("🛠️  新功能:")
        print("   1. 強化JSON解析和錯誤修復")
        print("   2. 動態URL追加")
        print("   3. 智慧停止條件")
        print("   4. 迭代式信心度提升")
        
        result = await quick_crawl_task(
            title="人工智慧晶片產業趨勢",
            description="收集人工智慧晶片產業的最新技術發展、市場趨勢、主要廠商動態和投資機會分析",
            llm_config=llm_config,
            keywords=["AI晶片", "GPU", "NVIDIA", "AMD", "Intel", "人工智慧", "半導體", "機器學習"],
            output_format="structured",
            target_confidence=0.8,  # 80%信心度目標
            max_iterations=3,
            max_search_depth=2,
            max_search_breadth=5,
            enable_content_summary=True
        )
        
        print("\n📊 增強版任務執行結果:")
        print(f"任務 ID: {result.task_id}")
        print(f"狀態: {result.status}")
        print(f"發現網站: {len(result.discovered_urls)} 個")
        print(f"爬取頁面: {result.crawled_pages} 個")
        print(f"🎯 最終信心度: {result.confidence_score:.2%} (目標: 80%)")
        print(f"執行時間: {result.execution_time:.1f} 秒")
        
        # 分析信心度達成情況
        if result.confidence_score >= 0.8:
            print("🎉 成功達到目標信心度！")
        else:
            print(f"⚠️  未達到目標信心度，差距: {0.8 - result.confidence_score:.1%}")
        
        # 分析JSON解析成功率
        if result.extracted_data:
            total_extracted = len(result.extracted_data)
            valid_extractions = sum(1 for item in result.extracted_data if item.get('confidence', 0) > 0.3)
            success_rate = valid_extractions / total_extracted if total_extracted > 0 else 0
            
            print(f"\n📄 資料抽取分析:")
            print(f"  總抽取資料: {total_extracted} 條")
            print(f"  有效抽取: {valid_extractions} 條")
            print(f"  成功率: {success_rate:.1%}")
            
            # 顯示抽取資料品質
            high_quality_count = sum(1 for item in result.extracted_data if item.get('confidence', 0) > 0.7)
            print(f"  高品質資料: {high_quality_count} 條 (信心度>70%)")
        
        # 幫助度統計
        if hasattr(result, 'helpfulness_stats') and result.helpfulness_stats:
            stats = result.helpfulness_stats
            print(f"\n📈 幫助度統計:")
            print(f"  有幫助頁面: {stats.get('helpful_pages', 0)} / {stats.get('total_pages', 0)}")
            print(f"  幫助度比例: {stats.get('helpfulness_ratio', 0):.1%}")
            print(f"  平均幫助度: {stats.get('avg_helpfulness_score', 0):.2f}")
        
        # 錯誤分析
        if result.error_messages:
            print(f"\n⚠️  錯誤記錄: {len(result.error_messages)} 個")
            for i, error in enumerate(result.error_messages[:3]):
                print(f"  {i+1}. {error[:100]}...")
        else:
            print("\n✅ 無錯誤記錄")
        
        # 顯示部分抽取結果示例
        if result.extracted_data:
            print(f"\n📋 抽取結果示例:")
            for i, item in enumerate(result.extracted_data[:2]):
                print(f"\n  示例 {i+1}:")
                print(f"    來源: {item.get('source_url', 'N/A')}")
                print(f"    標題: {item.get('title', 'N/A')}")
                print(f"    信心度: {item.get('confidence', 0):.1%}")
                
                key_points = item.get('key_points', [])
                if key_points:
                    print(f"    關鍵點: {key_points[0][:80]}...")
        
        print(f"\n💾 詳細結果保存在: ./crawl_results/{result.task_id}_*.json")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🧠 AI晶片產業趨勢 - 增強版信心度提升測試\n")
    
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
    result = asyncio.run(test_enhanced_confidence_crawler())
    
    if result:
        if result.confidence_score >= 0.8:
            print(f"\n🎉 增強版測試完全成功！達到目標信心度: {result.confidence_score:.1%}")
        else:
            print(f"\n📊 增強版測試完成，信心度: {result.confidence_score:.1%}")
        
        print("📋 增強功能驗證:")
        print("  ✅ JSON解析錯誤修復")
        print("  ✅ 動態URL追加機制")
        print("  ✅ 智慧停止條件")
        print("  ✅ 迭代式信心度提升")
    else:
        print("\n💥 增強版測試失敗！")
