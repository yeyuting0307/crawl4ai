"""
測試智能搜索爬蟲功能
基於Google Search API的智能關鍵字爬蟲測試
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from crawl4ai import LLMConfig
from crawl4ai.smart_search_crawler import SmartSearchCrawler, TaskObjectiveV3, quick_smart_crawl
from crawl4ai.google_search_integration import create_google_search_config_from_env

async def test_basic_smart_crawl():
    """測試基本智能搜索爬蟲功能"""
    print("=== 測試1：基本智能搜索爬蟲 ===")
    
    try:
        # 配置LLM
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1",
            api_token="sk-test-token"
        )
        
        # 執行智能爬蟲
        result = await quick_smart_crawl(
            title="2024年人工智慧發展趨勢",
            description="研究2024年人工智慧技術的最新發展趨勢、應用領域和市場前景",
            initial_keywords=["AI", "人工智慧", "2024趨勢"],
            llm_config=llm_config,
            max_iterations=2,
            target_confidence=0.75
        )
        
        print(f"任務狀態: {result.status}")
        print(f"迭代次數: {len(result.iterations)}")
        print(f"總爬取頁面: {result.total_pages_crawled}")
        print(f"最終信心度: {result.final_confidence:.2%}")
        print(f"執行時間: {result.execution_time:.1f}秒")
        
        # 顯示每次迭代的結果
        for i, iteration in enumerate(result.iterations, 1):
            print(f"\n迭代 {i}:")
            print(f"  使用關鍵字: {iteration.keywords_used}")
            print(f"  搜索結果數: {len(iteration.search_results)}")
            print(f"  爬取頁面數: {len(iteration.crawled_pages)}")
            print(f"  信心度: {iteration.confidence_score:.2%}")
            if iteration.new_keywords_generated:
                print(f"  新生成關鍵字: {iteration.new_keywords_generated}")
        
        # 顯示結構化資料摘要
        if result.structured_data:
            print(f"\n結構化資料數量: {len(result.structured_data)}")
            for i, data in enumerate(result.structured_data[:3], 1):  # 顯示前3條
                print(f"  {i}. {data.get('title', '無標題')}")
                print(f"     相關度: {data.get('relevance_score', 0):.2f}")
                print(f"     來源: {data.get('source_url', '')}")
        
        return result
        
    except Exception as e:
        print(f"測試失敗: {e}")
        return None

async def test_taiwan_specific_search():
    """測試台灣特定主題的搜索"""
    print("\n=== 測試2：台灣特定主題搜索 ===")
    
    try:
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1",
            api_token="sk-test-token"
        )
        
        objective = TaskObjectiveV3(
            title="台灣半導體產業競爭力分析",
            description="分析台灣半導體產業在全球市場的競爭優勢、挑戰和未來發展方向",
            initial_keywords=["台積電", "台灣半導體", "晶圓代工"],
            max_iterations=3,
            target_confidence=0.8,
            require_taiwan_sources=True,
            output_format="summary"
        )
        
        crawler = SmartSearchCrawler(llm_config)
        result = await crawler.execute_smart_crawl(objective)
        
        print(f"任務狀態: {result.status}")
        print(f"最終信心度: {result.final_confidence:.2%}")
        print(f"總關鍵字數: {result.total_keywords_used}")
        
        if result.summary:
            print(f"\n摘要報告 (前300字):")
            print(result.summary[:300] + "..." if len(result.summary) > 300 else result.summary)
        
        return result
        
    except Exception as e:
        print(f"台灣主題測試失敗: {e}")
        return None

async def test_keyword_refinement():
    """測試關鍵字優化功能"""
    print("\n=== 測試3：關鍵字優化迭代 ===")
    
    try:
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1",
            api_token="sk-test-token"
        )
        
        objective = TaskObjectiveV3(
            title="綠能科技投資機會",
            description="研究再生能源領域的投資機會和技術趨勢",
            initial_keywords=["綠能", "太陽能"],  # 故意使用較少的初始關鍵字
            max_iterations=3,
            target_confidence=0.8,
            enable_keyword_refinement=True,
            max_search_results_per_keyword=8
        )
        
        crawler = SmartSearchCrawler(llm_config)
        result = await crawler.execute_smart_crawl(objective)
        
        print(f"任務狀態: {result.status}")
        print(f"迭代次數: {len(result.iterations)}")
        
        # 分析關鍵字演化
        all_keywords = set()
        for i, iteration in enumerate(result.iterations, 1):
            print(f"\n迭代 {i} 關鍵字分析:")
            print(f"  使用的關鍵字: {iteration.keywords_used}")
            all_keywords.update(iteration.keywords_used)
            
            if iteration.new_keywords_generated:
                print(f"  新生成關鍵字: {iteration.new_keywords_generated}")
                print(f"  信心度提升: {iteration.confidence_score:.2%}")
        
        print(f"\n關鍵字總演化: {len(all_keywords)} 個唯一關鍵字")
        print(f"關鍵字列表: {list(all_keywords)}")
        
        return result
        
    except Exception as e:
        print(f"關鍵字優化測試失敗: {e}")
        return None

async def test_google_search_integration():
    """測試Google Search API集成"""
    print("\n=== 測試4：Google Search API集成 ===")
    
    try:
        from crawl4ai.google_search_integration import GoogleSearchAPI, IntelligentKeywordGenerator
        
        # 測試Google搜索
        google_config = create_google_search_config_from_env()
        google_search = GoogleSearchAPI(google_config)
        
        test_query = "台灣AI發展"
        search_results = await google_search.search(test_query, 5)
        
        print(f"搜索查詢: '{test_query}'")
        print(f"搜索結果數: {len(search_results)}")
        
        for i, result in enumerate(search_results, 1):
            print(f"  {i}. {result.title}")
            print(f"     URL: {result.url}")
            print(f"     摘要: {result.snippet[:100]}...")
            print(f"     排名: {result.search_rank}")
        
        # 測試關鍵字生成
        llm_config = LLMConfig(
            base_url="http://localhost:1234/v1", 
            api_token="sk-test-token"
        )
        
        keyword_generator = IntelligentKeywordGenerator(llm_config)
        generated_keywords = await keyword_generator.generate_initial_keywords(
            "電動車產業發展",
            "分析全球電動車產業的發展現況和未來趨勢"
        )
        
        print(f"\n關鍵字生成測試:")
        print(f"生成的關鍵字: {generated_keywords}")
        
        return {"search_results": search_results, "keywords": generated_keywords}
        
    except Exception as e:
        print(f"Google Search集成測試失敗: {e}")
        return None

async def save_test_results(results: dict, output_dir: str = "test_results"):
    """保存測試結果"""
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        for test_name, result in results.items():
            if result:
                filename = f"{output_dir}/{test_name}_result.json"
                
                # 將結果轉換為可序列化的格式
                if hasattr(result, '__dict__'):
                    result_data = result.__dict__.copy()
                    
                    # 處理datetime對象
                    for key, value in result_data.items():
                        if hasattr(value, 'isoformat'):
                            result_data[key] = value.isoformat()
                        elif isinstance(value, list):
                            # 處理列表中的對象
                            processed_list = []
                            for item in value:
                                if hasattr(item, '__dict__'):
                                    item_dict = item.__dict__.copy()
                                    for k, v in item_dict.items():
                                        if hasattr(v, 'isoformat'):
                                            item_dict[k] = v.isoformat()
                                    processed_list.append(item_dict)
                                else:
                                    processed_list.append(item)
                            result_data[key] = processed_list
                else:
                    result_data = result
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, ensure_ascii=False, indent=2)
                
                print(f"測試結果已保存到: {filename}")
        
    except Exception as e:
        print(f"保存測試結果失敗: {e}")

async def main():
    """主測試函數"""
    print("開始智能搜索爬蟲測試...")
    print(f"工作目錄: {os.getcwd()}")
    
    # 檢查環境變數
    if not os.getenv("GOOGLE_API_KEY"):
        print("錯誤: 請在.env檔案中設置GOOGLE_API_KEY")
        return
    
    results = {}
    
    # 執行測試
    results["basic_crawl"] = await test_basic_smart_crawl()
    results["taiwan_search"] = await test_taiwan_specific_search()
    results["keyword_refinement"] = await test_keyword_refinement()
    results["google_integration"] = await test_google_search_integration()
    
    # 保存結果
    await save_test_results(results)
    
    print("\n=== 測試完成 ===")
    successful_tests = sum(1 for result in results.values() if result is not None)
    print(f"成功測試: {successful_tests}/{len(results)}")

if __name__ == "__main__":
    # 載入環境變數
    from dotenv import load_dotenv
    load_dotenv()
    
    asyncio.run(main())
