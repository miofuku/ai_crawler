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
    """Get page content with improved handling"""
    for attempt in range(MAX_RETRIES):
        try:
            # 设置用户代理和视口
            await page.set_viewport_size({"width": 1920, "height": 1080})
            await page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
            })
            
            # 使用更快的加载策略
            response = await page.goto(
                url, 
                wait_until="domcontentloaded",  # 改为更快的等待条件
                timeout=30000,  # 减少超时时间
            )
            
            if response is None or not response.ok:
                raise Exception(f"Failed to load page: {response.status if response else 'No response'}")
            
            # 等待页面加载完成
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)
            
            # 平滑滚动
            for _ in range(3):
                await page.evaluate("""
                    window.scrollTo({
                        top: document.body.scrollHeight,
                        behavior: 'smooth'
                    });
                """)
                await asyncio.sleep(1)
            
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
    """Summarize content with dynamic length handling"""
    if not content or len(content.split()) < 30:
        return None
        
    try:
        # 检测内容语言
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in content)
        
        if is_chinese:
            # 中文内容处理
            translated_en = translator(
                content, 
                src_lang="zh", 
                tgt_lang="en",
                max_length=1024
            )[0]['translation_text']
            
            # 动态计算摘要长度
            input_length = len(translated_en.split())
            max_output_length = min(input_length, 150)  # 限制最大长度
            min_output_length = min(50, max_output_length - 10)  # 确保最小长度合理
            
            summary_en = summarizer(
                translated_en,
                max_length=max_output_length,
                min_length=min_output_length,
                length_penalty=2.0,
                num_beams=4,
                early_stopping=True
            )[0]['summary_text']
            
            summary_zh = translator(
                summary_en,
                src_lang="en",
                tgt_lang="zh",
                max_length=1024
            )[0]['translation_text']
        else:
            # 英文内容处理
            input_length = len(content.split())
            max_output_length = min(input_length, 150)  # 限制最大长度
            min_output_length = min(50, max_output_length - 10)  # 确保最小长度合理
            
            summary_en = summarizer(
                content,
                max_length=max_output_length,
                min_length=min_output_length,
                length_penalty=2.0,
                num_beams=4,
                early_stopping=True
            )[0]['summary_text']
            
            summary_zh = translator(
                summary_en,
                src_lang="en",
                tgt_lang="zh",
                max_length=1024
            )[0]['translation_text']
        
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
