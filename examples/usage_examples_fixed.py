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
from crawl4ai import LLMConfig
from crawl4ai.google_search_integration import GoogleSearchConfig

# 從環境變數載入設定
def load_config():
    """載入環境變數配置"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("💡 建議安裝 python-dotenv: pip install python-dotenv")
    
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

def create_crawler(config):
    """創建智能搜索爬蟲實例"""
    llm_config = LLMConfig(
        base_url=config['llm_base_url'],
        api_token=config['llm_api_key']
    )
    
    google_config = GoogleSearchConfig(
        api_key=config['google_api_key'],
        search_engine_id=config['google_engine_id']
    )
    
    return SmartSearchCrawler(
        llm_config=llm_config,
        google_config=google_config
    )

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
    crawler = create_crawler(config)
    
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
        import traceback
        traceback.print_exc()
        return None

async def example_2_structured_data():
    """範例2: 結構化資料收集 - 台灣新創公司"""
    print("\n🏢 === 範例2: 台灣新創公司資料收集 ===\n")
    
    # 載入配置
    config = load_config()
    if not config:
        return
    
    # 定義任務目標
    objective = TaskObjectiveV3(
        title="台灣新創公司資料庫建立",
        description="收集台灣新創公司的詳細資料，建立結構化的新創公司資料庫",
        initial_keywords=["台灣新創", "startup Taiwan", "創業公司", "新創投資"],
        target_confidence=0.8,
        max_iterations=2,
        max_total_pages=12,
        output_format="structured"
    )
    
    # 初始化爬蟲
    crawler = create_crawler(config)
    
    try:
        print(f"🚀 開始執行任務: {objective.title}")
        print(f"🔍 初始關鍵字: {', '.join(objective.initial_keywords)}")
        print()
        
        # 執行智能爬蟲
        result = await crawler.execute_smart_crawl(objective)
        
        # 顯示執行結果
        print(f"✅ 任務完成!")
        print(f"📊 最終信心度: {result.final_confidence:.2%}")
        print(f"📄 收集到的資料數量: {len(result.structured_data)}")
        print()
        
        # 顯示部分結構化資料
        if result.structured_data:
            print("🏢 收集到的公司資料 (前3筆):")
            for i, company in enumerate(result.structured_data[:3], 1):
                print(f"\n{i}. {company.get('title', 'N/A')}")
                print(f"   來源: {company.get('source_url', 'N/A')}")
                print(f"   相關度: {company.get('relevance_score', 0):.2f}")
        
        # 生成報表
        report_dir = Path("reports")
        report_dir.mkdir(exist_ok=True)
        report_path = generate_crawl_report(result, str(report_dir))
        print(f"\n📋 報表已生成: {report_path}")
        
        return result
        
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        import traceback
        traceback.print_exc()
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
    crawler = create_crawler(config)
    
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
        print(f"🔑 關鍵字擴展: {len(result.objective.initial_keywords)} → {result.total_keywords_used} 個")
        
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
        import traceback
        traceback.print_exc()
        return None

async def demo_mode_example():
    """示範模式範例 - 不需要真實API金鑰"""
    print("\n🎭 === 示範模式 (無需API金鑰) ===\n")
    
    # 使用示範配置
    demo_config = {
        'google_api_key': 'demo_google_key',
        'google_engine_id': 'demo_engine_id',
        'llm_api_key': 'demo_llm_key',
        'llm_base_url': 'http://localhost:1234/v1'  # 本地LLM服務
    }
    
    try:
        # 創建示範爬蟲
        crawler = create_crawler(demo_config)
        
        # 定義簡單任務
        objective = TaskObjectiveV3(
            title="示範任務",
            description="這是一個示範任務",
            initial_keywords=["demo", "test"],
            target_confidence=0.7,
            max_iterations=1,
            max_total_pages=5
        )
        
        print(f"🚀 執行示範任務: {objective.title}")
        print(f"📝 這個示範會展示系統架構，但不會進行實際API調用")
        
        # 顯示系統架構
        print(f"\n🏗️ 系統架構展示:")
        print(f"  ✅ LLM配置: {crawler.llm_config.base_url}")
        print(f"  ✅ Google配置: {crawler.google_config.search_engine_id}")
        print(f"  ✅ 關鍵字生成器: 已載入")
        print(f"  ✅ 搜索API: 已初始化")
        
        print(f"\n💡 要執行實際爬蟲，請設定正確的API金鑰")
        
        return True
        
    except Exception as e:
        print(f"❌ 示範模式失敗: {e}")
        return False

async def run_examples():
    """執行範例選擇"""
    print("🚀 智能搜索爬蟲系統 - 使用範例")
    print("=" * 60)
    
    # 檢查API配置
    config = load_config()
    
    if not config:
        print("\n🎭 由於缺少API配置，將執行示範模式")
        await demo_mode_example()
        
        print("\n" + "=" * 60)
        print("📝 完整設定指引:")
        print("=" * 60)
        print("1. 取得 Google Custom Search API:")
        print("   - 前往 https://console.cloud.google.com/")
        print("   - 啟用 Custom Search API")
        print("   - 創建自定義搜索引擎: https://cse.google.com/")
        print()
        print("2. 取得 LLM API 金鑰:")
        print("   - OpenAI: https://platform.openai.com/api-keys")
        print("   - 或其他相容的LLM服務")
        print()
        print("3. 設定環境變數:")
        print("   - 複製 .env.template 為 .env")
        print("   - 填入實際的API金鑰")
        print("   - 重新執行此腳本")
        
        return []
    
    # 有API配置，執行實際範例
    print("✅ API配置完成，開始執行實際範例")
    
    results = []
    
    # 依序執行範例
    examples = [
        ("台灣電商市場研究", example_1_market_research),
        ("台灣新創公司資料", example_2_structured_data),
        ("AI工具市場分析", example_3_competitive_analysis)
    ]
    
    for name, example_func in examples:
        print(f"\n正在執行: {name}")
        result = await example_func()
        if result:
            results.append((name, result))
        
        # 在範例之間暫停
        print("\n" + "-" * 40)
        await asyncio.sleep(1)
    
    # 總結報告
    if results:
        print("\n" + "=" * 60)
        print("📊 範例執行總結")
        print("=" * 60)
        
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
    
    return results

if __name__ == "__main__":
    # 執行使用範例
    asyncio.run(run_examples())
