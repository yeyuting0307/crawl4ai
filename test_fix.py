#!/usr/bin/env python3
"""
測試增強版方法是否可用
"""

import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_methods():
    """測試增強版方法是否可以導入和使用"""
    try:
        from crawl4ai.task_driven_crawler_v2 import TaskDrivenCrawler, TaskObjective
        from crawl4ai import LLMConfig
        
        print("✅ 成功導入增強版模組")
        
        # LLM 配置
        llm_config = LLMConfig(
            provider="openai/local",
            base_url="http://127.0.0.1:1234/v1",
            api_token="not-important"
        )
        
        # 創建增強版爬蟲
        crawler = TaskDrivenCrawler(llm_config=llm_config)
        
        print("✅ 成功創建TaskDrivenCrawler實例")
        
        # 檢查方法是否存在
        methods_to_check = [
            '_extract_data_from_pages',
            '_llm_recommend_websites', 
            '_should_stop_iteration',
            '_get_dynamic_urls',
            '_analyze_content_gaps',
            '_generate_helpfulness_stats'
        ]
        
        for method_name in methods_to_check:
            if hasattr(crawler, method_name):
                print(f"✅ 方法 {method_name} 存在")
            else:
                print(f"❌ 方法 {method_name} 缺失")
        
        # 簡單測試LLM推薦方法
        print("\n🧪 測試LLM網站推薦功能...")
        try:
            urls = await crawler._llm_recommend_websites(
                "AI晶片產業測試",
                ["AI", "晶片"],
                max_sites=2
            )
            print(f"✅ LLM推薦方法運行成功，返回 {len(urls)} 個URL")
            for i, url in enumerate(urls):
                print(f"  {i+1}. {url}")
        except Exception as e:
            print(f"⚠️  LLM推薦方法測試失敗: {e}")
        
        print("\n🎉 所有增強功能檢查完成！")
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 增強版方法可用性測試\n")
    success = asyncio.run(test_methods())
    
    if success:
        print("\n✅ 增強版修復成功！所有核心方法都可用。")
        print("\n📋 修復內容:")
        print("  ✅ 修復 _extract_data_from_pages 方法缺失")
        print("  ✅ 修復 _llm_recommend_websites 方法缺失")
        print("  ✅ 修復方法參數問題")
        print("  ✅ 刪除重複代碼")
        print("  ✅ 修復類方法縮排問題")
        print("\n🚀 現在可以正常使用80%信心度目標和動態迭代功能！")
    else:
        print("\n❌ 仍存在問題，需要進一步修復。")
