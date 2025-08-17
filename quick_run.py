import asyncio
from crawl4ai import quick_crawl_task
import logging
logging.basicConfig(level=logging.INFO)

async def main():
    result = await quick_crawl_task(
        title="NVIDIA 股價分析",
        description="收集 NVIDIA 股價預測和分析",
        keywords=["NVDA", "股價", "預測", "AI晶片"]
    )
    print(f"完成！爬取了 {result.crawled_pages} 個頁面")

asyncio.run(main())