"""AI 公司博客源配置"""

AI_COMPANY_BLOGS = {
    "OpenAI Blog": {
        "url": "https://openai.com/blog",
        "article_selector": "article.post-card",
        "title_selector": "h2.post-card-title",
        "link_selector": "a.post-card-link",
        "content_selector": "div.post-content"
    },
    "Anthropic Blog": {
        "url": "https://www.anthropic.com/blog",
        "article_selector": "article.blog-post",
        "title_selector": "h2.blog-title",
        "link_selector": "a.blog-link",
        "content_selector": ".blog-content"
    },
    "DeepMind Blog": {
        "url": "https://www.deepmind.com/blog",
        "article_selector": "article.blog-card",
        "title_selector": ".blog-title",
        "link_selector": "a.blog-link",
        "content_selector": ".blog-content"
    },
    "Stability AI Blog": {
        "url": "https://stability.ai/blog",
        "article_selector": ".blog-post",
        "title_selector": ".post-title",
        "link_selector": "a.post-link",
        "content_selector": ".post-content"
    },
    "Hugging Face Blog": {
        "url": "https://huggingface.co/blog",
        "article_selector": "article.blog-post",
        "title_selector": "h2.post-title",
        "link_selector": "a.post-link",
        "content_selector": ".post-content"
    },
} 