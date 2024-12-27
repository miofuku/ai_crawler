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
from playwright.async_api import async_playwright
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Website configuration - Selectors validated with developer tools
SITES = {
    "VentureBeat": {
        "url": "https://venturebeat.com/category/ai/",
        "article_selector": ".ArticleList__articleItem",
        "title_selector": ".ArticleListItem__title",
        "link_selector": ".ArticleListItem__title a",
        "content_selector": ".article-content",
        "wait_for": ".ArticleList",
        "load_more_selector": ".ArticleList__loadMore"
    },
    "Wired": {
        "url": "https://www.wired.com/tag/artificial-intelligence/",
        "article_selector": "div.summary-item",
        "title_selector": "h3",
        "link_selector": "a.summary-item-tracking__hed-link",
        "content_selector": ".article__body"
    },
    "TheVerge": {
        "url": "https://www.theverge.com/ai-artificial-intelligence",
        "article_selector": "h2.font-polysans",
        "title_selector": "a",
        "link_selector": "a",
        "content_selector": "div.duet--article--article-body-component"
    },
    "TechXplore": {
        "url": "https://techxplore.com/machine-learning-ai-news/",
        "article_selector": "article.sorted-article",
        "title_selector": ".news-title",
        "link_selector": ".news-title a",
        "content_selector": ".article-body"
    },
    "MIT Technology Review": {
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/",
        "article_selector": ".card--article, .card--articleModule",
        "title_selector": ".card--articleModule__title, .card--article__title, h2, h3",
        "link_selector": "a.card--articleModule__link, a.card--article__link, h2 a, h3 a",
        "content_selector": ".contentArticle__content, .article__content, article",
        "wait_for": ".topic__articles, .topic-page",
        "load_more_selector": "button.load-more, .infinite-scroll-component"
    }
}

MAX_RETRIES = 3
ARTICLES_PER_SITE = 5
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, 
    f"ai_news_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# Translation model
MODELS = {
    "summarizer": {
        "name": "sshleifer/distilbart-cnn-12-6",
        "max_length": 1024,
        "min_length": 30,
        "length_penalty": 2.0,
        "default_max_length": 150,
        "default_min_length": 30,
    },
    "translator": {
        "name": "Helsinki-NLP/opus-mt-en-zh",
        "max_length": 800,
    }
}

# Initialize models
summarizer = pipeline(
    "summarization", 
    model=MODELS["summarizer"]["name"],
    device=-1
)

translator = pipeline(
    "translation", 
    model=MODELS["translator"]["name"],
    tokenizer=MODELS["translator"]["name"],
    device=-1
)

async def get_page_content(page, url: str, site_config: dict) -> str:
    """Get page content with site-specific handling"""
    for attempt in range(MAX_RETRIES):
        try:
            response = await page.goto(
                url, 
                wait_until="networkidle",
                timeout=90000,
            )
            
            if response is None or not response.ok:
                raise Exception(f"Failed to load page: {response.status if response else 'No response'}")
            
            # MIT Technology Review special handling
            if "technologyreview.com" in url:
                # Wait for article list to load
                try:
                    await page.wait_for_selector(".topic__articles, .topic-page", timeout=30000)
                except Exception as e:
                    logger.warning(f"Wait for article list failed: {e}")
                
                # Handle possible subscription popup
                try:
                    close_button = page.locator("button[aria-label='Close']")
                    if await close_button.is_visible():
                        await close_button.click()
                except Exception:
                    pass
                
                # Scroll multiple times to load more content
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Try clicking the "Load more" button
                    try:
                        load_more = page.locator("button.load-more, .infinite-scroll-component")
                        if await load_more.is_visible():
                            await load_more.click()
                            await asyncio.sleep(2)
                    except Exception:
                        pass
                
                # Output page source for debugging
                content = await page.content()
                logger.debug(f"MIT Technology Review page source preview: {content[:1000]}")
                return content
            
            # Special handling for VentureBeat
            if "venturebeat.com" in url:
                # Wait for article list to load
                try:
                    await page.wait_for_selector(".ArticleList", timeout=30000)
                except Exception as e:
                    logger.warning(f"Wait for ArticleList failed: {e}")
                
                # Scroll multiple times to load more content
                for _ in range(5):  # Increase scroll attempts
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Click "Load more" button
                    try:
                        load_more = page.locator(".ArticleList__loadMore")
                        if await load_more.is_visible():
                            await load_more.click()
                            await asyncio.sleep(2)
                    except Exception:
                        pass
            
            # Regular wait and scroll
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)
            
            # Output page source for debugging
            if "venturebeat.com" in url:
                content = await page.content()
                logger.debug(f"VentureBeat page source preview: {content[:1000]}")
                return content
            
            return await page.content()
            
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}/{MAX_RETRIES} failed for {url}: {e}")
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All attempts failed for {url}")
                return None

