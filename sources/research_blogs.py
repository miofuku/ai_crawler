"""研究机构博客源配置"""

RESEARCH_BLOGS = {
    "Stanford AI Lab": {
        "url": "https://ai.stanford.edu/blog/",
        "article_selector": "article.post",
        "title_selector": ".post-title",
        "link_selector": "a.post-link",
        "content_selector": ".post-content"
    },
    "MIT AI Lab": {
        "url": "https://www.csail.mit.edu/news",
        "article_selector": ".news-item",
        "title_selector": ".news-title",
        "link_selector": ".news-link",
        "content_selector": ".news-content"
    },
    "Google AI Blog": {
        "url": "https://ai.googleblog.com/",
        "article_selector": ".post",
        "title_selector": ".post-title",
        "link_selector": ".post-title a",
        "content_selector": ".post-content"
    },
    "Microsoft Research": {
        "url": "https://www.microsoft.com/en-us/research/blog/",
        "article_selector": "article.blog-post",
        "title_selector": ".blog-title",
        "link_selector": ".blog-link",
        "content_selector": ".blog-content"
    },
} 