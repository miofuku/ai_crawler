import requests
from bs4 import BeautifulSoup
from transformers import pipeline

# Step 1: 定义目标网址
URLS = [
    "https://cointelegraph.com/",  # 加密货币和Web3新闻
    "https://www.coindesk.com/",   # 加密货币和区块链新闻
    "https://venturebeat.com/category/ai/",  # AI相关新闻
    "https://www.artificialintelligence-news.com/"  # AI专业新闻
]

# Step 2: 爬取网页内容
def fetch_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

# Step 3: 提取关键内容
def extract_content(html):
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # 示例：提取标题和文章段落
        title = soup.find('title').text
        paragraphs = soup.find_all('p')
        content = " ".join([p.text for p in paragraphs])
        return {"title": title, "content": content}
    except Exception as e:
        print(f"Error extracting content: {e}")
        return None

# Step 4: 总结内容
def summarize_content(content, model_name="facebook/bart-large-cnn"):
    try:
        summarizer = pipeline("summarization", model=model_name)
        summary = summarizer(content, max_length=130, min_length=30, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing content: {e}")
        return None

# 主逻辑
def main():
    for url in URLS:
        print(f"Processing URL: {url}")
        html = fetch_content(url)
        if not html:
            continue

        extracted = extract_content(html)
        if not extracted:
            continue
        
        print(f"Title: {extracted['title']}")
        
        summary = summarize_content(extracted['content'])
        if summary:
            print(f"Summary:\n{summary}")
        else:
            print("Failed to summarize content.")
        print("-" * 80)

if __name__ == "__main__":
    main()