async def get_article_links_async(page, site_name: str, site_config: dict) -> List[Dict]:
    """Get article links with improved error handling and debugging"""
    html = await get_page_content(page, site_config["url"], site_config)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    # Try multiple selector combinations
    selectors = [
        site_config['article_selector'],
        f"main {site_config['article_selector']}",
        f"div {site_config['article_selector']}",
        f".content {site_config['article_selector']}"
    ]
    
    elements = []
    for selector in selectors:
        elements = soup.select(selector)
        if elements:
            logger.info(f"Found {len(elements)} elements matching selector '{selector}' for {site_name}")
            break
    
    if not elements:
        logger.debug(f"No elements found for {site_name} with any selector")
        logger.debug(f"Page classes found: {[c for c in soup.find_all(class_=True)[:5]]}")
    
    for article in elements[:ARTICLES_PER_SITE]:
        try:
            # Try multiple ways to get title and link
            title_elem = (
                article.select_one(site_config["title_selector"]) or 
                article.find("h2") or 
                article.find("h3") or
                article.find("a")
            )
            
            link_elem = (
                article.select_one(site_config["link_selector"]) or 
                title_elem.find("a") if title_elem else None or
                article.find("a")
            )
            
            if title_elem and link_elem:
                link = link_elem.get('href')
                title = title_elem.text.strip()
                
                if not title or not link:
                    logger.debug(f"Empty title or link for article in {site_name}")
                    continue
                    
                if not link.startswith('http'):
                    link = urljoin(site_config["url"], link)
                
                logger.debug(f"Found article: {title} - {link}")
                articles.append({
                    "title": title,
                    "link": link
                })
            else:
                logger.debug(f"Missing title ({bool(title_elem)}) or link ({bool(link_elem)}) for {site_name}")
                if title_elem:
                    logger.debug(f"Title element content: {title_elem}")
        except Exception as e:
            logger.error(f"Error parsing article from {site_name}: {e}")
    
    logger.info(f"Found {len(articles)} valid articles for {site_name}")
    return articles

async def extract_article_content_async(page, url: str, content_selector: str, site_config: dict) -> str:
    """Extract article content"""
    html = await get_page_content(page, url, site_config)
    if not html:
        return None
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        content_div = soup.select_one(content_selector)
        if content_div:
            # Remove unwanted elements
            for elem in content_div.select('script, style, iframe, nav, header, footer'):
                elem.decompose()
            
            paragraphs = content_div.find_all('p')
            content = " ".join([p.text.strip() for p in paragraphs if p.text.strip()])
            
            logger.debug(f"Extracted content length: {len(content)} characters")
            return content if content else None
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
    return None

def translate_text(text: str) -> str:
    """Improved translation function with better quality"""
    try:
        max_length = MODELS["translator"]["max_length"]
        parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        translated_parts = []
        
        for part in parts:
            for attempt in range(3):
                try:
                    translation = translator(
                        part,
                        max_length=max_length,
                        num_beams=5,  # Increase beam search width
                        length_penalty=1.5,
                        do_sample=False,
                        early_stopping=True,
                        no_repeat_ngram_size=3  # Avoid repeating phrases
                    )[0]['translation_text']
                    translated_parts.append(translation)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Translation failed after 3 attempts: {e}")
                        translated_parts.append(part)
                    time.sleep(1)
        
        return "".join(translated_parts)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text

