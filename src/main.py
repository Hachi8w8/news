"""エントリーポイント。RSS収集 → 重複排除 → 本文取得 → AI分類・要約 → Discord通知を行う。"""

import logging

from cache_manager import filter_new_articles, load_cache, save_cache
from classifier import classify_articles, get_llm_stats, summarize_articles
from notifier import notify_articles, send_bot_log
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

    # --- Step 2: キャッシュ照合 ---
    logger.info("=== Step 2: キャッシュ照合（重複排除） ===")
    cache = load_cache()
    articles = filter_new_articles(articles, cache)

    if not articles:
        logger.info("未処理の記事はありませんでした（全てキャッシュ済み）")
        return

    # --- Step 3: 本文取得 ---
    logger.info("=== Step 3: 本文取得 ===")
    articles = scrape_articles(articles)

    # --- Step 4: AI分類 + 要約 ---
    logger.info("=== Step 4: AI分類 ===")
    articles = classify_articles(articles)

    logger.info("=== Step 4: 要約生成 ===")
    articles = summarize_articles(articles)

    # --- Step 5: Discord通知 ---
    logger.info("=== Step 5: Discord通知 ===")
    stats = notify_articles(articles)

    # --- Step 6: bot-logサマリー送信 ---
    logger.info("=== Step 6: 実行結果サマリー送信 ===")
    llm_stats = get_llm_stats()
    send_bot_log(articles, stats, llm_stats)

    # --- Step 7: キャッシュ保存 ---
    logger.info("=== Step 7: キャッシュ保存 ===")
    save_cache(cache, articles)

    logger.info(f"=== 処理完了: {len(articles)}件 ===")


if __name__ == "__main__":
    main()
