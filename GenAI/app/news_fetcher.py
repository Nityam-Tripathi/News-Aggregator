import requests
import os
from dotenv import load_dotenv

load_dotenv()

def fetch_news():

    api_key = os.getenv("NEWS_API_KEY")

    categories = [
        "technology",
        "business",
        "science",
        "health"
    ]

    keywords = [
        "artificial intelligence",
        "machine learning",
        "startup",
        "economy",
        "crypto",
        "global politics"
    ]

    articles = []

    # 🔹 Category-based news
    for category in categories:
        url = f"https://newsapi.org/v2/top-headlines?country=us&category={category}&pageSize=20&apiKey={api_key}"
        
        res = requests.get(url).json()
        if res["status"] == "ok":
            articles.extend(res["articles"])

    # 🔹 Keyword-based news
    for keyword in keywords:
        url = f"https://newsapi.org/v2/everything?q={keyword}&pageSize=20&sortBy=publishedAt&apiKey={api_key}"
        
        res = requests.get(url).json()
        if res["status"] == "ok":
            articles.extend(res["articles"])

    return articles

def fetch_news_query(query):

    api_key = os.getenv("NEWS_API_KEY")

    url = f"https://newsapi.org/v2/everything?q={query}&pageSize=10&sortBy=publishedAt&apiKey={api_key}"

    res = requests.get(url).json()

    if res["status"] == "ok":
        return res["articles"]

    return []