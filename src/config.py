"""設定値を一箇所に集約するモジュール。変更が必要なときはここだけ修正すればよい。"""

import os

from dotenv import load_dotenv

# .env ファイルがあれば環境変数として読み込む（なければ何もしない）
load_dotenv()

# 取得対象のRSSフィード一覧
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

# 過去何時間以内の記事を取得するか
ARTICLE_FETCH_HOURS = 24
