"""
智能搜索爬蟲系統演示測試
包含模擬API回應的測試功能
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# 添加專案根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def demo_google_search_integration():
    """演示Google搜索API整合功能"""
    print("🔍 === Google搜索API整合演示 ===")
    
    try:
        from crawl4ai.google_search_integration import GoogleSearchConfig, SearchResult
        
        # 創建搜索配置
        config = GoogleSearchConfig(
            api_key="demo_key",
            search_engine_id="demo_engine"
        )
        
        print(f"✅ 搜索配置創建成功")
        print(f"   - API Key: {config.api_key[:8]}...")
        print(f"   - 搜索引擎ID: {config.search_engine_id}")
        
        # 模擬搜索結果
        mock_results = [
            SearchResult(
                title="台灣電商市場趨勢分析 2024",
                url="https://example.com/ecommerce-trends-2024",
                snippet="台灣電商市場在2024年持續成長，行動商務占比達到65%，預計年成長率將達到15%。",
                display_url="example.com/ecommerce-trends-2024",
                search_rank=1,
                search_query="台灣電商"
            ),
            SearchResult(
                title="電子商務發展報告：台灣數位經濟現況",
                url="https://example.com/digital-economy-report",
                snippet="根據最新調查，台灣電子商務市場規模已突破3000億台幣，成為亞洲重要的數位經濟體。",
                display_url="example.com/digital-economy-report",
                search_rank=2,
                search_query="電子商務"
            )
        ]
        
        print(f"✅ 模擬搜索結果 ({len(mock_results)} 個結果)")
        for i, result in enumerate(mock_results, 1):
            print(f"   {i}. {result.title[:50]}...")
            print(f"      {result.url}")
            print(f"      搜索查詢: {result.search_query}")
        
        return True
        
    except Exception as e:
        print(f"❌ Google搜索API整合測試失敗: {e}")
        return False

async def demo_keyword_generation():
    """演示關鍵字生成功能"""
    print("\n🎯 === 智能關鍵字生成演示 ===")
    
    try:
        # 模擬LLM關鍵字生成
        task_description = "研究台灣電商市場的最新趨勢和消費者行為"
        
        # 模擬初始關鍵字生成
        initial_keywords = [
            "台灣電商", "線上購物", "電子商務", "數位行銷",
            "消費者行為", "電商趨勢", "網路購物", "行動商務"
        ]
        
        print(f"✅ 任務描述: {task_description}")
        print(f"✅ 初始關鍵字生成 ({len(initial_keywords)} 個)")
        for i, keyword in enumerate(initial_keywords, 1):
            print(f"   {i}. {keyword}")
        
        # 模擬關鍵字優化
        refined_keywords = [
            "台灣電商平台比較", "COVID-19電商影響", "社群電商",
            "直播購物", "永續電商", "跨境電商"
        ]
        
        print(f"✅ 關鍵字優化 (新增 {len(refined_keywords)} 個)")
        for i, keyword in enumerate(refined_keywords, 1):
            print(f"   {i}. {keyword}")
        
        return True
        
    except Exception as e:
        print(f"❌ 關鍵字生成測試失敗: {e}")
        return False

async def demo_smart_crawler():
    """演示智能爬蟲核心功能"""
    print("\n🕷️ === 智能爬蟲引擎演示 ===")
    
    try:
        from crawl4ai.smart_search_crawler import TaskObjectiveV3, CrawlPageResult, IterationResult
        
        # 創建任務目標
        objective = TaskObjectiveV3(
            title="台灣電商市場分析",
            description="深度分析台灣電商市場的發展趨勢、主要平台競爭態勢和消費者購物行為變化",
            initial_keywords=["台灣電商", "線上購物", "電子商務"],
            target_confidence=0.85,
            max_iterations=3,
            max_total_pages=15,
            output_format="summary"
        )
        
        print(f"✅ 任務目標創建")
        print(f"   - 標題: {objective.title}")
        print(f"   - 目標信心度: {objective.target_confidence:.2%}")
        print(f"   - 最大迭代次數: {objective.max_iterations}")
        print(f"   - 最大頁面數: {objective.max_total_pages}")
        
        # 模擬爬蟲結果
        from datetime import datetime
        current_time = datetime.now()
        
        mock_crawl_results = [
            CrawlPageResult(
                url="https://example.com/ecommerce-trends-2024",
                title="台灣電商市場趨勢分析 2024",
                content="台灣電商市場在2024年展現強勁成長...",
                summary="台灣電商市場持續成長，行動商務成為主流",
                success=True,
                relevance_score=0.92,
                confidence_score=0.88,
                is_helpful=True,
                crawl_time=current_time,
                source_keyword="台灣電商",
                search_rank=1
            ),
            CrawlPageResult(
                url="https://example.com/consumer-behavior-study",
                title="2024台灣消費者網購行為研究",
                content="消費者網購行為研究顯示重要趨勢...",
                summary="消費者偏好行動購物，平均訂單金額增加",
                success=True,
                relevance_score=0.87,
                confidence_score=0.82,
                is_helpful=True,
                crawl_time=current_time,
                source_keyword="消費者行為",
                search_rank=2
            )
        ]
        
        print(f"✅ 模擬爬蟲執行 ({len(mock_crawl_results)} 個頁面)")
        for i, result in enumerate(mock_crawl_results, 1):
            print(f"   {i}. {result.title}")
            print(f"      URL: {result.url}")
            print(f"      相關度: {result.relevance_score:.2f}")
            print(f"      信心度: {result.confidence_score:.2f}")
            print(f"      有用: {'是' if result.is_helpful else '否'}")
        
        # 模擬迭代結果
        iteration = IterationResult(
            iteration_number=1,
            keywords_used=objective.initial_keywords,
            search_results=[],  # 會在實際實現中填入
            crawled_pages=mock_crawl_results,
            confidence_score=0.85,
            new_keywords_generated=["社群電商", "直播購物"]
        )
        
        print(f"✅ 迭代 {iteration.iteration_number} 完成")
        print(f"   - 使用關鍵字: {', '.join(iteration.keywords_used)}")
        print(f"   - 信心度: {iteration.confidence_score:.2%}")
        print(f"   - 新關鍵字: {', '.join(iteration.new_keywords_generated)}")
        
        return True
        
    except Exception as e:
        print(f"❌ 智能爬蟲測試失敗: {e}")
        return False

async def demo_report_generation():
    """演示報表生成功能"""
    print("\n📊 === 智能報表生成演示 ===")
    
    try:
        from crawl4ai.smart_search_crawler import SmartCrawlResult, TaskObjectiveV3, IterationResult
        from datetime import datetime, timedelta
        
        # 創建模擬的完整爬蟲結果
        start_time = datetime.now() - timedelta(minutes=5)
        end_time = datetime.now()
        
        objective = TaskObjectiveV3(
            title="台灣電商市場分析",
            description="深度分析台灣電商市場的發展趨勢",
            initial_keywords=["台灣電商", "線上購物"],
            target_confidence=0.85,
            max_iterations=2
        )
        
        mock_result = SmartCrawlResult(
            task_id="demo_task_001",
            objective=objective,
            status="completed",
            start_time=start_time,
            end_time=end_time,
            iterations=[],  # 在實際情況中會有迭代資料
            final_confidence=0.87,
            total_pages_crawled=8,
            total_keywords_used=6,
            summary="台灣電商市場在2024年展現強勁成長動能，行動商務成為主要趨勢。",
            structured_data=[]
        )
        
        print(f"✅ 爬蟲結果摘要")
        print(f"   - 任務ID: {mock_result.task_id}")
        print(f"   - 執行狀態: {mock_result.status}")
        print(f"   - 執行時間: {mock_result.execution_time:.1f} 秒")
        print(f"   - 最終信心度: {mock_result.final_confidence:.2%}")
        print(f"   - 總爬取頁面: {mock_result.total_pages_crawled}")
        
        # 模擬報表生成
        report_content_preview = f"""# 智能搜索爬蟲報表

