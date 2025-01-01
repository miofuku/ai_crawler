"""主程序"""
import asyncio
from sources import (
    ai_company_blogs,
    web3_blogs,
    research_blogs,
    chinese_blogs,
    arxiv_sources
)
from crawlers import BlogCrawler, RSSCrawler

CATEGORIES = {
    "ai": ai_company_blogs.AI_COMPANY_BLOGS,
    "web3": web3_blogs.WEB3_BLOGS,
    "research": research_blogs.RESEARCH_BLOGS,
    "chinese": chinese_blogs.CHINESE_BLOGS,
    "arxiv": arxiv_sources.ARXIV_SOURCES
}

async def main():
    # 获取用户输入
    print("Available categories:")
    for category in CATEGORIES:
        print(f"- {category}")
    
    selected_categories = input("Enter categories to crawl (comma-separated): ").split(",")
    selected_categories = [cat.strip() for cat in selected_categories]
    
    # 初始化爬虫
    blog_crawler = BlogCrawler()
    rss_crawler = RSSCrawler()
    
    # 收集选定的源
    sources = {}
    for category in selected_categories:
        if category in CATEGORIES:
            sources.update(CATEGORIES[category])
    
    # 开始爬取
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        results = []
        
        for site_name, site_config in sources.items():
            crawler = rss_crawler if site_config.get("is_rss") else blog_crawler
            # 执行爬取逻辑...
        
        # 保存结果...

if __name__ == "__main__":
    asyncio.run(main()) 