async def process_site(browser, site_name: str, site_config: dict) -> List[Dict]:
    """Process site with improved error handling and retries"""
    processed_articles = []
    retry_queue = []  
    
    try:
        page = await browser.new_page()
        articles = await get_article_links_async(page, site_name, site_config)
        
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            await page.close()
            return []
        
        for article in articles:
            try:
                content = await extract_article_content_async(
                    page,
                    article["link"], 
                    site_config["content_selector"],
                    site_config
                )
                
                if not content:
                    retry_queue.append(article)
                    continue
                
                summary = summarize_and_translate(content)
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
                
                await asyncio.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
                retry_queue.append(article)
        
        # Process retry queue
        if retry_queue:
            logger.info(f"Retrying {len(retry_queue)} failed articles for {site_name}")
            for article in retry_queue:
                for attempt in range(MAX_RETRIES):
                    try:
                        content = await extract_article_content_async(
                            page,
                            article["link"], 
                            site_config["content_selector"],
                            site_config
                        )
                        
                        if content:
                            summary = summarize_and_translate(content)
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
                                logger.info(f"Successfully retried article: {article['title']}")
                                break
                        
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    except Exception as e:
                        logger.error(f"Retry {attempt + 1} failed for {article['link']}: {e}")
        
        await page.close()
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return processed_articles

def summarize_and_translate(content: str) -> Dict[str, str]:
    """Summarize content and translate to Chinese with improved quality"""
    if not content or len(content.split()) < 30:
        return None
        
    try:
        # Increase minimum output length to get a more detailed summary
        max_length = MODELS["summarizer"]["max_length"]
        parts = [content[i:i+max_length] for i in range(0, len(content), max_length)]
        summary_parts = []
        
        for part in parts[:3]:  # Process the first three parts
            if len(part.split()) >= 30:
                # Adjust length limit to ensure summary contains enough information
                input_length = len(part.split())
                max_output_length = max(
                    min(input_length * 0.4, 250),  # Increase maximum length to 250
                    MODELS["summarizer"]["default_min_length"]
                )
                min_output_length = max(
                    min(input_length * 0.2, 100),  # Ensure minimum length is at least 20% of the original text
                    MODELS["summarizer"]["default_min_length"]
                )
                
                # Use stricter generation parameters to get a more complete summary
                summary = summarizer(
                    part, 
                    max_length=int(max_output_length),
                    min_length=int(min_output_length),
                    length_penalty=2.0,  # Increase length penalty to encourage longer summaries
                    num_beams=5,  # Increase beam search width
                    early_stopping=True,
                    do_sample=False,
                    repetition_penalty=1.2,  # Add repetition penalty
                    no_repeat_ngram_size=3  # Avoid repeating phrases
                )[0]['summary_text']
                
                # Make sure the summary contains key information
                if not any(keyword in summary.lower() for keyword in ['ai', 'artificial intelligence', 'ml', 'machine learning']):
                    # If the summary does not contain keywords, try extracting sentences from the beginning
                    first_sentences = '. '.join(part.split('.')[:3])
                    if len(first_sentences.split()) > 30:
                        summary = first_sentences
                
                summary_parts.append(summary)
        
        summary_en = " ".join(summary_parts)
        
        # Improve translation quality
        summary_zh = translate_text(summary_en)
        
        return {
            "en": summary_en,
            "zh": summary_zh
        }
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

async def main_async():
    async with async_playwright() as p:
        for attempt in range(MAX_RETRIES):
            try:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-gpu',
                        '--disable-dev-shm-usage',
                        '--disable-setuid-sandbox',
                        '--no-sandbox',
                    ]
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                )
                
                tasks = []
                for site_name, site_config in SITES.items():
                    logger.info(f"Processing {site_name}...")
                    tasks.append(process_site(context, site_name, site_config))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results, filtering out exceptions
                all_articles = []
                for result in results:
                    if isinstance(result, list):
                        all_articles.extend(result)
                    else:
                        logger.error(f"Task failed with error: {result}")
                
                logger.info(f"Total articles processed: {len(all_articles)}")
                
                output = {
                    "timestamp": datetime.now().isoformat(),
                    "articles": all_articles
                }
                
                os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
                
                with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)
                logger.info(f"Results saved to {OUTPUT_FILE}")
                
                await context.close()
                await browser.close()
                break
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < MAX_RETRIES - 1:
                    wait_time = 2 ** attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("All attempts failed")
                    raise

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
