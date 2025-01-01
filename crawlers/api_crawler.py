import aiohttp
import logging
from .base_crawler import BaseCrawler

logger = logging.getLogger(__name__)

class APICrawler(BaseCrawler):
    async def get_content(self, session, url: str, site_config: dict) -> dict:
        """Get API content"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        
        if "openai.com" in url:
            headers.update({
                "Origin": "https://openai.com",
                "Referer": "https://openai.com/news",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            })
            
        try:
            logger.info(f"Fetching API content from {url}")
            async with session.get(url, headers=headers, ssl=False) as response:
                logger.info(f"API response status: {response.status}")
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API request failed with status {response.status}")
                    logger.error(f"Error response: {error_text[:500]}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching API {url}: {str(e)}", exc_info=True)
            return None

    async def parse_articles(self, data: dict, site_config: dict) -> list:
        """Parse API returned article list"""
        if not data:
            return []
            
        articles = []
        try:
            if site_config["api_type"] == "json":
                # OpenAI blog API
                if "openai.com" in site_config["url"]:
                    posts = data.get("items", [])  # Update to correct data structure
                    for post in posts[:self.articles_per_site]:
                        articles.append({
                            "title": post.get("title", ""),
                            "link": f"https://openai.com/blog/{post.get('slug', '')}",
                            "content": post.get("content", "")
                        })
                        logger.info(f"Found article: {post.get('title', '')}")
        except Exception as e:
            logger.error(f"Error parsing API response: {e}")
        return articles

    async def get_article_content(self, session, url: str, site_config: dict) -> str:
        """Get article content"""
        # For OpenAI, content is already in the list API
        if "openai.com" in url:
            return None
            
        # For other APIs, get specific article content
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("content", "")
        except Exception as e:
            logger.error(f"Error fetching article content from API {url}: {e}")
        return None 