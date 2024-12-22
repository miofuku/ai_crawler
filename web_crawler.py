import aiohttp
import asyncio
from bs4 import BeautifulSoup
from transformers import pipeline
import json
from datetime import datetime
from typing import List, Dict
import logging
from urllib.parse import urljoin
import time
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Website configuration
SITES = {
    "VentureBeat": {
        "url": "https://venturebeat.com/ai/",
        "article_selector": "article.article-block",
        "title_selector": "h2 a",
        "link_selector": "h2 a",
        "content_selector": "div.article-content"
    },
    "TechCrunch": {
        "url": "https://techcrunch.com/category/artificial-intelligence/",
        "article_selector": "div.post-block",
        "title_selector": "a.post-block__title__link",
        "link_selector": "a.post-block__title__link",
        "content_selector": "div.article-content"
    },
    "TheVerge": {
        "url": "https://www.theverge.com/ai-artificial-intelligence",
        "article_selector": "h2.font-polysans",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": "div.duet--article--article-body-component"
    }
}

MAX_RETRIES = 3
ARTICLES_PER_SITE = 5
OUTPUT_FILE = "output/ai_news_summary.json"

# Proxy configuration
PROXIES = {
    'http': 'http://proxy.crawlera.com:8010',  # Crawlera Proxy
    'https': 'http://proxy.crawlera.com:8010',
    # Free Proxy
    # 'http': 'http://free-proxy.cz:8080',
    # 'https': 'http://free-proxy.cz:8080'
}
USE_PROXY = False  # Configure whether to use proxy

# Proxy authentication
PROXY_AUTH = {
    'username': 'your_username',
    'password': 'your_password'
}

# Translation model
translator = pipeline("translation", 
                     model="Helsinki-NLP/opus-mt-en-zh",
                     tokenizer="Helsinki-NLP/opus-mt-en-zh",
                     device=-1)  # -1 indicates using CPU, set to 0 if using GPU

async def fetch_content_async(url: str, session: aiohttp.ClientSession) -> str:
    """Async fetch webpage content"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",  # Support brotli compression
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "DNT": "1"
    }
    
    await asyncio.sleep(random.uniform(1, 3))
    
    if USE_PROXY and PROXY_AUTH:
        auth = aiohttp.BasicAuth(PROXY_AUTH['username'], PROXY_AUTH['password'])
    else:
        auth = None
    
    timeout = aiohttp.ClientTimeout(total=30)
    
    for attempt in range(MAX_RETRIES):
        try:
            proxy = PROXIES['http'] if USE_PROXY else None
            async with session.get(
                url, 
                headers=headers, 
                proxy=proxy, 
                proxy_auth=auth, 
                timeout=timeout,
                ssl=False  # Add this option to handle some SSL issues
            ) as response:
                response.raise_for_status()
                return await response.text()
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Error fetching {url}: {e}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None

async def get_article_links_async(site_name: str, site_config: dict, session: aiohttp.ClientSession) -> List[Dict]:
    """Async get article links"""
    html = await fetch_content_async(site_config["url"], session)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    logger.debug(f"Found {len(soup.select(site_config['article_selector']))} articles for {site_name}")
    
    for article in soup.select(site_config["article_selector"])[:ARTICLES_PER_SITE]:
        try:
            title_elem = article.select_one(site_config["title_selector"])
            link_elem = article.select_one(site_config["link_selector"])
            
            if title_elem and link_elem:
                link = link_elem.get('href')
                title = title_elem.text.strip()
                
                if not title or not link:
                    continue
                    
                if not link.startswith('http'):
                    link = urljoin(site_config["url"], link)
                
                logger.debug(f"Found article: {title} - {link}")
                
                articles.append({
                    "title": title,
                    "link": link
                })
            else:
                logger.debug(f"Missing title or link element for article in {site_name}")
        except Exception as e:
            logger.error(f"Error parsing article from {site_name}: {e}")
    
    logger.info(f"Found {len(articles)} valid articles for {site_name}")
    return articles

async def extract_article_content_async(url: str, content_selector: str, session: aiohttp.ClientSession) -> str:
    """Async extract article content"""
    html = await fetch_content_async(url, session)
    if not html:
        return None
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        content_div = soup.select_one(content_selector)
        if content_div:
            for elem in content_div.select('script, style, iframe, nav'):
                elem.decompose()
            
            paragraphs = content_div.find_all('p')
            content = " ".join([p.text.strip() for p in paragraphs if p.text.strip()])
            
            logger.debug(f"Extracted content length: {len(content)} characters")
            return content if content else None
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
    return None

def translate_text(text: str) -> str:
    """Translate text to Chinese"""
    try:
        # Translate in segments, reduce the maximum length to improve stability
        max_length = 400
        parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        translated_parts = []
        
        for part in parts:
            # Add retry mechanism
            for attempt in range(3):
                try:
                    translation = translator(part, max_length=800)[0]['translation_text']
                    translated_parts.append(translation)
                    break
                except Exception as e:
                    if attempt == 2:  # Last attempt failed
                        logger.error(f"Translation failed after 3 attempts: {e}")
                        translated_parts.append(part)  # Fail to keep original
                    time.sleep(1)
        
        return "".join(translated_parts)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text  # Return original if error

def summarize_and_translate(content: str) -> Dict[str, str]:
    """Summarize content and translate to Chinese"""
    if not content or len(content.split()) < 30:
        return None
        
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        summary_en = summarizer(content, max_length=130, min_length=30, do_sample=False)[0]['summary_text']
        summary_zh = translate_text(summary_en)
        
        return {
            "en": summary_en,
            "zh": summary_zh
        }
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

async def process_site(site_name: str, site_config: dict, session: aiohttp.ClientSession) -> List[Dict]:
    """Process all articles from a single site"""
    try:
        articles = await get_article_links_async(site_name, site_config, session)
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            return []
            
        processed_articles = []
        for article in articles:
            try:
                content = await extract_article_content_async(
                    article["link"], 
                    site_config["content_selector"], 
                    session
                )
                if content:
                    summaries = summarize_and_translate(content)
                    if summaries:
                        article_data = {
                            "site": site_name,
                            "title": article["title"],
                            "link": article["link"],
                            "summary_en": summaries["en"],
                            "summary_zh": summaries["zh"],
                            "timestamp": datetime.now().isoformat()
                        }
                        processed_articles.append(article_data)
                        logger.info(f"Processed article: {article['title']}")
                await asyncio.sleep(random.uniform(2, 4))  # Random delay
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
                continue
                
        return processed_articles
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []

async def main_async():
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector, trust_env=True) as session:
        tasks = []
        for site_name, site_config in SITES.items():
            logger.info(f"Processing {site_name}...")
            tasks.append(process_site(site_name, site_config, session))
        
        results = await asyncio.gather(*tasks)
        all_articles = [article for site_articles in results for article in site_articles]
        
        logger.info(f"Total articles processed: {len(all_articles)}")
        for article in all_articles:
            logger.info(f"Article from {article['site']}: {article['title']}")
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "articles": all_articles
        }
        
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            logger.info(f"Results saved to {OUTPUT_FILE}")
        except Exception as e:
            logger.error(f"Error saving to file: {e}")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
