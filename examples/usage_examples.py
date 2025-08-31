"""
智能搜索爬蟲系統使用範例
演示如何使用智能搜索爬蟲進行實際任務
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path

# 導入智能搜索爬蟲模組
from crawl4ai.smart_search_crawler import SmartSearchCrawler, TaskObjectiveV3
from crawl4ai.smart_crawl_report import generate_crawl_report

# 從環境變數載入設定
def load_config():
    """載入環境變數配置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    config = {
        'google_api_key': os.getenv('GOOGLE_SEARCH_API_KEY'),
        'google_engine_id': os.getenv('GOOGLE_SEARCH_ENGINE_ID'), 
        'llm_api_key': os.getenv('LLM_API_KEY'),
        'llm_base_url': os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')
    }
    
    # 檢查必要的API金鑰
    missing_keys = [k for k, v in config.items() if v is None and k != 'llm_base_url']
    if missing_keys:
        print(f"❌ 缺少必要的環境變數: {', '.join(missing_keys)}")
        print("請設定 .env 檔案或環境變數")
        return None
    
    return config

async def example_1_market_research():
    """範例1: 台灣電商市場研究"""
    print("📈 === 範例1: 台灣電商市場研究 ===\n")
    
    # 載入配置
    config = load_config()
    if not config:
        return
    
    # 定義任務目標
    objective = TaskObjectiveV3(
        title="台灣電商市場趨勢分析2024",
        description="深度分析台灣電商市場的最新發展趨勢，包括市場規模、主要平台競爭態勢、消費者行為變化、以及未來發展機會",
        initial_keywords=["台灣電商", "線上購物", "電子商務", "數位行銷"],
        target_confidence=0.85,
        max_iterations=3,
        max_total_pages=15,
        output_format="summary"
    )
    
    # 初始化爬蟲
    crawler = SmartSearchCrawler(
        google_api_key=config['google_api_key'],
        google_engine_id=config['google_engine_id'],
        llm_api_key=config['llm_api_key'],
        llm_base_url=config['llm_base_url']
    )
    
    try:
        print(f"🚀 開始執行任務: {objective.title}")
        print(f"🎯 目標信心度: {objective.target_confidence:.2%}")
        print(f"🔍 初始關鍵字: {', '.join(objective.initial_keywords)}")
        print()
        
        # 執行智能爬蟲
        result = await crawler.execute_smart_crawl(objective)
        
        # 顯示執行結果
        print(f"✅ 任務完成!")
        print(f"📊 最終信心度: {result.final_confidence:.2%}")
        print(f"⏱️ 執行時間: {result.execution_time:.1f}秒")
        print(f"📄 總爬取頁面: {result.total_pages_crawled}")
        print(f"🔑 使用關鍵字數: {result.total_keywords_used}")
        print()
        
        # 生成報表
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        report_path = generate_crawl_report(result, str(report_dir))
        print(f"📋 報表已生成: {report_path}")
        
        # 顯示摘要
        if result.summary:
            print(f"\n📝 任務摘要:")
            print(result.summary[:300] + "..." if len(result.summary) > 300 else result.summary)
        
        return result
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return None

async def example_2_structured_data():
    """範例2: 結構化資料收集 - 台灣新創公司"""
    print("\n🏢 === 範例2: 台灣新創公司資料收集 ===\n")
    
    # 載入配置
    config = load_config()
    if not config:
        return
    
    # 定義結構化資料架構
    structured_schema = {
        "company_name": "公司名稱",
        "industry": "產業領域",
        "funding_stage": "資金階段",
        "funding_amount": "融資金額",
        "founded_year": "成立年份",
        "employees": "員工數量",
        "description": "公司描述",
        "website": "官方網站"
    }
    
    # 定義任務目標
    objective = TaskObjectiveV3(
        title="台灣新創公司資料庫建立",
        description="收集台灣新創公司的詳細資料，建立結構化的新創公司資料庫",
        initial_keywords=["台灣新創", "startup Taiwan", "創業公司", "新創投資"],
        target_confidence=0.8,
        max_iterations=2,
        max_total_pages=12,
        output_format="structured",
        structured_schema=structured_schema
    )
    
    # 初始化爬蟲
    crawler = SmartSearchCrawler(
        google_api_key=config['google_api_key'],
        google_engine_id=config['google_engine_id'],
        llm_api_key=config['llm_api_key'],
        llm_base_url=config['llm_base_url']
    )
    
    try:
        print(f"🚀 開始執行任務: {objective.title}")
        print(f"📊 資料架構: {len(structured_schema)} 個欄位")
        print(f"🔍 初始關鍵字: {', '.join(objective.initial_keywords)}")
        print()
        
        # 執行智能爬蟲
        result = await crawler.execute_smart_crawl(objective)
        
        # 顯示執行結果
        print(f"✅ 任務完成!")
        print(f"📊 最終信心度: {result.final_confidence:.2%}")
        print(f"📄 收集到的公司數量: {len(result.structured_data)}")
        print()
        
        # 顯示部分結構化資料
        if result.structured_data:
            print("🏢 收集到的公司資料 (前3筆):")
            for i, company in enumerate(result.structured_data[:3], 1):
                print(f"\n{i}. {company.get('company_name', 'N/A')}")
                print(f"   產業: {company.get('industry', 'N/A')}")
                print(f"   階段: {company.get('funding_stage', 'N/A')}")
                print(f"   網站: {company.get('website', 'N/A')}")
        
        # 生成報表
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        report_path = generate_crawl_report(result, str(report_dir))
        print(f"\n📋 報表已生成: {report_path}")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return None

