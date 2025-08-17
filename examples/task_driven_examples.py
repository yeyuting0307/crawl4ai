"""
任務驅動、自適應、語意理解型爬蟲系統 - 使用範例

這個檔案展示如何使用新的任務驅動爬蟲系統來執行各種任務。
"""

import asyncio
import json
from pathlib import Path
from crawl4ai import (
    TaskDrivenCrawler,
    TaskObjective,
    LLMConfig,
    quick_crawl_task
)

async def example_1_nvidia_stock_analysis():
    """範例 1: NVIDIA 股價預測分析"""
    print("🚀 範例 1: NVIDIA 股價預測分析")
    print("=" * 50)
    
    # 配置本地 LLM（您需要根據實際配置調整）
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx"
    )
    
    # 執行任務
    result = await quick_crawl_task(
        title="NVIDIA (NVDA) 股價預測分析 2025",
        description="收集和分析關於 NVIDIA 股價的專家預測、財務分析和市場觀點",
        llm_config=llm_config,
        keywords=["NVDA", "NVIDIA", "股價預測", "AI 晶片", "GPU", "財務分析"],
        output_format="structured",
        additional_urls=[
            "https://investor.nvidia.com/",
            "https://finance.yahoo.com/quote/NVDA"
        ],
        output_dir="./examples/nvidia_analysis"
    )
    
    print(f"✅ 任務完成！")
    print(f"   📊 爬取頁面: {result.crawled_pages}")
    print(f"   🎯 信心度: {result.confidence_score:.2%}")
    print(f"   ⏱️ 執行時間: {result.execution_time:.1f} 秒")
    print(f"   📁 結果保存在: ./examples/nvidia_analysis/")
    
    return result

async def example_2_ai_industry_trends():
    """範例 2: AI 產業趨勢研究（摘要格式）"""
    print("\n🔍 範例 2: AI 產業趨勢研究")
    print("=" * 50)
    
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx"
    )
    
    result = await quick_crawl_task(
        title="2025 年 AI 產業趨勢與發展預測",
        description="研究人工智慧產業的最新趨勢、技術發展和市場機會",
        llm_config=llm_config,
        keywords=["AI", "人工智慧", "機器學習", "深度學習", "產業趨勢", "技術發展"],
        output_format="summary",  # 使用摘要格式
        additional_urls=[
            "https://www.mckinsey.com/capabilities/quantumblack/our-insights",
            "https://www.pwc.com/gx/en/issues/data-and-analytics/artificial-intelligence.html"
        ],
        output_dir="./examples/ai_trends"
    )
    
    print(f"✅ 任務完成！")
    print(f"   📝 生成摘要: {'是' if result.summary else '否'}")
    print(f"   🎯 信心度: {result.confidence_score:.2%}")
    print(f"   📁 結果保存在: ./examples/ai_trends/")
    
    # 顯示摘要預覽
    if result.summary:
        preview = result.summary[:200] + "..." if len(result.summary) > 200 else result.summary
        print(f"\n📖 摘要預覽:\n{preview}")
    
    return result

async def example_3_brand_monitoring():
    """範例 3: 品牌監測（Tesla）"""
    print("\n🏷️ 範例 3: Tesla 品牌監測")
    print("=" * 50)
    
    llm_config = LLMConfig(
        provider="openai/local", 
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx"
    )
    
    # 建立任務目標
    objective = TaskObjective(
        title="Tesla 品牌聲量與市場反應監測",
        description="監測 Tesla 在各大媒體的報導、市場反應和公眾觀點",
        keywords=["Tesla", "特斯拉", "電動車", "馬斯克", "Elon Musk", "EV"],
        target_domains=["tesla.com", "cnbc.com", "reuters.com"],  # 指定目標域名
        output_format="structured",
        schema={  # 自定義 schema
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "新聞標題"},
                "date": {"type": "string", "description": "發布日期"},
                "sentiment": {"type": "string", "enum": ["positive", "negative", "neutral"], "description": "情緒傾向"},
                "key_topics": {"type": "array", "items": {"type": "string"}, "description": "關鍵話題"},
                "impact_score": {"type": "number", "description": "影響力評分 (1-10)"},
                "source_credibility": {"type": "string", "enum": ["high", "medium", "low"], "description": "來源可信度"}
            }
        }
    )
    
    # 使用 TaskDrivenCrawler 類別
    crawler = TaskDrivenCrawler(llm_config)
    result = await crawler.execute_task(
        objective=objective,
        additional_urls=[
            "https://www.tesla.com/blog",
            "https://ir.tesla.com/"
        ],
        output_dir="./examples/tesla_monitoring"
    )
    
    print(f"✅ 任務完成！")
    print(f"   🎯 發現網站: {len(result.discovered_urls)}")
    print(f"   📊 抽取資料: {len(result.extracted_data)}")
    print(f"   🎯 信心度: {result.confidence_score:.2%}")
    
    return result

