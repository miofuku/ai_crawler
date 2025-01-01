"""博客爬虫"""
from .base_crawler import BaseCrawler

class BlogCrawler(BaseCrawler):
    async def get_content(self, page, url: str, site_config: dict) -> str:
        # 实现博客页面的内容获取逻辑
        pass

    async def parse_articles(self, html: str, site_config: dict) -> list:
        # 实现博客文章的解析逻辑
        pass 