#!/usr/bin/env python3
"""
簡化的任務驅動爬蟲測試 - 單一URL測試
"""

import asyncio
import sys
import os

# 添加項目路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def simple_test():
    """簡化測試：只爬取一個具體的台積電頁面"""
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig, CacheMode
        
        print("✅ 成功導入爬蟲模組")
        
        # 測試爬取單一台積電頁面
        target_url = "https://finance.yahoo.com/quote/TSM"
        
        config = CrawlerRunConfig(
            word_count_threshold=10,
            cache_mode=CacheMode.BYPASS
        )
        
        print(f"🚀 開始爬取: {target_url}")
        
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=target_url, config=config)
            
            # 檢查result是否為AsyncGenerator並正確處理
            if hasattr(result, '__aiter__'):
                # 如果是AsyncGenerator，收集所有結果
                results = []
                async for r in result:
                    results.append(r)
                if results:
                    result = results[0]  # 取第一個結果
                else:
                    print("❌ 沒有獲得任何結果")
                    return None
            
            # 輸出結果資訊
            if hasattr(result, 'success') and result.success:
                print("✅ 爬取成功！")
                
                if hasattr(result, 'markdown') and result.markdown:
                    print(f"📄 內容長度: {len(result.markdown)} 字元")
                    
                    # 顯示前500字元內容
                    content = str(result.markdown)
                    if len(content) > 500:
                        content = content[:500] + "..."
                    print(f"📝 內容預覽:\n{content}")
                    
                if hasattr(result, 'metadata') and result.metadata:
                    title = result.metadata.get('title', 'N/A')
                    print(f"🏷️  標題: {title}")
                    
                return result
            else:
                error_msg = getattr(result, 'error_message', '未知錯誤')
                print(f"❌ 爬取失敗: {error_msg}")
                return None
        
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 台積電股價頁面爬取測試\n")
    
    result = asyncio.run(simple_test())
    
    if result:
        print("\n🎉 測試完成！")
    else:
        print("\n💥 測試失敗！")
