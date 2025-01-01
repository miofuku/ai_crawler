"""论文分析博客源配置"""

PAPER_ANALYSIS_BLOGS = {
    "Papers with Code": {  # 论文代码实现
        "url": "https://paperswithcode.com/latest",
        "article_selector": ".paper-card",
        "title_selector": ".paper-title",
        "link_selector": ".paper-link",
        "content_selector": ".paper-abstract"
    },
    "Two Minute Papers": {  # AI论文视频解读
        "url": "https://www.youtube.com/@TwoMinutePapers/videos",
        "article_selector": "ytd-video-renderer",
        "title_selector": "#video-title",
        "link_selector": "#video-title",
        "content_selector": "#description"
    },
    "Lil'Log": {  # 深度学习论文解读
        "url": "https://lilianweng.github.io/",
        "article_selector": ".post-list-item",
        "title_selector": ".post-title",
        "link_selector": "a.post-link",
        "content_selector": ".post-content"
    },
    "The Gradient": {  # AI研究分析
        "url": "https://thegradient.pub/",
        "article_selector": "article.post",
        "title_selector": ".post-title",
        "link_selector": ".post-link",
        "content_selector": ".post-content"
    },
    "ML Explained": {  # 机器学习论文解读
        "url": "https://mlexplained.com/",
        "article_selector": "article.post",
        "title_selector": ".entry-title",
        "link_selector": ".entry-title a",
        "content_selector": ".entry-content"
    },
    "Berkeley AI Research Blog": {  # 学术研究博客
        "url": "https://bair.berkeley.edu/blog/",
        "article_selector": "article.post",
        "title_selector": ".post-title",
        "link_selector": ".post-link",
        "content_selector": ".post-content"
    },
    "Distill.pub": {  # 高质量可视化解释
        "url": "https://distill.pub/",
        "article_selector": "d-article",
        "title_selector": "h1",
        "link_selector": "a.title-link",
        "content_selector": "d-article"
    },
    "AI Alignment Forum": {  # AI安全与对齐
        "url": "https://www.alignmentforum.org/",
        "article_selector": ".PostsItem",
        "title_selector": ".PostsTitle",
        "link_selector": ".PostsTitle a",
        "content_selector": ".PostsBody"
    },
}