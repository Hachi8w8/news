"""エントリーポイント。RSS収集 → 本文取得 → コンソール出力を行う。"""

import logging

from rss_collector import collect_articles
from scraper import scrape_articles

# ログの出力形式を設定（タイムスタンプ・レベル・モジュール名・メッセージ）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    # --- Step 1: RSS収集 ---
    logger.info("=== Step 1: RSS記事収集 ===")
    articles = collect_articles()

    if not articles:
        logger.info("新規記事はありませんでした")
        return

    # --- Step 2: 本文取得 ---
    logger.info("=== Step 2: 本文取得 ===")
    articles = scrape_articles(articles)

    # --- 結果表示 ---
    for i, article in enumerate(articles, 1):
        content_preview = article["content"][:200] if article.get("content") else "(本文取得失敗)"
        logger.info(
            f"[{i}/{len(articles)}] [{article['source']}] {article['title']}\n"
            f"  URL: {article['url']}\n"
            f"  本文: {content_preview}"
        )

    logger.info(f"=== 処理完了: {len(articles)}件 ===")


if __name__ == "__main__":
    main()
