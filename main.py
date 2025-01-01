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
from transformers import pipeline
import aiohttp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure output
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, 
    f"ai_news_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Initialize model
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6",
    device=-1
)

translator = pipeline(
    "translation", 
    model="Helsinki-NLP/opus-mt-en-zh",
    tokenizer="Helsinki-NLP/opus-mt-en-zh",
    device=-1
)

CATEGORIES = {
    "ai": ai_company_blogs.AI_COMPANY_BLOGS,
    "web3": web3_blogs.WEB3_BLOGS,
    "research": research_blogs.RESEARCH_BLOGS,
    "chinese": chinese_blogs.CHINESE_BLOGS,
    "arxiv": arxiv_sources.ARXIV_SOURCES,
    "paper_analysis": paper_analysis.PAPER_ANALYSIS_BLOGS
}

async def summarize_content(content: str, summarizer, translator) -> dict:
    """Generate structured summary with key points"""
    if not content:
        return {
            "summary": {"en": "", "zh": ""},
            "key_points": {"en": [], "zh": []}
        }
        
    try:
        # Clean and prepare content
        cleaned_content = ' '.join(str(content).split())
        
        # Split content into paragraphs
        paragraphs = [p.strip() for p in cleaned_content.split('\n') if p.strip()]
        
        # Combine paragraphs into a single text for initial summarization
        full_text = ' '.join(paragraphs)
        
        # Generate initial summary with dynamic max_length
        input_length = len(full_text[:1024])
        max_length = min(150, input_length - 10)  # Ensure output is shorter than input
        min_length = min(50, max_length - 10)  # Ensure min_length is less than max_length

        initial_summary = summarizer(
            full_text[:1024],  # Limit input length
            max_length=max_length,
            min_length=min_length,
            do_sample=False
        )
        summary_en = initial_summary[0]['summary_text'] if initial_summary else ""
        
        # Extract key points (using the full text)
        key_points_en = []
        chunk_size = 1024
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for chunk in chunks:
            chunk_length = len(chunk)
            max_length = min(50, chunk_length - 5)  # Ensure output is shorter than input
            min_length = min(20, max_length - 5)  # Ensure min_length is less than max_length

            point_summary = summarizer(
                chunk,
                max_length=max_length,
                min_length=min_length,
                do_sample=False
            )
            if point_summary:
                key_points_en.append(point_summary[0]['summary_text'])
        
        # Translate summaries
        summary_zh = translator(summary_en)[0]['translation_text'] if summary_en else ""
        key_points_zh = [translator(point)[0]['translation_text'] for point in key_points_en]
        
        return {
            "summary": {
                "en": summary_en,
                "zh": summary_zh
            },
            "key_points": {
                "en": key_points_en,
                "zh": key_points_zh
            }
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_content: {e}")
        return None

async def process_site(browser, site_name: str, site_config: dict, crawler: BaseCrawler) -> List[Dict]:
    """Process a single blog-based site"""
    try:
        # Create a new page for each site
        page = await browser.new_page()
        try:
            html = await crawler.get_content(page, site_config["url"], site_config)
            articles = await crawler.parse_articles(html, site_config)
            
            if not articles:
                logger.warning(f"No articles found for {site_name}")
                return []
                
            processed_articles = []
            for article in articles:
                try:
                    logger.info(f"Processing article: {article['title']}")
                    content = await crawler.get_article_content(page, article["link"], site_config)
                    if content:
                        logger.info(f"Got content for article: {article['title']} ({len(content)} chars)")
                        summary = await summarize_content(content, summarizer, translator)
                        if summary:
                            article_data = {
                                "site": site_name,
                                "title": article["title"],
                                "link": article["link"],
                                "summary_en": summary["summary"]["en"],
                                "summary_zh": summary["summary"]["zh"],
                                "timestamp": datetime.now().isoformat()
                            }
                            processed_articles.append(article_data)
                            logger.info(f"Successfully processed article: {article['title']}")
                        else:
                            logger.error(f"Failed to generate summary for article: {article['title']}")
                    else:
                        logger.error(f"Failed to get content for article: {article['title']}")
                    
                    await asyncio.sleep(2)  # Avoid too frequent requests
                    
                except Exception as e:
                    logger.error(f"Error processing article {article['link']}: {e}", exc_info=True)
            
            return processed_articles
            
        finally:
            await page.close()
            
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}", exc_info=True)
        return []

