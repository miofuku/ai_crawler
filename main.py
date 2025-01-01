import asyncio
import json
import os
from datetime import datetime
import logging
from typing import List, Dict
from sources import (
    ai_company_blogs,
    web3_blogs,
    research_blogs,
    chinese_blogs,
    arxiv_sources,
    paper_analysis
)
from crawlers.base_crawler import BaseCrawler
from crawlers.blog_crawler import BlogCrawler
from crawlers.rss_crawler import RSSCrawler
from playwright.async_api import async_playwright
from transformers import pipeline

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置输出
OUTPUT_DIR = "output"
OUTPUT_FILE = os.path.join(
    OUTPUT_DIR, 
    f"ai_news_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
)

# 初始化模型
summarizer = pipeline(
    "summarization", 
    model="sshleifer/distilbart-cnn-12-6",
    device=-1
)

translator = pipeline(
    "translation", 
    model="Helsinki-NLP/opus-mt-en-zh",
    tokenizer="Helsinki-NLP/opus-mt-en-zh",
    device=-1
)

CATEGORIES = {
    "ai": ai_company_blogs.AI_COMPANY_BLOGS,
    "web3": web3_blogs.WEB3_BLOGS,
    "research": research_blogs.RESEARCH_BLOGS,
    "chinese": chinese_blogs.CHINESE_BLOGS,
    "arxiv": arxiv_sources.ARXIV_SOURCES,
    "paper_analysis": paper_analysis.PAPER_ANALYSIS_BLOGS
}

def summarize_and_translate(content: str) -> Dict[str, str]:
    """Summarize content and translate to Chinese"""
    if not content or len(content.split()) < 30:
        return None
        
    try:
        # 检测内容语言
        is_chinese = any('\u4e00' <= char <= '\u9fff' for char in content)
        
        if is_chinese:
            # 中文内容处理
            translated_en = translator(
                content, 
                src_lang="zh", 
                tgt_lang="en",
                max_length=1024
            )[0]['translation_text']
            
            # 动态计算摘要长度
            input_length = len(translated_en.split())
            max_output_length = min(input_length, 150)
            min_output_length = min(50, max_output_length - 10)
            
            summary_en = summarizer(
                translated_en,
                max_length=max_output_length,
                min_length=min_output_length,
                length_penalty=2.0,
                num_beams=4,
                early_stopping=True
            )[0]['summary_text']
            
            summary_zh = content  # 保留原中文内容
        else:
            # 英文内容处理
            input_length = len(content.split())
            max_output_length = min(input_length, 150)
            min_output_length = min(50, max_output_length - 10)
            
            summary_en = summarizer(
                content,
                max_length=max_output_length,
                min_length=min_output_length,
                length_penalty=2.0,
                num_beams=4,
                early_stopping=True
            )[0]['summary_text']
            
            summary_zh = translator(
                summary_en,
                src_lang="en",
                tgt_lang="zh",
                max_length=1024
            )[0]['translation_text']
        
        return {
            "en": summary_en,
            "zh": summary_zh
        }
    except Exception as e:
        logger.error(f"Error summarizing content: {e}")
        return None

async def process_site(browser, site_name: str, site_config: dict, crawler: BaseCrawler) -> List[Dict]:
    """Process a single site"""
    try:
        page = await browser.new_page()
        
        # 获取文章列表
        html = await crawler.get_content(page, site_config["url"], site_config)
        articles = await crawler.parse_articles(html, site_config)
        
        if not articles:
            logger.warning(f"No articles found for {site_name}")
            await page.close()
            return []
        
        processed_articles = []
        for article in articles:
            try:
                content = await crawler.get_article_content(page, article["link"], site_config)
                if content:
                    summary = summarize_and_translate(content)
                    if summary:
                        article_data = {
                            "site": site_name,
                            "title": article["title"],
                            "link": article["link"],
                            "summary_en": summary["en"],
                            "summary_zh": summary["zh"],
                            "timestamp": datetime.now().isoformat()
                        }
                        processed_articles.append(article_data)
                        logger.info(f"Processed article: {article['title']}")
                
                await asyncio.sleep(2)  # 避免请求过快
                
            except Exception as e:
                logger.error(f"Error processing article {article['link']}: {e}")
        
        await page.close()
        return processed_articles
        
    except Exception as e:
        logger.error(f"Error processing site {site_name}: {e}")
        return []

async def main():
    # 获取用户输入
    print("Available categories:")
    for category in CATEGORIES:
        print(f"- {category}")
    
    selected_categories = input("Enter categories to crawl (comma-separated): ").split(",")
    selected_categories = [cat.strip() for cat in selected_categories]
    
    # 初始化爬虫
    blog_crawler = BlogCrawler()
    rss_crawler = RSSCrawler()
    
    # 收集选定的源
    sources = {}
    for category in selected_categories:
        if category in CATEGORIES:
            sources.update(CATEGORIES[category])
    
    # 开始爬取
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        tasks = []
        
        for site_name, site_config in sources.items():
            crawler = rss_crawler if site_config.get("is_rss") else blog_crawler
            tasks.append(process_site(browser, site_name, site_config, crawler))
        
        # 并行处理所有网站
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤掉异常，合并结果
        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
        
        logger.info(f"Total articles processed: {len(all_articles)}")
        
        # 保存结果
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "articles": all_articles
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main()) 