from bs4 import BeautifulSoup
from urllib.parse import urljoin
import asyncio
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class BlogCrawler(BaseCrawler):
    async def get_content(self, page, url: str, site_config: dict) -> str:
        """Get page content"""
        for attempt in range(self.max_retries):
            try:
                # Log request details
                logger.info(f"Attempt {attempt + 1}: Loading page {url}")
                logger.debug(f"Page viewport: 1920x1080")
                logger.debug(f"Site config: {site_config}")
                
                # Set a more realistic browser environment
                await page.set_viewport_size({"width": 1920, "height": 1080})
                
                # Set a more complete request header
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-User": "?1",
                    "Sec-Fetch-Dest": "document",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache"
                }
                

                if "anthropic.com" in url:
                    headers.update({
                        "Origin": "https://www.anthropic.com",
                        "Referer": "https://www.anthropic.com/"
                })
                
                await page.set_extra_http_headers(headers)

                # Configure page
                if site_config.get("needs_js"):
                    await page.route("**/*", lambda route: route.continue_())

                # Visit page
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=60000,
                )

                # Log response details
                if response:
                    logger.info(f"Response status: {response.status}")
                    logger.debug(f"Response headers: {response.headers}")
                    logger.debug(f"Response URL: {response.url}")
                    
                    if not response.ok:
                        logger.error(f"Response not OK - Status: {response.status}")
                        logger.error(f"Response text: {await response.text()}")
                else:
                    logger.error("No response received from page.goto()")

                if response is None or not response.ok:
                    raise Exception(f"Failed to load page: {response.status if response else 'No response'}")

                # Wait for page load
                if site_config.get("wait_for"):
                    try:
                        await page.wait_for_selector(site_config["wait_for"], timeout=30000)
                    except Exception as e:
                        logger.warning(f"Wait for selector warning (continuing anyway): {e}")
                        # Don't return None, continue with the page content
                
                await asyncio.sleep(3)  # Give extra time for dynamic content
                
                # Handle cookie prompts and popups
                for selector in [
                    "button[data-testid='cookie-policy-dialog-accept']",
                    "button[aria-label='Accept cookies']",
                    ".cookie-banner button",
                    "#cookie-consent button",
                    ".modal-close",
                    ".close-button"
                ]:
                    try:
                        button = page.locator(selector)
                        if await button.is_visible(timeout=2000):
                            await button.click()
                            await asyncio.sleep(1)
                    except Exception:
                        continue

                # Adjust scroll times based on configuration
                scroll_times = site_config.get("scroll_times", 3)
                for _ in range(scroll_times):
                    await page.evaluate("""
                        window.scrollTo({
                            top: document.body.scrollHeight,
                            behavior: 'smooth'
                        });
                    """)
                    await asyncio.sleep(2)

                return await page.content()

            except Exception as e:
                logger.error(f"Attempt {attempt + 1}/{self.max_retries} failed for {url}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.debug(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All attempts failed for {url}")
                    return None

    async def parse_articles(self, html: str, site_config: dict) -> list:
        if not html:
            return []
            
        articles = []
        soup = BeautifulSoup(html, 'html.parser')
        base_url = site_config['base_url'].rstrip('/')
        
        # Find all article elements
        elements = soup.select(site_config['article_selector'])
        logger.debug(f"Found {len(elements)} elements matching selector '{site_config['article_selector']}'")
        
        for element in elements[:self.articles_per_site]:
            try:
                # Get link
                link = element.get('href')
                title = None
                
                # Handle relative URLs immediately
                if link and not link.startswith('http'):
                    link = f"{base_url}{link}"
                
                # Special handling for Anthropic blog
                if "anthropic.com" in site_config["url"]:
                    # Try multiple possible title selectors
                    title_selectors = [
                        "h3",  # Direct h3 heading
                        "span.text-xl",  # Text-xl span
                        "div[class*='text-xl']",  # Div with text-xl class
                        "h3.font-display",  # Specific heading class
                        "[class*='heading']"  # Any element with heading in class
                    ]
                    
                    for selector in title_selectors:
                        title_elem = element.select_one(selector)
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            if title:
                                break
                    
                    # If still no title found, look in parent elements
                    if not title:
                        parent = element.parent
                        while parent and not title:
                            for selector in title_selectors:
                                title_elem = parent.select_one(selector)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    if title:
                                        break
                            parent = parent.parent
                    
                    # Skip the main news page link
                    if link == '/news':
                        continue

                    # Add debug logging
                    logger.debug(f"Found title: {title} for link: {link}")
                
                # Special handling for Hugging Face blog
                elif "huggingface.co" in site_config["url"]:
                    # Get title from the element itself
                    title_selectors = [
                        "h1", "h2", ".text-2xl", ".font-bold",
                        "div[class*='heading']", "div[class*='title']"
                    ]
                    
                    for selector in title_selectors:
                        title_elem = element.select_one(selector)
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            if title:
                                break
                    
                    # If no title found in element, try parent elements
                    if not title:
                        parent = element.parent
                        while parent and not title:
                            for selector in title_selectors:
                                title_elem = parent.select_one(selector)
                                if title_elem:
                                    title = title_elem.get_text(strip=True)
                                    if title:
                                        break
                            parent = parent.parent
                    
                    # If still no title, try getting it from aria-label
                    if not title:
                        title = element.get('aria-label', '').strip()
                    
                    logger.debug(f"Hugging Face blog - Found link: {link}, title: {title}")
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link
                    })
                    logger.debug(f"Found article: {title} - {link}")
                
            except Exception as e:
                logger.error(f"Error parsing article: {e}")
                continue

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    async def get_article_content(self, page, url: str, site_config: dict) -> str:
        """Get article content"""
        try:
            logger.debug(f"Fetching content from: {url}")
            
            # Navigate with longer timeout
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            
            if response and response.ok:
                # First wait for any dynamic content to load
                await page.wait_for_load_state("networkidle")
                
                if "anthropic.com" in url:
                    try:
                        # Wait for main content
                        await page.wait_for_selector("main", timeout=10000)
                        
                        # Get content from article or main
                        for selector in ["article", "main article", "main div[class*='prose']"]:
                            content_elem = await page.query_selector(selector)
                            if content_elem:
                                text = await content_elem.inner_text()
                                if text and len(text.strip()) > 0:
                                    return text.strip()
                                    
                    except Exception as e:
                        logger.warning(f"Error getting Anthropic content: {e}")
                        
                # Default content extraction if no special handling needed
                content_selector = site_config.get("content_selector", "article")
                try:
                    content_elem = await page.query_selector(content_selector)
                    if content_elem:
                        return await content_elem.inner_text()
                except Exception as e:
                    logger.error(f"Error extracting content with selector {content_selector}: {e}")
                    
                if "huggingface.co" in url:
                    try:
                        # Wait for main content
                        await page.wait_for_selector("main", timeout=10000)
                        
                        # Try multiple content selectors
                        for selector in ["main article", "div.prose", ".markdown", "main div[class*='prose']"]:
                            content_elem = await page.query_selector(selector)
                            if content_elem:
                                text = await content_elem.inner_text()
                                if text and len(text.strip()) > 100:  # Ensure we have substantial content
                                    return text.strip()
                                    
                    except Exception as e:
                        logger.warning(f"Error getting Hugging Face content: {e}")
                
            return ""  # Return empty string instead of None
            
        except Exception as e:
            logger.error(f"Error fetching article content: {e}")
            return ""  # Return empty string instead of None 