import logging

logger = logging.getLogger(__name__)

# Simple fixed limit for all sites
ARTICLES_PER_SITE_LIMIT = 2

def get_articles_per_site(site_url: str, source_type: str) -> int:
    """
    Get the number of articles to fetch (simplified version).
    
    Args:
        site_url: The URL of the site
        source_type: Type of source (rss, blog, paper, api)
    
    Returns:
        int: Number of articles to fetch (fixed at 2)
    """
    return ARTICLES_PER_SITE_LIMIT

logger.info(f"Article limit configuration: {ARTICLES_PER_SITE_LIMIT} articles per site")