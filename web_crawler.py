import requests
from bs4 import BeautifulSoup
from transformers import pipeline
import json
from datetime import datetime
import time
from typing import List, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Website configuration
SITES = {
    "VentureBeat": {
        "url": "https://venturebeat.com/ai/",
        "article_selector": "article.ArticleListing",
        "title_selector": "h2.article-title",
        "link_selector": "a.article-link",
        "content_selector": "div.article-content"
    },
    "AINews": {
        "url": "https://aibusiness.com/",
        "article_selector": "div.post-item",
        "title_selector": "h2.entry-title",
        "link_selector": "a",
        "content_selector": "div.entry-content"
    }
}

MAX_RETRIES = 3
ARTICLES_PER_SITE = 5
OUTPUT_FILE = "ai_news_summary.json"

def fetch_content(url: str, retries: int = MAX_RETRIES) -> str:
    """Fetch webpage content with retry mechanism"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                logger.error(f"Error fetching {url}: {e}")
                return None
            time.sleep(2 ** attempt)  # Exponential backoff
    return None

def get_article_links(site_name: str, site_config: dict) -> List[Dict]:
    """Get the latest article links and titles"""
    html = fetch_content(site_config["url"])
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    articles = []
    
    for article in soup.select(site_config["article_selector"])[:ARTICLES_PER_SITE]:
        try:
            title_elem = article.select_one(site_config["title_selector"])
            link_elem = article.select_one(site_config["link_selector"])
            
            if title_elem and link_elem:
                link = link_elem.get('href')
                if not link.startswith('http'):
                    link = site_config["url"].rstrip('/') + link
                
                articles.append({
                    "title": title_elem.text.strip(),
                    "link": link
                })
        except Exception as e:
            logger.error(f"Error parsing article from {site_name}: {e}")
            
    return articles

def extract_article_content(url: str, content_selector: str) -> str:
    """Extract article content"""
    html = fetch_content(url)
    if not html:
        return None
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        content_div = soup.select_one(content_selector)
        if content_div:
            paragraphs = content_div.find_all('p')
            return " ".join([p.text.strip() for p in paragraphs])
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {e}")
    return None

def summarize_content(content: str) -> str:
    """Summarize content using AI model"""
    if not content or len(content.split()) < 30:
        return None
        
    try:
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        summary = summarizer(content, max_length=130, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

def save_to_file(data: List[Dict]) -> None:
    """Save results to file"""
    output = {
        "timestamp": datetime.now().isoformat(),
        "articles": data
    }
    
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        logger.info(f"Results saved to {OUTPUT_FILE}")
    except Exception as e:
        logger.error(f"Error saving to file: {e}")

def main():
    all_articles = []
    
    for site_name, site_config in SITES.items():
        logger.info(f"Processing {site_name}...")
        articles = get_article_links(site_name, site_config)
        
        for article in articles:
            content = extract_article_content(article["link"], site_config["content_selector"])
            if content:
                summary = summarize_content(content)
                if summary:
                    article_data = {
                        "site": site_name,
                        "title": article["title"],
                        "link": article["link"],
                        "summary": summary
                    }
                    all_articles.append(article_data)
                    logger.info(f"Processed article: {article['title']}")
            time.sleep(1)  # Avoid too frequent requests
            
    save_to_file(all_articles)

if __name__ == "__main__":
    main()
