"""arXiv RSS 源配置"""

ARXIV_SOURCES = {
    "arXiv AI": {
        "url": "http://arxiv.org/rss/cs.AI",
        "is_rss": True,  # 标记为 RSS 源
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description"
    },
    "arXiv ML": {
        "url": "http://arxiv.org/rss/cs.LG",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description"
    },
    "arXiv CL": {  # 计算语言学
        "url": "http://arxiv.org/rss/cs.CL",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description"
    }
} 