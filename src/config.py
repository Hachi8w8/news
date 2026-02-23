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

# --- LLM設定 ---
# LiteLLM のモデル名（プロバイダー/モデル の形式）
# OpenRouter経由: "openrouter/google/gemini-2.5-flash", "openrouter/deepseek/deepseek-chat-v3-0324"
# Gemini直接(無料枠20RPD): "gemini/gemini-2.5-flash"
CLASSIFY_MODEL = "openrouter/google/gemini-2.5-flash"
SUMMARY_MODEL = "openrouter/google/gemini-2.5-flash"

# 分類は安定性重視で低め、要約は自然な文章にするためやや高め
CLASSIFY_TEMPERATURE = 0.1
SUMMARY_TEMPERATURE = 0.3

# 分類バッチサイズ（1リクエストに含める記事数の上限）
CLASSIFY_BATCH_SIZE = 10

# OpenRouterはレート制限が緩いが、念のため間隔を空ける
LLM_REQUEST_INTERVAL = 2

# リトライ設定
LLM_MAX_RETRIES = 3
LLM_RETRY_DELAYS = [10, 30, 60]
