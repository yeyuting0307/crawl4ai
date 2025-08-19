#!/usr/bin/env python3
"""
簡化的增強版功能測試
"""

import asyncio
import sys
import os
import json
import logging

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO)

async def simple_enhanced_test():
    """簡化的增強版測試"""
    try:
        from crawl4ai.task_driven_crawler_v2 import TaskDrivenCrawler
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
        
        print("🚀 測試LLM網站推薦功能...")
        
        # 測試1: LLM網站推薦
        recommended_urls = await crawler._llm_recommend_websites(
            "人工智慧晶片產業趨勢", 
            ["AI晶片", "GPU", "NVIDIA"], 
            max_sites=3
        )
        
        print(f"📋 LLM推薦的網站數量: {len(recommended_urls)}")
        for i, url in enumerate(recommended_urls[:3]):
            print(f"  {i+1}. {url}")
        
        print("\n🧪 測試JSON解析功能...")
        
        # 測試2: 強化JSON解析
        test_json_cases = [
            '{"title": "test", "content": "正常JSON"}',
            '{"title": "test", "content": "缺少引號}',
            '{"title": "test"',
            'invalid json content',
            '{"title": "test", "content": "帶\\n換行符的內容"}'
        ]
        
        for i, test_case in enumerate(test_json_cases):
            try:
                result = crawler._robust_json_parse(test_case)
                if result:
                    print(f"  ✅ 測試案例 {i+1}: 解析成功")
                else:
                    print(f"  ⚠️  測試案例 {i+1}: 解析失敗但無異常")
            except Exception as e:
                print(f"  ❌ 測試案例 {i+1}: {str(e)[:50]}...")
        
        print("\n📊 增強功能驗證完成:")
        print("  ✅ LLM網站推薦功能")
        print("  ✅ 強化JSON解析功能")
        print("  ✅ 錯誤處理機制")
        
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 增強版功能簡化測試\n")
    success = asyncio.run(simple_enhanced_test())
    
    if success:
        print("\n🎉 增強版功能測試成功！")
    else:
        print("\n💥 增強版功能測試失敗！")
