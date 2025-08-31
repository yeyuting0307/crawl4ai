"""
智能搜索爬蟲報表生成模組
生成詳細的Markdown格式分析報表
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .smart_search_crawler import SmartCrawlResult, IterationResult, CrawlPageResult

class SmartCrawlReportGenerator:
    """智能爬蟲報表生成器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_report(self, result: SmartCrawlResult, output_file: Optional[str] = None) -> str:
        """生成完整的Markdown報表"""
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"smart_crawl_report_{result.task_id}_{timestamp}.md"
        
        output_path = self.output_dir / output_file
        
        # 生成報表內容
        report_content = self._create_full_report(result)
        
        # 寫入檔案
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        
        return str(output_path)
    
    def _create_full_report(self, result: SmartCrawlResult) -> str:
        """創建完整報表內容"""
        
        report = f"""# 智能搜索爬蟲報表

## 📋 基本資訊

- **任務ID**: {result.task_id}
- **任務標題**: {result.objective.title}
- **任務描述**: {result.objective.description}
- **執行狀態**: {result.status}
- **開始時間**: {result.start_time.strftime('%Y-%m-%d %H:%M:%S') if result.start_time else 'N/A'}
- **結束時間**: {result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else 'N/A'}
- **執行時間**: {result.execution_time:.1f} 秒

## 📊 執行摘要

| 指標 | 數值 |
|------|------|
| 迭代次數 | {len(result.iterations)} |
| 總爬取頁面 | {result.total_pages_crawled} |
| 使用關鍵字總數 | {result.total_keywords_used} |
| 最終信心度 | {result.final_confidence:.2%} |
| 目標信心度 | {result.objective.target_confidence:.2%} |
| 信心度達成 | {'✅ 是' if result.final_confidence >= result.objective.target_confidence else '❌ 否'} |

"""

        # 迭代詳情
        report += self._create_iterations_section(result.iterations)
        
        # 關鍵字分析
        report += self._create_keywords_analysis(result)
        
        # 搜索結果分析
        report += self._create_search_results_analysis(result)
        
        # 爬蟲結果分析
        report += self._create_crawl_results_analysis(result)
        
        # 內容品質分析
        report += self._create_quality_analysis(result)
        
        # 結構化資料或摘要
        if result.objective.output_format == "structured" and result.structured_data:
            report += self._create_structured_data_section(result.structured_data)
        elif result.summary:
            report += self._create_summary_section(result.summary)
        
        # 改進建議
        report += self._create_recommendations_section(result)
        
        # 附錄
        report += self._create_appendix_section(result)
        
        return report
    
    def _create_iterations_section(self, iterations: List[IterationResult]) -> str:
        """創建迭代詳情部分"""
        
        section = "\n## 🔄 迭代執行詳情\n\n"
        
        for i, iteration in enumerate(iterations, 1):
            successful_crawls = [p for p in iteration.crawled_pages if p.success]
            helpful_pages = [p for p in successful_crawls if p.is_helpful]
            
            section += f"### 迭代 {i}\n\n"
            section += f"- **使用關鍵字**: {', '.join(iteration.keywords_used)}\n"
            section += f"- **搜索結果數**: {len(iteration.search_results)}\n"
            section += f"- **爬取頁面數**: {len(iteration.crawled_pages)}\n"
            section += f"- **成功爬取**: {len(successful_crawls)}\n"
            section += f"- **有用頁面**: {len(helpful_pages)}\n"
            section += f"- **迭代信心度**: {iteration.confidence_score:.2%}\n"
            
            if iteration.new_keywords_generated:
                section += f"- **新生成關鍵字**: {', '.join(iteration.new_keywords_generated)}\n"
            
            # 顯示該迭代最有價值的頁面
            if helpful_pages:
                top_pages = sorted(helpful_pages, key=lambda x: x.relevance_score, reverse=True)[:3]
                section += f"\n**該迭代最有價值頁面**:\n"
                for j, page in enumerate(top_pages, 1):
                    section += f"{j}. [{page.title[:60]}...]({page.url}) (相關度: {page.relevance_score:.2f})\n"
            
            section += "\n"
        
        return section
    
    def _create_keywords_analysis(self, result: SmartCrawlResult) -> str:
        """創建關鍵字分析部分"""
        
        section = "\n## 🔍 關鍵字分析\n\n"
        
        # 收集所有關鍵字
        all_keywords = set()
        keyword_evolution = []
        
        for iteration in result.iterations:
            iteration_keywords = set(iteration.keywords_used)
            all_keywords.update(iteration_keywords)
            keyword_evolution.append({
                'iteration': iteration.iteration_number,
                'keywords': iteration.keywords_used,
                'new_keywords': iteration.new_keywords_generated,
                'confidence': iteration.confidence_score
            })
        
        section += f"### 關鍵字統計\n\n"
        section += f"- **初始關鍵字**: {', '.join(result.objective.initial_keywords)}\n"
        section += f"- **總關鍵字數**: {len(all_keywords)}\n"
        section += f"- **關鍵字擴展**: {len(all_keywords) - len(result.objective.initial_keywords)}\n\n"
        
        section += f"### 關鍵字演化\n\n"
        for evo in keyword_evolution:
            section += f"**迭代 {evo['iteration']}** (信心度: {evo['confidence']:.2%})\n"
            section += f"- 使用關鍵字: {', '.join(evo['keywords'])}\n"
            if evo['new_keywords']:
                section += f"- 新增關鍵字: {', '.join(evo['new_keywords'])}\n"
            section += "\n"
        
        return section
    
    def _create_search_results_analysis(self, result: SmartCrawlResult) -> str:
        """創建搜索結果分析部分"""
        
        section = "\n## 🔍 Google搜索結果分析\n\n"
        
        all_search_results = []
        for iteration in result.iterations:
            all_search_results.extend(iteration.search_results)
        
        if not all_search_results:
            return section + "無搜索結果資料\n\n"
        
        # 按域名統計
        domain_stats = {}
        for search_result in all_search_results:
            from urllib.parse import urlparse
            domain = urlparse(search_result.url).netloc
            domain_stats[domain] = domain_stats.get(domain, 0) + 1
        
        section += f"### 搜索結果統計\n\n"
        section += f"- **總搜索結果**: {len(all_search_results)}\n"
        section += f"- **涵蓋域名數**: {len(domain_stats)}\n\n"
        
        section += f"### 主要來源域名\n\n"
        sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        for domain, count in sorted_domains:
            percentage = count / len(all_search_results) * 100
            section += f"- **{domain}**: {count} 結果 ({percentage:.1f}%)\n"
        
        section += "\n"
        return section
    
    def _create_crawl_results_analysis(self, result: SmartCrawlResult) -> str:
        """創建爬蟲結果分析部分"""
        
        section = "\n## 🕷️ 爬蟲結果分析\n\n"
        
        all_crawl_results = []
        for iteration in result.iterations:
            all_crawl_results.extend(iteration.crawled_pages)
        
        if not all_crawl_results:
            return section + "無爬蟲結果資料\n\n"
        
        successful_crawls = [r for r in all_crawl_results if r.success]
        helpful_pages = [r for r in successful_crawls if r.is_helpful]
        
        section += f"### 爬蟲統計\n\n"
        section += f"- **嘗試爬取**: {len(all_crawl_results)} 頁\n"
        section += f"- **成功爬取**: {len(successful_crawls)} 頁 ({len(successful_crawls)/len(all_crawl_results)*100:.1f}%)\n"
        section += f"- **有用頁面**: {len(helpful_pages)} 頁 ({len(helpful_pages)/len(successful_crawls)*100:.1f}%)\n\n"
        
        if successful_crawls:
            avg_relevance = sum(r.relevance_score for r in successful_crawls) / len(successful_crawls)
            avg_confidence = sum(r.confidence_score for r in successful_crawls) / len(successful_crawls)
            
            section += f"### 品質指標\n\n"
            section += f"- **平均相關度**: {avg_relevance:.2f}\n"
            section += f"- **平均信心度**: {avg_confidence:.2f}\n"
            section += f"- **有用頁面比例**: {len(helpful_pages)/len(successful_crawls)*100:.1f}%\n\n"
        
        # 失敗分析
        failed_crawls = [r for r in all_crawl_results if not r.success]
        if failed_crawls:
            section += f"### 失敗分析\n\n"
            section += f"- **失敗頁面數**: {len(failed_crawls)}\n"
            
            # 統計失敗原因
            error_types = {}
            for failed in failed_crawls:
                error = failed.error_message or "未知錯誤"
                error_types[error] = error_types.get(error, 0) + 1
            
            section += "- **主要失敗原因**:\n"
            for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]:
                section += f"  - {error}: {count} 次\n"
            section += "\n"
        
        return section
    
    def _create_quality_analysis(self, result: SmartCrawlResult) -> str:
        """創建內容品質分析部分"""
        
        section = "\n## 📈 內容品質分析\n\n"
        
        all_successful = []
        for iteration in result.iterations:
            all_successful.extend([p for p in iteration.crawled_pages if p.success])
        
        if not all_successful:
            return section + "無有效內容可分析\n\n"
        
        # 相關度分佈
        relevance_ranges = {
            "高相關 (0.8-1.0)": len([p for p in all_successful if p.relevance_score >= 0.8]),
            "中相關 (0.5-0.8)": len([p for p in all_successful if 0.5 <= p.relevance_score < 0.8]),
            "低相關 (0.0-0.5)": len([p for p in all_successful if p.relevance_score < 0.5])
        }
        
        section += "### 相關度分佈\n\n"
        for range_name, count in relevance_ranges.items():
            percentage = count / len(all_successful) * 100
            section += f"- **{range_name}**: {count} 頁 ({percentage:.1f}%)\n"
        
        # 信心度分佈
        confidence_ranges = {
            "高信心 (0.8-1.0)": len([p for p in all_successful if p.confidence_score >= 0.8]),
            "中信心 (0.5-0.8)": len([p for p in all_successful if 0.5 <= p.confidence_score < 0.8]),
            "低信心 (0.0-0.5)": len([p for p in all_successful if p.confidence_score < 0.5])
        }
        
        section += "\n### 信心度分佈\n\n"
        for range_name, count in confidence_ranges.items():
            percentage = count / len(all_successful) * 100
            section += f"- **{range_name}**: {count} 頁 ({percentage:.1f}%)\n"
        
        section += "\n"
        return section
    
    def _create_structured_data_section(self, structured_data: List[Dict]) -> str:
        """創建結構化資料部分"""
        
        section = "\n## 📊 結構化資料摘要\n\n"
        section += f"成功抽取 {len(structured_data)} 條結構化資料\n\n"
        
        # 顯示前5條最相關的資料
        sorted_data = sorted(structured_data, key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        section += "### 最相關資料 (前5條)\n\n"
        for i, data in enumerate(sorted_data[:5], 1):
            section += f"#### {i}. {data.get('title', '無標題')}\n\n"
            section += f"- **來源**: [{data.get('source_url', '')}]({data.get('source_url', '')})\n"
            section += f"- **相關度**: {data.get('relevance_score', 0):.2f}\n"
            section += f"- **搜索關鍵字**: {data.get('source_keyword', '')}\n"
            section += f"- **摘要**: {data.get('summary', '')[:200]}...\n\n"
            
            # 顯示結構化資料內容
            extracted_data = data.get('extracted_data', {})
            if extracted_data:
                section += "**結構化資料**:\n"
                for key, value in extracted_data.items():
                    if isinstance(value, (list, dict)):
                        section += f"- {key}: {str(value)[:100]}...\n"
                    else:
                        section += f"- {key}: {value}\n"
            
            section += "\n---\n\n"
        
        return section
    
    def _create_summary_section(self, summary: str) -> str:
        """創建摘要部分"""
        
        section = "\n## 📝 任務摘要\n\n"
        section += summary + "\n\n"
        
        return section
    
    def _create_recommendations_section(self, result: SmartCrawlResult) -> str:
        """創建改進建議部分"""
        
        section = "\n## 💡 改進建議\n\n"
        
        recommendations = []
        
        # 信心度分析
        if result.final_confidence < result.objective.target_confidence:
            gap = result.objective.target_confidence - result.final_confidence
            recommendations.append(f"信心度未達目標，差距 {gap:.2%}。建議增加迭代次數或調整關鍵字策略。")
        
        # 成功率分析
        all_crawls = []
        for iteration in result.iterations:
            all_crawls.extend(iteration.crawled_pages)
        
        if all_crawls:
            success_rate = len([p for p in all_crawls if p.success]) / len(all_crawls)
            if success_rate < 0.8:
                recommendations.append(f"爬蟲成功率 {success_rate:.1%} 偏低，建議檢查目標網站的反爬蟲策略。")
        
        # 有用頁面分析
        successful_crawls = [p for p in all_crawls if p.success]
        if successful_crawls:
            helpful_rate = len([p for p in successful_crawls if p.is_helpful]) / len(successful_crawls)
            if helpful_rate < 0.5:
                recommendations.append(f"有用頁面比例 {helpful_rate:.1%} 偏低，建議優化關鍵字選擇或調整搜索策略。")
        
        # 關鍵字優化建議
        if result.objective.enable_keyword_refinement:
            total_new_keywords = sum(len(iter.new_keywords_generated) for iter in result.iterations)
            if total_new_keywords == 0:
                recommendations.append("未生成新關鍵字，建議檢查LLM配置或改進關鍵字生成策略。")
        
        # 迭代效率分析
        if len(result.iterations) >= result.objective.max_iterations:
            recommendations.append("達到最大迭代次數限制，如果信心度不足，可考慮增加迭代次數上限。")
        
        if not recommendations:
            recommendations.append("任務執行良好，無特別改進建議。")
        
        for i, rec in enumerate(recommendations, 1):
            section += f"{i}. {rec}\n"
        
        section += "\n"
        return section
    
    def _create_appendix_section(self, result: SmartCrawlResult) -> str:
        """創建附錄部分"""
        
        section = "\n## 📋 附錄\n\n"
        
        section += "### 任務配置\n\n"
        section += f"- **最大迭代次數**: {result.objective.max_iterations}\n"
        section += f"- **目標信心度**: {result.objective.target_confidence:.2%}\n"
        section += f"- **最大頁面數**: {result.objective.max_total_pages}\n"
        section += f"- **每關鍵字最大結果**: {result.objective.max_search_results_per_keyword}\n"
        section += f"- **啟用關鍵字優化**: {'是' if result.objective.enable_keyword_refinement else '否'}\n"
        section += f"- **輸出格式**: {result.objective.output_format}\n"
        section += f"- **時間優先級**: {'是' if result.objective.time_priority else '否'}\n\n"
        
        section += f"### 報表生成資訊\n\n"
        section += f"- **生成時間**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        section += f"- **報表版本**: SmartCrawlReportGenerator v1.0\n\n"
        
        return section

def generate_crawl_report(result: SmartCrawlResult, output_dir: str = "reports") -> str:
    """便利函數：生成爬蟲報表"""
    generator = SmartCrawlReportGenerator(output_dir)
    return generator.generate_report(result)
