#!/usr/bin/env python3
"""
快速驗證增強版功能
"""

import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def quick_test():
    """快速測試增強版任務驅動爬蟲"""
    try:
        from crawl4ai.task_driven_crawler_v2 import quick_crawl_task
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入增強版模組")
        
        # LLM 配置
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        print("🚀 測試增強版信心度功能...")
        
        # 測試增強版功能：目標信心度80%
        result = await quick_crawl_task(
            title="AI晶片產業",
            description="收集AI晶片產業發展動態",
            llm_config=llm_config,
            keywords=["AI晶片", "NVIDIA"],
            output_format="structured",
            target_confidence=0.8,  # 80%信心度目標
            max_iterations=2,       # 限制迭代次數以加速測試
            max_search_depth=1,     # 減少搜尋深度
            max_search_breadth=3    # 減少搜尋寬度
        )
        
        print(f"\n📊 測試結果:")
        print(f"任務狀態: {result.status}")
        print(f"爬取頁面: {result.crawled_pages}")
        print(f"🎯 信心度: {result.confidence_score:.1%} (目標: 80%)")
        print(f"執行時間: {result.execution_time:.1f}秒")
        
        if result.confidence_score >= 0.8:
            print("🎉 達到目標信心度！")
        else:
            print(f"📈 信心度差距: {0.8 - result.confidence_score:.1%}")
        
        # 檢查是否有錯誤
        if result.error_messages:
            print(f"⚠️  錯誤數量: {len(result.error_messages)}")
        else:
            print("✅ 無錯誤記錄")
        
        print(f"\n💾 結果文件: ./crawl_results/{result.task_id}_*.json")
        
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 增強版信心度快速測試\n")
    
    success = asyncio.run(quick_test())
    
    if success:
        print("\n🎉 增強版功能測試完成！")
        print("\n📋 增強功能包括:")
        print("  ✅ LLM推薦網站")
        print("  ✅ 強化JSON解析")
        print("  ✅ 動態URL追加")
        print("  ✅ 信心度迭代")
        print("  ✅ 智慧停止條件")
    else:
        print("\n💥 測試失敗！")
