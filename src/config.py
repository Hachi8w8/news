import os

from dotenv import load_dotenv

load_dotenv()

RSS_FEEDS = [
    {
        "url": "https://zenn.dev/feed",
        "source": "Zenn",
    },
    {
        "url": "https://qiita.com/popular-items/feed.atom",
        "source": "Qiita",
    },
]

ARTICLE_FETCH_HOURS = 24
