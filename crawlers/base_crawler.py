from abc import ABC, abstractmethod
import logging
from typing import List, Dict
import asyncio

logger = logging.getLogger(__name__)

class BaseCrawler(ABC):
    def __init__(self):
        self.max_retries = 3
        self.articles_per_site = 5

    @abstractmethod
    async def get_content(self, page, url: str, site_config: dict) -> str:
        """获取页面内容"""
        pass

    @abstractmethod
    async def parse_articles(self, html: str, site_config: dict) -> List[Dict]:
        """解析文章列表"""
        pass

    @abstractmethod
    async def get_article_content(self, page, url: str, site_config: dict) -> str:
        """获取文章内容"""
        pass 