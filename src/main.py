"""エントリーポイント。RSS収集 → 本文取得 → AI分類・要約 → コンソール出力を行う。"""

import logging

from classifier import classify_articles, summarize_articles
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

    # --- Step 3: AI分類 + 要約 ---
    logger.info("=== Step 3: AI分類 ===")
    articles = classify_articles(articles)

    logger.info("=== Step 3: 要約生成 ===")
    articles = summarize_articles(articles)

    # --- 結果表示 ---
    for i, article in enumerate(articles, 1):
        summary = article.get("ai_summary", "(要約なし)")
        logger.info(
            f"[{i}/{len(articles)}] [{article['category']}] [{article['source']}] {article['title']}\n"
            f"  URL: {article['url']}\n"
            f"  要約: {summary}"
        )

    logger.info(f"=== 処理完了: {len(articles)}件 ===")


if __name__ == "__main__":
    main()
