from bs4 import BeautifulSoup
import logging
import feedparser
from .base_crawler import BaseCrawler
from playwright.async_api import async_playwright
import asyncio

logger = logging.getLogger(__name__)

class RSSCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self._article_contents = {}  # Store contents by URL
    
    async def get_content(self, session, url: str, site_config: dict) -> str:
        """Get RSS content"""
        # If site requires browser handling
        if site_config.get("requires_browser"):
            logger.info(f"Using browser to fetch RSS feed: {url}")
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    
                    # Set headers
                    await page.set_extra_http_headers({
                        "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
                        "Accept-Language": "en-US,en;q=0.9",
                    })
                    
                    logger.info(f"Loading page: {url}")
                    response = await page.goto(url, wait_until="networkidle")
                    
                    if response:
                        logger.info(f"Response status: {response.status}")
                        if response.ok:
                            content = await page.content()
                            logger.debug(f"Content preview: {content[:200]}")
                            return content
                        else:
                            logger.error(f"Failed to load RSS feed: {response.status}")
                    
                    await browser.close()
                    return None
                    
            except Exception as e:
                logger.error(f"Error fetching RSS with browser: {str(e)}")
                return None
                
        # Regular RSS handling for other sites
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            }
            
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.error(f"RSS request failed with status {response.status}")
                        return None
            except Exception as e:
                logger.error(f"Error fetching RSS feed: {str(e)}")
                return None

    async def parse_articles(self, feed_content: str, site_config: dict) -> list:
        """Parse RSS article list"""
        if not feed_content:
            return []
            
        articles = []
        try:
            feed = feedparser.parse(feed_content)
            items = feed.entries
            logger.info(f"Found {len(items)} items in RSS feed")
            
            for item in items[:self.articles_per_site]:
                title = item.get('title')
                link = item.get('link')
                
                # More robust content extraction
                content = None
                if hasattr(item, 'content_encoded'):
                    content = item.content_encoded
                elif 'content' in item:
                    if isinstance(item.content, list):
                        content = item.content[0].get('value', '')
                    else:
                        content = item.content
                elif hasattr(item, 'encoded'):
                    content = item.encoded
                elif 'description' in item:
                    content = item.description
                elif 'summary' in item:
                    content = item.summary
                
                if title and link:
                    article = {
                        "title": title,
                        "link": link,
                        "content": content
                    }
                    # Store content for later retrieval if it exists
                    if content and len(str(content).strip()) > 100:
                        self._article_contents[link] = content
                        logger.debug(f"Stored content for article: {title} ({len(str(content))} chars)")
                    articles.append(article)
                    logger.info(f"Found article: {title}")
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
        return articles

    async def get_article_content(self, session, url: str, site_config: dict) -> str:
        """Get article content"""
        try:
            # Check stored content first
            if url in self._article_contents:
                content = self._article_contents.pop(url)  # Remove after use
                logger.info(f"Using stored content for URL: {url}")
                return content

            # Special handling for OpenAI blog
            if "openai.com" in url:
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    
                    # Set headers and cookies
                    await page.set_extra_http_headers({
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": "https://openai.com/",
                        "Origin": "https://openai.com",
                        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"'
                    })
                    
                    try:
                        # First wait for initial page load with shorter timeout
                        response = await page.goto(url, timeout=10000)
                        if not response or not response.ok:
                            logger.error(f"Initial page load failed: {response.status if response else 'No response'}")
                            return None

                        # Then wait for network idle separately with retry logic
                        for attempt in range(3):
                            try:
                                await page.wait_for_load_state("networkidle", timeout=10000)
                                break
                            except Exception as e:
                                if attempt == 2:  # Last attempt
                                    logger.warning(f"Network idle timeout, proceeding anyway: {e}")
                                await asyncio.sleep(2)

                        # Try multiple content selectors
                        content = None
                        selectors = [
                            "article.prose",
                            "main article",
                            "div.prose",
                            "[class*='article']",
                            "main"
                        ]
                        
                        for selector in selectors:
                            try:
                                await page.wait_for_selector(selector, timeout=5000)
                                content_elem = await page.query_selector(selector)
                                if content_elem:
                                    content = await content_elem.inner_text()
                                    if content and len(content.strip()) > 100:  # Minimum content length
                                        break
                            except Exception:
                                continue

                        if content:
                            return content
                        else:
                            # Fallback: get all text from body
                            body = await page.query_selector("body")
                            if body:
                                return await body.inner_text()
                            
                    except Exception as e:
                        logger.error(f"Error fetching OpenAI content: {e}", exc_info=True)
                    finally:
                        await browser.close()
                    
            # Special handling for Hugging Face blog
            if "huggingface.co" in url:
                logger.info(f"Starting Hugging Face content fetch for: {url}")
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                        
                        # Try multiple content selectors
                        for selector in ["main article", "div.prose", ".markdown", "main div[class*='prose']"]:
                            try:
                                content_elem = await page.query_selector(selector)
                                if content_elem:
                                    text = await content_elem.inner_text()
                                    if text and len(text.strip()) > 100:  # Ensure we have substantial content
                                        logger.info(f"Found Hugging Face content with selector: {selector}")
                                        return text.strip()
                            except Exception as e:
                                logger.debug(f"Hugging Face selector {selector} failed: {e}")
                                continue
                            
                    except Exception as e:
                        logger.error(f"Error getting Hugging Face content: {e}")
                    finally:
                        await browser.close()

            # For Google Research blog
            if "blog.research.google" in url:
                # Use the content from RSS feed if available
                if hasattr(self, '_current_article_content') and self._current_article_content:
                    content = self._current_article_content
                    self._current_article_content = None  # Clear for next article
                    return content
                
                # Fallback to fetching from the webpage if RSS content not available
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        if html:
                            soup = BeautifulSoup(html, 'html.parser')
                            content_elem = soup.select_one(".post-content, article, .post-body")
                            if content_elem:
                                return content_elem.get_text(strip=True)
                            
            # For RSS feeds that include content in the feed
            if hasattr(self, '_current_article_content') and self._current_article_content:
                content = self._current_article_content
                self._current_article_content = None
                return content
            
            # Default content fetching for other sites
            async with session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    if html:
                        soup = BeautifulSoup(html, 'html.parser')
                        content_elem = soup.select_one(site_config["content_selector"])
                        if content_elem:
                            return content_elem.get_text(strip=True)
                        
        except Exception as e:
            logger.error(f"Error fetching article content: {e}", exc_info=True)
        return None