async def example_3_competitive_analysis():
    """範例3: 競爭對手分析 - AI工具市場"""
    print("\n🤖 === 範例3: AI工具市場競爭分析 ===\n")
    
    # 載入配置
    config = load_config()
    if not config:
        return
    
    # 定義任務目標
    objective = TaskObjectiveV3(
        title="AI工具市場競爭態勢分析",
        description="分析AI工具市場的主要競爭者、產品特色、市場定位和發展策略",
        initial_keywords=["AI工具", "人工智能平台", "AI SaaS", "機器學習工具"],
        target_confidence=0.85,
        max_iterations=3,
        max_total_pages=18,
        enable_keyword_refinement=True,
        output_format="summary"
    )
    
    # 初始化爬蟲
    crawler = SmartSearchCrawler(
        google_api_key=config['google_api_key'],
        google_engine_id=config['google_engine_id'],
        llm_api_key=config['llm_api_key'],
        llm_base_url=config['llm_base_url']
    )
    
    try:
        print(f"🚀 開始執行任務: {objective.title}")
        print(f"🎯 啟用關鍵字優化: {objective.enable_keyword_refinement}")
        print(f"🔍 初始關鍵字: {', '.join(objective.initial_keywords)}")
        print()
        
        # 執行智能爬蟲
        result = await crawler.execute_smart_crawl(objective)
        
        # 顯示執行結果
        print(f"✅ 任務完成!")
        print(f"📊 執行了 {len(result.iterations)} 次迭代")
        print(f"📈 信心度提升: {result.iterations[0].confidence_score:.2%} → {result.final_confidence:.2%}")
        print(f"🔑 關鍵字擴展: {result.objective.initial_keywords} → {result.total_keywords_used} 個")
        
        # 顯示關鍵字演化
        print(f"\n🔍 關鍵字演化過程:")
        for i, iteration in enumerate(result.iterations, 1):
            print(f"  迭代 {i}: {', '.join(iteration.keywords_used)}")
            if iteration.new_keywords_generated:
                print(f"    新增: {', '.join(iteration.new_keywords_generated)}")
        
        # 生成報表
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        report_path = generate_crawl_report(result, str(report_dir))
        print(f"\n📋 報表已生成: {report_path}")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        return None

async def run_all_examples():
    """執行所有範例"""
    print("🚀 智能搜索爬蟲系統 - 使用範例展示")
    print("=" * 60)
    
    # 檢查API配置
    config = load_config()
    if not config:
        print("\n📝 設定指引:")
        print("1. 複製 .env.template 為 .env")
        print("2. 填入您的 Google Search API 金鑰")
        print("3. 填入您的 LLM API 金鑰")
        print("4. 重新執行此腳本")
        return
    
    results = []
    
    # 執行範例1: 市場研究
    result1 = await example_1_market_research()
    if result1:
        results.append(("台灣電商市場研究", result1))
    
    # 執行範例2: 結構化資料收集
    result2 = await example_2_structured_data()
    if result2:
        results.append(("台灣新創公司資料", result2))
    
    # 執行範例3: 競爭分析
    result3 = await example_3_competitive_analysis()
    if result3:
        results.append(("AI工具市場分析", result3))
    
    # 總結報告
    print("\n" + "=" * 60)
    print("📊 範例執行總結")
    print("=" * 60)
    
    if results:
        total_pages = sum(r[1].total_pages_crawled for r in results)
        total_time = sum(r[1].execution_time for r in results)
        avg_confidence = sum(r[1].final_confidence for r in results) / len(results)
        
        print(f"✅ 成功執行 {len(results)} 個範例")
        print(f"📄 總共爬取 {total_pages} 個頁面")
        print(f"⏱️ 總執行時間 {total_time:.1f} 秒")
        print(f"📊 平均信心度 {avg_confidence:.2%}")
        
        print(f"\n📋 各範例結果:")
        for name, result in results:
            print(f"  • {name}: {result.final_confidence:.2%} 信心度, {result.total_pages_crawled} 頁面")
        
        print(f"\n🎉 所有範例執行完成！報表已生成在 reports/ 目錄中。")
    else:
        print("❌ 沒有成功執行的範例，請檢查API配置。")

if __name__ == "__main__":
    # 執行所有使用範例
    asyncio.run(run_all_examples())
