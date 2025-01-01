from bs4 import BeautifulSoup
import logging
import feedparser
from .base_crawler import BaseCrawler
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class RSSCrawler(BaseCrawler):
    async def get_content(self, session, url: str, site_config: dict) -> str:
        """获取 RSS 内容"""
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

    async def parse_articles(self, xml: str, site_config: dict) -> list:
        """解析 RSS 文章列表"""
        if not xml:
            return []
            
        articles = []
        try:
            soup = BeautifulSoup(xml, 'xml')  
            
            items = soup.find_all(site_config['article_selector'])
            logger.info(f"Found {len(items)} items in RSS feed")
            
            for item in items[:self.articles_per_site]:
                try:
                    title = item.find(site_config['title_selector'])
                    link = item.find(site_config['link_selector'])
                    description = item.find(site_config['content_selector'])
                    
                    if title and link:
                        article = {
                            "title": title.text.strip(),
                            "link": link.text.strip(),
                            "content": description.text.strip() if description else None
                        }
                        articles.append(article)
                        logger.info(f"Found article: {article['title']}")
                except Exception as e:
                    logger.error(f"Error parsing RSS item: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
        return articles

    async def get_article_content(self, session, url: str, site_config: dict) -> str:
        """获取文章内容"""
        # For RSS feeds that include content in the feed
        if hasattr(self, '_current_article_content') and self._current_article_content:
            content = self._current_article_content
            self._current_article_content = None  # Clear for next article
            return content
            
        # For RSS feeds that need content fetching
        try:
            if site_config.get("requires_browser"):
                async with async_playwright() as p:
                    browser = await p.chromium.launch()
                    page = await browser.new_page()
                    response = await page.goto(url, wait_until="networkidle")
                    
                    if response and response.ok:
                        # Wait for content
                        if site_config.get("content_selector"):
                            await page.wait_for_selector(site_config["content_selector"])
                            content_elem = await page.query_selector(site_config["content_selector"])
                            if content_elem:
                                return await content_elem.inner_text()
                    
                    await browser.close()
            else:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        if html:
                            soup = BeautifulSoup(html, 'html.parser')
                            content_elem = soup.select_one(site_config["content_selector"])
                            if content_elem:
                                return content_elem.get_text(strip=True)
        except Exception as e:
            logger.error(f"Error fetching article content from {url}: {e}")
        return None

    async def parse_articles(self, feed_content: str, site_config: dict) -> list:
        """解析 RSS 文章列表"""
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
                if 'content' in item and item.content:
                    content = item.content[0].get('value', '')
                elif 'description' in item:
                    content = item.description
                elif 'summary' in item:
                    content = item.summary
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link,
                        "content": content  # Store content directly in article dict
                    })
                    logger.info(f"Found article: {title}")
        except Exception as e:
            logger.error(f"Error parsing RSS feed: {e}")
        return articles 