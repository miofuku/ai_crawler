"""RSS 爬虫"""
from bs4 import BeautifulSoup
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class RSSCrawler(BaseCrawler):
    async def get_content(self, page, url: str, site_config: dict) -> str:
        """获取 RSS 内容"""
        try:
            response = await page.goto(url)
            if response and response.ok:
                return await page.content()
        except Exception as e:
            logger.error(f"Error fetching RSS feed {url}: {e}")
        return None

    async def parse_articles(self, html: str, site_config: dict) -> list:
        """解析 RSS 文章列表"""
        if not html:
            return []
            
        articles = []
        soup = BeautifulSoup(html, 'xml')  # 使用 xml 解析器
        
        items = soup.find_all(site_config['article_selector'])
        logger.info(f"Found {len(items)} items in RSS feed")
        
        for item in items[:self.articles_per_site]:
            try:
                title = item.find(site_config['title_selector'])
                link = item.find(site_config['link_selector'])
                
                if title and link:
                    articles.append({
                        "title": title.text.strip(),
                        "link": link.text.strip()
                    })
            except Exception as e:
                logger.error(f"Error parsing RSS item: {e}")
        
        return articles

    async def get_article_content(self, page, url: str, site_config: dict) -> str:
        """获取 RSS 文章内容"""
        # RSS 项目通常在 description 标签中包含内容
        html = await self.get_content(page, url, site_config)
        if not html:
            return None
            
        try:
            soup = BeautifulSoup(html, 'xml')
            description = soup.find(site_config['content_selector'])
            
            if description:
                # 移除 HTML 标签，保留纯文本
                content = BeautifulSoup(description.text, 'html.parser').get_text()
                return content.strip() if content else None
                
        except Exception as e:
            logger.error(f"Error extracting content from RSS item {url}: {e}")
            
        return None 