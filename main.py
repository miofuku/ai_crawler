import asyncio
import json
import os
from datetime import datetime
import logging
from typing import List, Dict
from sources import (
    ai_company_blogs,
    web3_blogs,
    research_blogs,
    chinese_blogs,
    arxiv_sources,
    paper_analysis
)
from crawlers.base_crawler import BaseCrawler
from crawlers.blog_crawler import BlogCrawler
from crawlers.rss_crawler import RSSCrawler
from crawlers.api_crawler import APICrawler
from playwright.async_api import async_playwright
import aiohttp
from processor import process_site, process_api_site, process_rss_site
from summarizer import summarizer, translator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure output
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, 
    f"ai_news_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

CATEGORIES = {
    "ai": ai_company_blogs.AI_COMPANY_BLOGS,
    "web3": web3_blogs.WEB3_BLOGS,
    "research": research_blogs.RESEARCH_BLOGS,
    "chinese": chinese_blogs.CHINESE_BLOGS,
    "arxiv": arxiv_sources.ARXIV_SOURCES,
    "paper_analysis": paper_analysis.PAPER_ANALYSIS_BLOGS
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            print("Available categories:")
            for category in CATEGORIES:
                print(f"- {category}")
            
            selected_categories = input("Enter categories to crawl (comma-separated): ").split(",")
            selected_categories = [cat.strip() for cat in selected_categories]
            
            blog_crawler = BlogCrawler()
            rss_crawler = RSSCrawler()
            api_crawler = APICrawler()
            
            sources = {}
            for category in selected_categories:
                if category in CATEGORIES:
                    sources.update(CATEGORIES[category])
            
            async with aiohttp.ClientSession() as session:
                all_articles = []
                total_sites = len(sources)
                
                print(f"\nProcessing {total_sites} sites:")
                for i, (site_name, site_config) in enumerate(sources.items(), 1):
                    print(f"\n[{i}/{total_sites}] Processing {site_name}...")
                    
                    if site_config.get("is_api"):
                        crawler = api_crawler
                        result = await process_api_site(session, site_name, site_config, crawler, summarizer, translator)
                    elif site_config.get("is_rss"):
                        crawler = rss_crawler
                        result = await process_rss_site(session, site_name, site_config, crawler, summarizer, translator)
                    else:
                        crawler = blog_crawler
                        result = await process_site(browser, site_name, site_config, crawler, summarizer, translator)
                    
                    if isinstance(result, list):
                        all_articles.extend(result)
                    
                    await asyncio.sleep(2)
                
                logger.info(f"Total articles processed: {len(all_articles)}")
                
                os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "articles": all_articles
                    }, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Results saved to {OUTPUT_FILE}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main()) 