"""中文技术博客源配置"""

CHINESE_BLOGS = {
    "机器之心": {
        "url": "https://www.jiqizhixin.com/",
        "article_selector": "article.article-item",
        "title_selector": ".article-title",
        "link_selector": ".article-link",
        "content_selector": ".article-content"
    },
    "量子位": {
        "url": "https://www.qbitai.com/",
        "article_selector": ".article-item",
        "title_selector": ".title",
        "link_selector": "a.link",
        "content_selector": ".article-content"
    },
    "PaperWeekly": {
        "url": "https://www.paperweekly.site/",
        "article_selector": ".article-item",
        "title_selector": ".title",
        "link_selector": ".title a",
        "content_selector": ".content"
    },
    "InfoQ AI": {
        "url": "https://www.infoq.cn/topic/AI",
        "article_selector": ".article-item",
        "title_selector": ".article-title",
        "link_selector": ".article-link",
        "content_selector": ".article-content"
    },
} 