async def example_4_academic_research():
    """範例 4: 學術研究追蹤（量子計算）"""
    print("\n🔬 範例 4: 量子計算研究追蹤")
    print("=" * 50)
    
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1", 
        api_token="local-mlx"
    )
    
    objective = TaskObjective(
        title="量子計算研究進展與突破",
        description="追蹤量子計算領域的最新研究成果、技術突破和產業應用",
        keywords=["quantum computing", "qubit", "quantum algorithm", "quantum supremacy", "量子計算"],
        exclude_domains=["wikipedia.org"],  # 排除某些域名
        output_format="summary",
        max_results=30
    )
    
    crawler = TaskDrivenCrawler(llm_config)
    result = await crawler.execute_task(
        objective=objective,
        additional_urls=[
            "https://arxiv.org/list/quant-ph/recent",
            "https://quantum-computing.ibm.com/"
        ],
        output_dir="./examples/quantum_research"
    )
    
    print(f"✅ 任務完成！")
    print(f"   📚 爬取頁面: {result.crawled_pages}")
    print(f"   📝 生成摘要: {'是' if result.summary else '否'}")
    print(f"   🎯 信心度: {result.confidence_score:.2%}")
    
    return result

async def example_5_financial_analysis():
    """範例 5: 金融市場分析（多標的）"""
    print("\n💰 範例 5: 科技股分析比較")
    print("=" * 50)
    
    llm_config = LLMConfig(
        provider="openai/local",
        base_url="http://127.0.0.1:8080/v1",
        api_token="local-mlx"
    )
    
    # 分析多個標的
    stocks = ["NVDA", "AAPL", "MSFT", "GOOGL"]
    results = []
    
    for stock in stocks:
        print(f"  🔍 分析 {stock}...")
        
        result = await quick_crawl_task(
            title=f"{stock} 股價分析與預測",
            description=f"分析 {stock} 的財務表現、市場預測和投資機會",
            llm_config=llm_config,
            keywords=[stock, "股價", "財報", "預測", "分析"],
            output_format="structured",
            output_dir=f"./examples/stocks_analysis/{stock.lower()}"
        )
        
        results.append({
            "stock": stock,
            "confidence": result.confidence_score,
            "pages": result.crawled_pages,
            "data_points": len(result.extracted_data)
        })
    
    # 顯示比較結果
    print(f"\n📊 分析結果比較:")
    for r in results:
        print(f"   {r['stock']}: 信心度 {r['confidence']:.2%}, "
              f"頁面 {r['pages']}, 資料點 {r['data_points']}")
    
    return results

def save_example_results(results, filename):
    """保存範例結果"""
    output_dir = Path("./examples/summary")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"📁 結果摘要保存在: {output_dir / filename}")

