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

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置输出
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, 
    f"ai_news_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# 初始化模型
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
        
        # Generate initial summary
        initial_summary = summarizer(
            full_text[:1024],  # Limit input length
            max_length=150,
            min_length=50,
            do_sample=False
        )
        summary_en = initial_summary[0]['summary_text'] if initial_summary else ""
        
        # Extract key points (using the full text)
        key_points_en = []
        chunk_size = 1024
        chunks = [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]
        
        for chunk in chunks:
            point_summary = summarizer(
                chunk,
                max_length=50,  # Shorter summaries for key points
                min_length=20,
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
    """Process a single site"""
    page = None
    try:
        # 为每个网站创建新的页面
        page = await browser.new_page()
        
        # 获取文章列表
        html = await crawler.get_content(page, site_config["url"], site_config)
        articles = await crawler.parse_articles(html, site_config)
        
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            return []
        
        processed_articles = []
        for article in articles:
            try:
                # 为每篇文章创建新的页面
                article_page = await browser.new_page()
                try:
                    content = await crawler.get_article_content(article_page, article["link"], site_config)
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
                finally:
                    # 确保关闭文章页面
                    await article_page.close()
                
                await asyncio.sleep(2)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
        
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []
    finally:
        # 确保关闭主页面
        if page:
            await page.close()

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
                            "summary_en": summary["en"],
                            "summary_zh": summary["zh"],
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
    return await process_api_site(session, site_name, site_config, crawler)  # RSS processing is similar to API

async def process_source(name: str, config: dict) -> List[Dict]:
    try:
        logger.info(f"Processing source: {name}")
        
        # Initialize appropriate crawler
        if config.get("is_rss"):
            crawler = RSSCrawler()
        elif config.get("is_api"):
            crawler = APICrawler()
        else:
            crawler = BlogCrawler()

        # Get articles
        articles = await crawler.get_articles(name, config)
        if not articles:
            logger.warning(f"No articles found for {name}")
            return []

        # Process each article
        processed_articles = []
        async with aiohttp.ClientSession() as session:
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                
                for article in articles:
                    try:
                        # Get content based on crawler type
                        if config.get("is_rss"):
                            content = await crawler.get_article_content(session, article["link"], config)
                        elif config.get("is_api"):
                            content = article.get("content")
                        else:
                            content = await crawler.get_article_content(page, article["link"], config)
                        
                        if content:
                            # Clean content
                            cleaned_content = ' '.join(str(content).split())
                            
                            # Calculate appropriate max_length based on input length
                            input_length = len(cleaned_content.split())
                            max_length = min(150, max(40, input_length // 2))  # Set max_length to half of input length
                            
                            try:
                                # Generate summary with dynamic max_length
                                summary_result = summarizer(
                                    cleaned_content[:1024],  # Limit input to 1024 chars
                                    max_length=max_length,
                                    min_length=min(30, max_length - 10),  # Ensure min_length is less than max_length
                                    do_sample=False
                                )
                                
                                # Extract summary text
                                summary_en = summary_result[0]['summary_text'] if summary_result else ""
                                
                                # Generate Chinese translation
                                if summary_en:
                                    translation_result = translator(summary_en)
                                    summary_zh = translation_result[0]['translation_text'] if translation_result else ""
                                else:
                                    summary_zh = ""
                                
                                processed_articles.append({
                                    "title": article["title"],
                                    "link": article["link"],
                                    "content": cleaned_content,  
                                    "summary_en": summary_en,
                                    "summary_zh": summary_zh,
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"Processed article: {article['title']}")
                                
                            except Exception as e:
                                logger.error(f"Error processing summaries: {e}")
                                processed_articles.append({
                                    "title": article["title"],
                                    "link": article["link"],
                                    "content": cleaned_content,  
                                    "summary_en": "",
                                    "summary_zh": "",
                                    "timestamp": datetime.now().isoformat()
                                })
                        else:
                            logger.warning(f"No content found for article: {article['title']}")
                            
                    except Exception as e:
                        logger.error(f"Error processing article {article.get('title', 'Unknown')}: {e}")
                        continue
                        
                await browser.close()
                
        logger.info(f"Successfully processed {len(processed_articles)} articles from {name}")
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing source {name}: {e}")
        return []

async def main():
    # Initialize playwright browser
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            # 获取用户输入
            print("Available categories:")
            for category in CATEGORIES:
                print(f"- {category}")
            
            selected_categories = input("Enter categories to crawl (comma-separated): ").split(",")
            selected_categories = [cat.strip() for cat in selected_categories]
            
            # 初始化爬虫
            blog_crawler = BlogCrawler()
            rss_crawler = RSSCrawler()
            api_crawler = APICrawler()
            # 收集选定的源
            sources = {}
            for category in selected_categories:
                if category in CATEGORIES:
                    sources.update(CATEGORIES[category])
            
            # 使用 aiohttp session 替代 playwright
            async with aiohttp.ClientSession() as session:
                # 串行处理网站
                all_articles = []
                total_sites = len(sources)
                
                print(f"\nProcessing {total_sites} sites:")
                for i, (site_name, site_config) in enumerate(sources.items(), 1):
                    print(f"\n[{i}/{total_sites}] Processing {site_name}...")
                    
                    # 选择合适的爬虫
                    if site_config.get("is_api"):
                        crawler = api_crawler
                        result = await process_api_site(session, site_name, site_config, crawler)
                    elif site_config.get("is_rss"):
                        crawler = rss_crawler
                        result = await process_rss_site(session, site_name, site_config, crawler)
                    else:
                        # 只有真正需要浏览器的网站才使用 playwright
                        crawler = blog_crawler
                        result = await process_site(browser, site_name, site_config, crawler)
                    
                    if isinstance(result, list):
                        all_articles.extend(result)
                    
                    await asyncio.sleep(2)
                
                logger.info(f"Total articles processed: {len(all_articles)}")
                
                # 保存结果
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