"""博客爬虫"""
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
                # 设置用户代理和视口
                await page.set_viewport_size({"width": 1920, "height": 1080})
                await page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
                })
                
                response = await page.goto(
                    url, 
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                
                if response is None or not response.ok:
                    raise Exception(f"Failed to load page: {response.status if response else 'No response'}")
                
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
            return []
            
        articles = []
        soup = BeautifulSoup(html, 'html.parser')
        
        elements = soup.select(site_config['article_selector'])
        logger.info(f"Found {len(elements)} elements matching selector '{site_config['article_selector']}'")
        
        for article in elements[:self.articles_per_site]:
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
                    
                    articles.append({
                        "title": title,
                        "link": link
                    })
            except Exception as e:
                logger.error(f"Error parsing article: {e}")
        
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
                for elem in content_div.select('script, style, iframe, nav, header, footer'):
                    elem.decompose()
                
                # 获取所有段落文本
                paragraphs = content_div.find_all('p')
                content = " ".join([p.text.strip() for p in paragraphs if p.text.strip()])
                
                return content if content else None
                
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {e}")
            
        return None 