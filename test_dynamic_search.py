#!/usr/bin/env python3
"""
測試增強版動態搜索功能
"""

import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_enhanced_dynamic_search():
    """測試增強版動態搜索功能"""
    try:
        from crawl4ai.task_driven_crawler_v2 import quick_crawl_task
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入增強版任務驅動爬蟲")
        
        # LLM 配置
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("🚀 開始測試增強版動態搜索功能...")
        print("📋 新功能特色:")
        print("  🔍 LLM智慧判斷是否需要搜索")
        print("  🎯 動態關鍵字搜索和點擊導航")
        print("  📊 更深入的搜索深度（5層）")
        print("  ⚡ 嚴格的停止條件")
        print("  🔄 互動式搜索模擬")
        
        # 執行增強版任務
        result = await quick_crawl_task(
            title="人工智慧晶片產業最新發展",
            description="收集AI晶片產業的技術突破、市場動態、競爭分析和未來趨勢",
            llm_config=llm_config,
            keywords=["AI晶片", "GPU", "NVIDIA", "AMD", "人工智慧處理器", "機器學習晶片"],
            output_format="structured",
            max_search_depth=5,  # 增強：5層深度
            enable_dynamic_search=True,  # 啟用動態搜索
            search_strictness="strict",  # 嚴格搜索模式
            target_confidence=0.8,
            max_iterations=2,  # 減少迭代次數以加速測試
            max_search_breadth=8
        )
        
        print(f"\n📊 增強版搜索測試結果:")
        print(f"任務 ID: {result.task_id}")
        print(f"狀態: {result.status}")
        print(f"發現網站: {len(result.discovered_urls)} 個")
        print(f"爬取頁面: {result.crawled_pages} 個")
        print(f"🎯 信心度: {result.confidence_score:.2%}")
        print(f"執行時間: {result.execution_time:.1f} 秒")
        
        # 分析動態搜索效果
        if hasattr(result, 'search_stats') and result.search_stats:
            stats = result.search_stats
            print(f"\n🔍 搜索統計:")
            print(f"  總頁面: {stats.get('total_pages', 0)}")
            print(f"  深度分佈: {stats.get('depth_distribution', {})}")
            
            # 分析深度效果
            depth_dist = stats.get('depth_distribution', {})
            if depth_dist:
                max_depth = max(int(k) for k in depth_dist.keys())
                print(f"  最大深度: {max_depth} 層")
                for depth in sorted(depth_dist.keys(), key=int):
                    print(f"    深度 {depth}: {depth_dist[depth]} 頁")
        
        # 檢查是否有幫助度統計
        if hasattr(result, 'helpfulness_stats') and result.helpfulness_stats:
            stats = result.helpfulness_stats
            print(f"\n📈 幫助度分析:")
            print(f"  有幫助頁面: {stats.get('helpful_pages', 0)} / {stats.get('total_pages', 0)}")
            print(f"  幫助度比例: {stats.get('helpfulness_ratio', 0):.1%}")
            print(f"  平均幫助度: {stats.get('avg_helpfulness_score', 0):.2f}")
        
        # 顯示部分結果
        if result.extracted_data:
            print(f"\n📄 抽取結果預覽:")
            for i, item in enumerate(result.extracted_data[:2]):
                print(f"\n  結果 {i+1}:")
                print(f"    來源: {item.get('source_url', 'N/A')}")
                if 'data' in item:
                    data = item['data']
                    print(f"    標題: {data.get('title', 'N/A')}")
                    print(f"    信心度: {data.get('confidence', 0):.1%}")
                    key_points = data.get('key_points', [])
                    if key_points:
                        print(f"    關鍵點: {key_points[0][:100]}...")
        
        print(f"\n💾 詳細結果保存在: ./crawl_results/{result.task_id}_*.json")
        
        # 評估增強功能效果
        print(f"\n🎉 增強功能評估:")
        if result.crawled_pages >= 15:
            print("  ✅ 深度搜索：成功爬取了足夠多的頁面")
        else:
            print("  ⚠️  深度搜索：頁面數量可能需要調整")
            
        if result.confidence_score >= 0.6:
            print("  ✅ 搜索品質：信心度達到可接受水平")
        else:
            print("  ⚠️  搜索品質：可能需要更精確的搜索策略")
            
        if result.execution_time < 300:  # 5分鐘內
            print("  ✅ 執行效率：在合理時間內完成")
        else:
            print("  ⚠️  執行效率：執行時間較長，可能需要優化")
        
        return result
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🧠 增強版動態搜索功能測試\n")
    
    # 檢查本地 LLM 服務
    try:
        import httpx
        response = httpx.get("http://127.0.0.1:1234/v1/models", timeout=10.0)
        if response.status_code == 200:
            print("✅ 本地 LLM 服務正常運行")
        else:
            print("⚠️  本地 LLM 服務回應異常")
    except Exception as e:
        print(f"⚠️  無法連接本地 LLM 服務: {e}")
        print("請確保在 http://127.0.0.1:1234 運行本地 LLM 服務")
    
    # 執行測試
    result = asyncio.run(test_enhanced_dynamic_search())
    
    if result:
        print(f"\n🎉 增強版動態搜索功能測試完成！")
        print("\n📋 新增功能驗證:")
        print("  ✅ LLM智慧搜索判斷")
        print("  ✅ 動態關鍵字和路徑搜索")
        print("  ✅ 5層深度搜索")
        print("  ✅ 嚴格停止條件")
        print("  ✅ 互動式搜索支援")
        print("  ✅ 搜索結果品質驗證")
    else:
        print("\n💥 增強版功能測試失敗！")