async def run_all_examples():
    """運行所有範例"""
    print("🎯 任務驅動爬蟲系統 - 完整範例展示")
    print("=" * 60)
    print("這個範例展示了系統的各種應用場景：")
    print("1. 股價分析（結構化資料）")
    print("2. 產業趨勢（摘要報告）") 
    print("3. 品牌監測（自定義 schema）")
    print("4. 學術研究（排除特定域名）")
    print("5. 多標的分析（批次處理）")
    print("=" * 60)
    
    all_results = {}
    
    try:
        # 範例 1: NVIDIA 分析
        result1 = await example_1_nvidia_stock_analysis()
        all_results['nvidia_analysis'] = {
            'status': 'completed',
            'pages': result1.crawled_pages,
            'confidence': result1.confidence_score
        }
        
        # 範例 2: AI 趨勢
        result2 = await example_2_ai_industry_trends()
        all_results['ai_trends'] = {
            'status': 'completed', 
            'pages': result2.crawled_pages,
            'confidence': result2.confidence_score
        }
        
        # 範例 3: Tesla 監測
        result3 = await example_3_brand_monitoring()
        all_results['tesla_monitoring'] = {
            'status': 'completed',
            'pages': result3.crawled_pages,
            'confidence': result3.confidence_score
        }
        
        # 範例 4: 量子計算
        result4 = await example_4_academic_research() 
        all_results['quantum_research'] = {
            'status': 'completed',
            'pages': result4.crawled_pages,
            'confidence': result4.confidence_score
        }
        
        # 範例 5: 多股票分析
        result5 = await example_5_financial_analysis()
        all_results['multi_stock_analysis'] = {
            'status': 'completed',
            'results': result5
        }
        
        # 保存總結
        save_example_results(all_results, 'all_examples_summary.json')
        
        print(f"\n🎉 所有範例執行完成！")
        print(f"   📁 詳細結果請查看 ./examples/ 目錄")
        print(f"   📊 摘要報告: ./examples/summary/all_examples_summary.json")
        
    except Exception as e:
        print(f"\n❌ 執行過程中發生錯誤: {e}")
        all_results['error'] = str(e)
        save_example_results(all_results, 'examples_error.json')

# CLI 使用範例
def show_cli_examples():
    """顯示 CLI 使用範例"""
    print("""
🖥️  CLI 使用範例

1. 基本任務執行:
   crwl task --title "NVIDIA 股價分析" \\
             --description "收集 NVIDIA 股價預測和分析" \\
             --keywords "NVDA,股價,預測"

2. 摘要格式輸出:
   crwl task --title "AI 產業趨勢" \\
             --description "研究 AI 產業發展趨勢" \\
             --output-format summary

3. 添加額外網站:
   crwl task --title "Tesla 監測" \\
             --description "監測 Tesla 相關新聞" \\
             --additional-urls "https://tesla.com,https://ir.tesla.com"

4. 自定義輸出目錄:
   crwl task --title "市場分析" \\
             --description "分析股票市場" \\
             --output-dir "./my_analysis"

5. 顯示使用範例:
   crwl task-example
   
6. 詳細執行過程:
   crwl task --title "分析任務" \\
             --description "詳細分析" \\
             --verbose
""")

if __name__ == "__main__":
    print("選擇執行模式:")
    print("1. 運行所有範例 (預設)")
    print("2. 單獨運行 NVIDIA 分析")
    print("3. 單獨運行 AI 趨勢分析")
    print("4. 單獨運行品牌監測")
    print("5. 單獨運行學術研究")
    print("6. 單獨運行多股票分析")
    print("7. 顯示 CLI 使用範例")
    
    choice = input("\n請輸入選擇 (1-7, 預設為 1): ").strip() or "1"
    
    if choice == "1":
        asyncio.run(run_all_examples())
    elif choice == "2":
        asyncio.run(example_1_nvidia_stock_analysis())
    elif choice == "3":
        asyncio.run(example_2_ai_industry_trends())
    elif choice == "4":
        asyncio.run(example_3_brand_monitoring())
    elif choice == "5":
        asyncio.run(example_4_academic_research())
    elif choice == "6":
        asyncio.run(example_5_financial_analysis())
    elif choice == "7":
        show_cli_examples()
    else:
        print("無效選擇，運行所有範例...")
        asyncio.run(run_all_examples())
