"""AI 公司博客源配置"""

AI_COMPANY_BLOGS = {
    "OpenAI Blog": {
        "url": "https://openai.com/news/rss.xml",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description",
        "base_url": "https://openai.com",
        "needs_js": True,
        "wait_for": "rss",
        "requires_browser": True
    },
    "Google Research": {
        "url": "https://blog.research.google/feeds/posts/default",
        "is_rss": True,
        "article_selector": "entry",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "content",
        "base_url": "https://blog.research.google"
    },
    "AWS AI Blog": {
        "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description",
        "base_url": "https://aws.amazon.com"
    },
    "NVIDIA AI Blog": {
        "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description",
        "base_url": "https://blogs.nvidia.com"
    },
    # 需要使用网页爬虫的博客
    # "Anthropic Blog": {
    #     "url": "https://www.anthropic.com/news",
    #     "article_selector": "a[href^='/news']",
    #     "title_selector": "h3",
    #     "link_selector": "a",
    #     "content_selector": "article",
    #     "needs_js": True,
    #     "wait_for": "main",
    #     "base_url": "https://www.anthropic.com"
    # },
    "Hugging Face Blog": {
        "url": "https://huggingface.co/blog",
        "article_selector": "div.flex.flex-col",
        "title_selector": "h2, h3, span.font-bold",
        "link_selector": "a[href*='/blog/']",
        "content_selector": "article.prose",
        "needs_js": True,
        "wait_for": "div.flex.flex-col",
        "base_url": "https://huggingface.co"
    }
} 