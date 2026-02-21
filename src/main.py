import logging

from rss_collector import collect_articles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("=== RSS記事収集 開始 ===")

    articles = collect_articles()

    if not articles:
        logger.info("新規記事はありませんでした")
        return

    for i, article in enumerate(articles, 1):
        summary_preview = article["summary"][:100] if article["summary"] else "(概要なし)"
        logger.info(
            f"[{i}/{len(articles)}] [{article['source']}] {article['title']}\n"
            f"  URL: {article['url']}\n"
            f"  概要: {summary_preview}"
        )

    logger.info(f"=== RSS記事収集 完了: {len(articles)}件 ===")


if __name__ == "__main__":
    main()
