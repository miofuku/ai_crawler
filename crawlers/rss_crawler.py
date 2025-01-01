"""RSS 爬虫"""
from .base_crawler import BaseCrawler

class RSSCrawler(BaseCrawler):
    async def get_content(self, page, url: str, site_config: dict) -> str:
        # 实现 RSS 内容获取逻辑
        pass

    async def parse_articles(self, html: str, site_config: dict) -> list:
        # 实现 RSS 文章解析逻辑
        pass 