async def process_api_site(session, site_name: str, site_config: dict, crawler: BaseCrawler) -> List[Dict]:
    """Process a single API-based site"""
    try:
        html = await crawler.get_content(session, site_config["url"], site_config)
        articles = await crawler.parse_articles(html, site_config)
        
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            return []
            
        processed_articles = []
        for article in articles:
            try:
                content = await crawler.get_article_content(session, article["link"], site_config)
                if content:
                    summary = await summarize_content(content, summarizer, translator)
                    if summary:
                        article_data = {
                            "site": site_name,
                            "title": article["title"],
                            "link": article["link"],
                            "summary_en": summary["summary"]["en"],
                            "summary_zh": summary["summary"]["zh"],
                            "timestamp": datetime.now().isoformat()
                        }
                        processed_articles.append(article_data)
                        logger.info(f"Processed article: {article['title']}")
                
                await asyncio.sleep(2)  # Avoid too frequent requests
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
        
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []

async def process_rss_site(session, site_name: str, site_config: dict, crawler: BaseCrawler) -> List[Dict]:
    """Process a single RSS-based site"""
    try:
        html = await crawler.get_content(session, site_config["url"], site_config)
        articles = await crawler.parse_articles(html, site_config)
        
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            return []
            
        processed_articles = []
        for article in articles:
            try:
                logger.info(f"Processing article: {article['title']}")
                content = await crawler.get_article_content(session, article["link"], site_config)
                if content:
                    logger.info(f"Got content for article: {article['title']} ({len(content)} chars)")
                    summary = await summarize_content(content, summarizer, translator)
                    if summary:
                        article_data = {
                            "site": site_name,
                            "title": article["title"],
                            "link": article["link"],
                            "summary_en": summary["summary"]["en"],
                            "summary_zh": summary["summary"]["zh"],
                            "timestamp": datetime.now().isoformat()
                        }
                        processed_articles.append(article_data)
                        logger.info(f"Successfully processed article: {article['title']}")
                    else:
                        logger.error(f"Failed to generate summary for article: {article['title']}")
                else:
                    logger.error(f"Failed to get content for article: {article['title']}")
                
                await asyncio.sleep(2)  # Avoid too frequent requests
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}", exc_info=True)
        
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}", exc_info=True)
        return []

async def main():
    # Initialize playwright browser
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            # Get user input
            print("Available categories:")
            for category in CATEGORIES:
                print(f"- {category}")
            
            selected_categories = input("Enter categories to crawl (comma-separated): ").split(",")
            selected_categories = [cat.strip() for cat in selected_categories]
            
            # Initialize crawlers
            blog_crawler = BlogCrawler()
            rss_crawler = RSSCrawler()
            api_crawler = APICrawler()
            
            # Collect selected sources
            sources = {}
            for category in selected_categories:
                if category in CATEGORIES:
                    sources.update(CATEGORIES[category])
            
            # Use aiohttp session instead of playwright
            async with aiohttp.ClientSession() as session:
                # Process sites serially
                all_articles = []
                total_sites = len(sources)
                
                print(f"\nProcessing {total_sites} sites:")
                for i, (site_name, site_config) in enumerate(sources.items(), 1):
                    print(f"\n[{i}/{total_sites}] Processing {site_name}...")
                    
                    # Choose the appropriate crawler
                    if site_config.get("is_api"):
                        crawler = api_crawler
                        result = await process_api_site(session, site_name, site_config, crawler)
                    elif site_config.get("is_rss"):
                        crawler = rss_crawler
                        result = await process_rss_site(session, site_name, site_config, crawler)
                    else:
                        # Only use playwright for sites that truly require it
                        crawler = blog_crawler
                        result = await process_site(browser, site_name, site_config, crawler)
                    
                    if isinstance(result, list):
                        all_articles.extend(result)
                    
                    await asyncio.sleep(2)
                
                logger.info(f"Total articles processed: {len(all_articles)}")
                
                # Save results
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