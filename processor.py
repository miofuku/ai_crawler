import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from summarizer import summarize_content

logger = logging.getLogger(__name__)

async def process_site(browser, site_name: str, site_config: dict, crawler, summarizer, translator) -> List[Dict]:
    """Process a single blog-based site"""
    try:
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
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Error processing article {article['link']}: {e}", exc_info=True)
            
            return processed_articles
            
        finally:
            await page.close()
            
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}", exc_info=True)
        return []

async def process_api_site(session, site_name: str, site_config: dict, crawler, summarizer, translator) -> List[Dict]:
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
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
        
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []

async def process_rss_site(session, site_name: str, site_config: dict, crawler, summarizer, translator) -> List[Dict]:
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
                
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}", exc_info=True)
        
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}", exc_info=True)
        return []