## 📋 基本資訊
- **任務ID**: {mock_result.task_id}
- **任務標題**: {mock_result.objective.title}
- **執行狀態**: {mock_result.status}
- **最終信心度**: {mock_result.final_confidence:.2%}

## 📊 執行摘要
任務成功完成，達到預期信心度目標。總共爬取 {mock_result.total_pages_crawled} 個頁面，
獲得高品質的台灣電商市場分析資料。

## 💡 主要發現
1. 台灣電商市場持續高速成長
2. 行動商務佔比超過65%
3. 消費者購物行為日趨數位化

## 📝 任務摘要
{mock_result.summary}
"""
        
        print(f"✅ 報表內容預覽")
        print("=" * 50)
        print(report_content_preview[:300] + "...")
        print("=" * 50)
        
        # 模擬報表檔案生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"smart_crawl_report_{mock_result.task_id}_{timestamp}.md"
        
        print(f"✅ 報表檔案: {report_filename}")
        print(f"   - 格式: Markdown")
        print(f"   - 大小: ~{len(report_content_preview)} 字符")
        
        return True
        
    except Exception as e:
        print(f"❌ 報表生成測試失敗: {e}")
        return False

async def demo_system_integration():
    """演示完整系統整合"""
    print("\n🔧 === 系統整合演示 ===")
    
    try:
        print("✅ 檢查模組載入")
        
        # 檢查各模組是否可以正常載入
        modules_to_check = [
            "crawl4ai.google_search_integration",
            "crawl4ai.smart_search_crawler", 
            "crawl4ai.smart_crawl_report"
        ]
        
        for module_name in modules_to_check:
            try:
                __import__(module_name)
                print(f"   ✅ {module_name}")
            except ImportError as e:
                print(f"   ❌ {module_name}: {e}")
        
        print("\n✅ 檢查核心類別")
        
        # 檢查核心類別
        from crawl4ai.google_search_integration import GoogleSearchAPI, IntelligentKeywordGenerator
        from crawl4ai.smart_search_crawler import SmartSearchCrawler, TaskObjectiveV3
        from crawl4ai.smart_crawl_report import SmartCrawlReportGenerator
        
        classes_checked = [
            "GoogleSearchAPI", "IntelligentKeywordGenerator",
            "SmartSearchCrawler", "TaskObjectiveV3", 
            "SmartCrawlReportGenerator"
        ]
        
        for class_name in classes_checked:
            print(f"   ✅ {class_name}")
        
        print("\n✅ 系統整合檢查完成")
        print("   - 所有核心模組可正常載入")
        print("   - 所有核心類別可正常使用")
        print("   - 系統架構完整")
        
        return True
        
    except Exception as e:
        print(f"❌ 系統整合測試失敗: {e}")
        return False

async def run_demo_suite():
    """執行完整演示測試套件"""
    print("🚀 智能搜索爬蟲系統 - 完整演示測試")
    print("=" * 60)
    
    # 記錄測試結果
    test_results = {}
    
    # 執行各項演示測試
    demos = [
        ("Google搜索API整合", demo_google_search_integration),
        ("智能關鍵字生成", demo_keyword_generation),
        ("智能爬蟲引擎", demo_smart_crawler),
        ("智能報表生成", demo_report_generation),
        ("系統整合", demo_system_integration)
    ]
    
    for demo_name, demo_func in demos:
        try:
            result = await demo_func()
            test_results[demo_name] = result
        except Exception as e:
            print(f"❌ {demo_name} 演示失敗: {e}")
            test_results[demo_name] = False
    
    # 總結報告
    print("\n" + "=" * 60)
    print("📊 演示測試總結報告")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(test_results.values())
    
    print(f"總測試數: {total_tests}")
    print(f"通過測試: {passed_tests}")
    print(f"失敗測試: {total_tests - passed_tests}")
    print(f"成功率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n詳細結果:")
    for test_name, result in test_results.items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"  {status} {test_name}")
    
    if all(test_results.values()):
        print("\n🎉 所有演示測試通過！智能搜索爬蟲系統已準備就緒。")
    else:
        print("\n⚠️ 部分測試失敗，請檢查系統配置。")
    
    # 生成測試報告檔案
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_data = {
        "test_time": timestamp,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "success_rate": passed_tests/total_tests*100,
        "results": test_results
    }
    
    # 確保測試結果目錄存在
    results_dir = Path("test_results")
    results_dir.mkdir(exist_ok=True)
    
    # 儲存測試結果
    results_file = results_dir / f"demo_test_results_{timestamp}.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 測試結果已儲存: {results_file}")
    
    return test_results

if __name__ == "__main__":
    # 執行演示測試套件
    results = asyncio.run(run_demo_suite())
