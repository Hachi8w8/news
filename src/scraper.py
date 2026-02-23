"""記事URLから本文テキストを抽出するモジュール。"""

import logging
import time

import trafilatura

logger = logging.getLogger(__name__)

# 本文がこの文字数未満なら取得失敗とみなす
MIN_CONTENT_LENGTH = 100

# サーバーへの負荷を抑えるためのリクエスト間隔（秒）
REQUEST_INTERVAL = 5


def fetch_content(url: str) -> str | None:
    """単一URLから本文テキストを抽出する。

    取得失敗または100文字未満の場合は None を返す。
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            logger.warning(f"HTML取得失敗: {url}")
            return None

        text = trafilatura.extract(downloaded)
        if text is None or len(text) < MIN_CONTENT_LENGTH:
            logger.warning(f"本文抽出失敗（100文字未満）: {url}")
            return None

        return text
    except Exception:
        logger.exception(f"本文取得中に例外発生: {url}")
        return None


def scrape_articles(articles: list[dict]) -> list[dict]:
    """記事リストの各URLから本文を取得し、content フィールドに追加して返す。

    5秒間隔でリクエストし、失敗時は content=None として続行する。
    """
    total = len(articles)
    success_count = 0
    fail_count = 0

    for i, article in enumerate(articles):
        url = article["url"]
        logger.info(f"本文取得中 [{i + 1}/{total}]: {url}")

        content = fetch_content(url)
        article["content"] = content

        if content is not None:
            success_count += 1
        else:
            fail_count += 1

        # 最後の記事のあとは待たない
        if i < total - 1:
            time.sleep(REQUEST_INTERVAL)

    logger.info(f"本文取得完了: 成功 {success_count}件 / 失敗 {fail_count}件 / 合計 {total}件")
    return articles
