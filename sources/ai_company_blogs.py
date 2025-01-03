"""AI Company Blogs"""

AI_COMPANY_BLOGS = {
    # "OpenAI Blog": {
    #     "url": "https://openai.com/news/rss.xml",
    #     "is_rss": True,
    #     "article_selector": "item",
    #     "title_selector": "title",
    #     "link_selector": "link",
    #     "content_selector": "article.prose",
    #     "base_url": "https://openai.com",
    #     "needs_js": True,
    #     "wait_for": "article.prose",
    #     "requires_browser": True,
    #     "use_playwright": True
    # },
    # "Google Research": {
    #     "url": "https://blog.research.google/feeds/posts/default",
    #     "is_rss": True,
    #     "article_selector": "entry",
    #     "title_selector": "title",
    #     "link_selector": "link",
    #     "content_selector": "content",
    #     "base_url": "https://blog.research.google",
    #     "use_rss_content": True
    # },
    # "AWS AI Blog": {
    #     "url": "https://aws.amazon.com/blogs/machine-learning/feed/",
    #     "is_rss": True,
    #     "article_selector": "item",
    #     "title_selector": "title",
    #     "link_selector": "link",
    #     "content_selector": "description",
    #     "base_url": "https://aws.amazon.com"
    # },
    # "NVIDIA AI Blog": {
    #     "url": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
    #     "is_rss": True,
    #     "article_selector": "item",
    #     "title_selector": "title",
    #     "link_selector": "link",
    #     "content_selector": "encoded",
    #     "base_url": "https://blogs.nvidia.com",
    #     "use_rss_content": True
    # },
    # "Anthropic Blog": {
    #     "url": "https://www.anthropic.com/news",
    #     "article_selector": "main a[href^='/news/']",
    #     "title_selector": "h3, span.text-xl, div[class*='text-xl'], h3.font-display, [class*='heading']",
    #     "link_selector": "self",
    #     "content_selector": "article, main article",
    #     "needs_js": True,
    #     "wait_for": "main",
    #     "base_url": "https://www.anthropic.com"
    # },
    "Hugging Face Blog": {
        "url": "https://huggingface.co/blog/feed.xml",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "description",
        "base_url": "https://huggingface.co",
        "use_rss_content": True,
        "requires_browser": False,
        "rss_content_field": "content"
    },
    "LangChain Blog": {
        "url": "https://blog.langchain.dev/rss/",
        "is_rss": True,
        "article_selector": "item",
        "title_selector": "title",
        "link_selector": "link",
        "content_selector": "content:encoded",
        "base_url": "https://blog.langchain.dev",
        "use_rss_content": True,
        "rss_content_field": "content_encoded"
    }
} 