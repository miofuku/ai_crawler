"""基础爬虫类"""
from abc import ABC, abstractmethod

class BaseCrawler(ABC):
    @abstractmethod
    async def get_content(self, page, url: str, site_config: dict) -> str:
        pass

    @abstractmethod
    async def parse_articles(self, html: str, site_config: dict) -> list:
        pass 