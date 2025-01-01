from bs4 import BeautifulSoup
from urllib.parse import urljoin
import asyncio
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class BlogCrawler(BaseCrawler):
    async def get_content(self, page, url: str, site_config: dict) -> str:
        """获取页面内容"""
        for attempt in range(self.max_retries):
            try:
                # Log request details
                logger.info(f"Attempt {attempt + 1}: Loading page {url}")
                logger.debug(f"Page viewport: 1920x1080")
                logger.debug(f"Site config: {site_config}")
                
                # 设置更真实的浏览器环境
                await page.set_viewport_size({"width": 1920, "height": 1080})
                
                # 设置更完整的请求头
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

                # 配置页面
                if site_config.get("needs_js"):
                    await page.route("**/*", lambda route: route.continue_())

                # 访问页面
                response = await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=60000,
                )

                # Log response details
                if response:
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response headers: {response.headers}")
                    logger.debug(f"Response URL: {response.url}")
                    
                    if not response.ok:
                        logger.error(f"Response not OK - Status: {response.status}")
                        logger.error(f"Response text: {await response.text()}")
                else:
                    logger.error("No response received from page.goto()")

                if response is None or not response.ok:
                    raise Exception(f"Failed to load page: {response.status if response else 'No response'}")

                # 等待页面加载
                if site_config.get("wait_for"):
                    try:
                        await page.wait_for_selector(site_config["wait_for"], timeout=30000)
                    except Exception as e:
                        logger.warning(f"Wait for selector warning (continuing anyway): {e}")
                        # Don't return None, continue with the page content
                
                await asyncio.sleep(3)  # Give extra time for dynamic content
                
                # 处理 cookie 提示和弹窗
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

                # 根据配置调整滚动次数
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
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"All attempts failed for {url}")
                    return None

    async def parse_articles(self, html: str, site_config: dict) -> list:
        """解析文章列表"""
        if not html:
            logger.warning("No HTML content to parse")
            return []
            
        articles = []
        soup = BeautifulSoup(html, 'html.parser')
        
        elements = soup.select(site_config['article_selector'])
        logger.info(f"Found {len(elements)} elements matching selector '{site_config['article_selector']}'")
        
        for article in elements[:self.articles_per_site]:
            try:
                # Hugging Face specific handling
                if "huggingface.co" in site_config["url"]:
                    logger.debug(f"Processing Hugging Face article element: {article.get('class', [])}")
                    
                    # Get link element
                    link_elem = article.select_one(site_config["link_selector"])
                    logger.debug(f"Link element found: {link_elem is not None}")
                    if link_elem:
                        logger.debug(f"Link element attributes: {link_elem.attrs}")
                    
                    # Get title element with detailed logging
                    title_elem = (
                        article.select_one("h2") or 
                        article.select_one("h3") or 
                        article.select_one("span.font-bold")
                    )
                    logger.debug(f"Title element found: {title_elem is not None}")
                    if title_elem:
                        logger.debug(f"Title element text: {title_elem.get_text(strip=True)}")
                    
                    link = link_elem.get('href') if link_elem else None
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    logger.debug(f"Extracted title: {title}")
                    logger.debug(f"Extracted link: {link}")
                    
                    # If no title found but have link, try to extract from URL
                    if not title and link:
                        path = link.split('/')[-1]
                        title = ' '.join(word.capitalize() for word in path.split('-'))
                    
                    if link and not link.startswith('http'):
                        link = urljoin(site_config['base_url'], link)
                
                # 对于 Anthropic 的特殊处理
                elif "anthropic.com" in site_config["url"]:
                    # The link is the article element itself
                    link = article.get('href')
                    title_elem = None
                    
                    # Find the closest h3 in any parent div
                    parent = article.parent
                    while parent and parent.name == 'div':
                        title_elem = parent.find('h3')
                        if title_elem:
                            break
                        parent = parent.parent
                    
                    # If no title found in parents, try to find in siblings
                    if not title_elem:
                        next_sibling = article.find_next_sibling()
                        while next_sibling:
                            title_elem = next_sibling.find('h3')
                            if title_elem:
                                break
                            next_sibling = next_sibling.find_next_sibling()
                    
                    title = title_elem.get_text(strip=True) if title_elem else None
                    
                    # If still no title, try to extract from the URL
                    if not title and link:
                        # Convert URL path to title (e.g., "announcing-claude-3" -> "Announcing Claude 3")
                        path = link.split('/')[-1]
                        title = ' '.join(word.capitalize() for word in path.split('-'))
                    
                    if link and not link.startswith('http'):
                        link = urljoin(site_config['base_url'], link)
            
                title_elem = article.select_one(site_config["title_selector"])
                link_elem = article.select_one(site_config["link_selector"])
                
                title = title_elem.get_text(strip=True) if title_elem else None
                link = link_elem.get('href') if link_elem else None
                if link and not link.startswith('http'):
                    base_url = site_config.get('base_url', site_config['url'])
                    link = urljoin(base_url, link)
                
                if title and link:
                    articles.append({
                        "title": title,
                        "link": link
                    })
                    logger.info(f"Found article: {title} - {link}")  # Added link to logging
                else:
                    logger.warning(f"Skipping article - Title: {title}, Link: {link}")
                
            except Exception as e:
                logger.error(f"Error parsing article: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(articles)} articles")  # Added summary logging
        return articles

    async def get_article_content(self, page, url: str, site_config: dict) -> str:
        """获取文章内容"""
        html = await self.get_content(page, url, site_config)
        if not html:
            return None
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            content_div = soup.select_one(site_config["content_selector"])
            
            if content_div:
                # 移除不需要的元素
                for elem in content_div.select('script, style, iframe, nav, header, footer, button'):
                    elem.decompose()
                
                # 获取结构化内容
                content_parts = []
                
                # Get headings for structure
                headings = content_div.find_all(['h1', 'h2', 'h3'])
                for heading in headings:
                    section_title = heading.get_text(strip=True)
                    # Get all paragraph content until next heading
                    section_content = []
                    current = heading.find_next_sibling()
                    while current and current.name not in ['h1', 'h2', 'h3']:
                        if current.name in ['p', 'li']:
                            text = current.get_text(strip=True)
                            if text:  # Only add non-empty text
                                section_content.append(text)
                        current = current.find_next_sibling()
                    
                    if section_content:  # Only add sections with content
                        content_parts.append({
                            "title": section_title,
                            "content": " ".join(section_content)
                        })
                
                # If no sections found, get all paragraph content
                if not content_parts:
                    paragraphs = content_div.find_all(['p', 'li'])
                    content_text = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                    if content_text:
                        content_parts.append({
                            "title": "Main Content",
                            "content": content_text
                        })
                
                return content_parts if content_parts else None
                
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            
        return None 