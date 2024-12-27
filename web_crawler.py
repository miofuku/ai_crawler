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
        "article_selector": "div.article-item",
        "title_selector": "h2.article-title",
        "link_selector": "h2.article-title a",
        "content_selector": "div.article-content"
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
        "article_selector": ".feed__item",
        "title_selector": ".feed__title",
        "link_selector": ".feed__title a",
        "content_selector": ".article__body"
    }
}

MAX_RETRIES = 3
ARTICLES_PER_SITE = 5
OUTPUT_FILE = "output/ai_news_summary.json"

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

async def get_page_content(page, url: str) -> str:
    """Get page content using Playwright with improved waiting"""
    try:
        await page.goto(
            url, 
            wait_until="networkidle",
            timeout=90000,
        )
        
        # 等待页面加载
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)
        
        # 更多的滚动和等待
        for _ in range(5):  # 增加滚动次数
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # 尝试点击"加载更多"按钮（如果存在）
            try:
                load_more_button = page.locator("text=Load more")
                if await load_more_button.is_visible():
                    await load_more_button.click()
                    await asyncio.sleep(2)
            except Exception:
                pass
        
        # 最终等待
        await asyncio.sleep(2)
        
        return await page.content()
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None

async def get_article_links_async(page, site_name: str, site_config: dict) -> List[Dict]:
    """Get article links with improved error handling and debugging"""
    html = await get_page_content(page, site_config["url"])
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    # 尝试多个选择器组合
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
            # 尝试多种方式获取标题和链接
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

async def extract_article_content_async(page, url: str, content_selector: str) -> str:
    """Extract article content"""
    html = await get_page_content(page, url)
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
    """Process all articles from a single site"""
    try:
        page = await browser.new_page()
        articles = await get_article_links_async(page, site_name, site_config)
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            await page.close()
            return []
            
        processed_articles = []
        for article in articles:
            try:
                content = await extract_article_content_async(
                    page,
                    article["link"], 
                    site_config["content_selector"]
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
                        logger.info(f"Processed article: {article['title']}")
                await asyncio.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
                continue
        
        await page.close()
        return processed_articles
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []

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
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        
        tasks = []
        for site_name, site_config in SITES.items():
            logger.info(f"Processing {site_name}...")
            tasks.append(process_site(context, site_name, site_config))
        
        results = await asyncio.gather(*tasks)
        all_articles = [article for site_articles in results for article in site_articles]
        
        logger.info(f"Total articles processed: {len(all_articles)}")
        
        output = {
            "timestamp": datetime.now().isoformat(),
            "articles": all_articles
        }
        
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        try:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            logger.info(f"Results saved to {OUTPUT_FILE}")
        except Exception as e:
            logger.error(f"Error saving to file: {e}")
        
        await context.close()
        await browser.close()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
