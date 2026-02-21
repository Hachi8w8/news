import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urlunparse

import feedparser

from config import ARTICLE_FETCH_HOURS, RSS_FEEDS

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """クエリパラメータ・フラグメント・末尾スラッシュを除去してURLを正規化する。"""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    normalized = urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    return normalized


def _get_article_time(entry: feedparser.FeedParserDict) -> datetime | None:
    """記事の日時を取得する。updated_parsed → published_parsed の優先順。"""
    time_struct = entry.get("updated_parsed") or entry.get("published_parsed")
    if time_struct is None:
        return None
    return datetime(*time_struct[:6], tzinfo=timezone.utc)


def _is_within_hours(article_time: datetime | None, hours: int) -> bool:
    """記事が指定時間以内かどうかを判定する。日時なしの場合はTrueを返す（取りこぼし防止）。"""
    if article_time is None:
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return article_time >= cutoff


def _extract_summary(entry: feedparser.FeedParserDict) -> str:
    """記事の概要テキストを取得する。"""
    summary = entry.get("summary", "")
    if not summary:
        content = entry.get("content")
        if content and isinstance(content, list):
            summary = content[0].get("value", "")
    return summary


def _fetch_feed(feed_config: dict) -> list[dict]:
    """単一フィードから記事を取得し、フィルタリングして返す。"""
    url = feed_config["url"]
    source = feed_config["source"]

    logger.info(f"フィード取得開始: {source} ({url})")
    feed = feedparser.parse(url)

    if feed.bozo:
        logger.warning(f"フィードパースに問題あり: {source} - {feed.bozo_exception}")

    status = feed.get("status")
    if status and status != 200:
        logger.warning(f"HTTPステータス異常: {source} - {status}")

    articles = []
    for entry in feed.entries:
        article_time = _get_article_time(entry)
        if not _is_within_hours(article_time, ARTICLE_FETCH_HOURS):
            continue

        raw_url = entry.get("link", "")
        if not raw_url:
            continue

        article = {
            "title": entry.get("title", "タイトルなし"),
            "url": normalize_url(raw_url),
            "summary": _extract_summary(entry),
            "source": source,
        }
        articles.append(article)

    logger.info(f"{source}: {len(articles)}件の記事を取得（フィード全体: {len(feed.entries)}件）")
    return articles


def collect_articles() -> list[dict]:
    """全RSSフィードから記事を収集して返す。"""
    all_articles = []
    for feed_config in RSS_FEEDS:
        try:
            articles = _fetch_feed(feed_config)
            all_articles.extend(articles)
        except Exception:
            logger.exception(f"フィード取得失敗: {feed_config['source']}")

    seen_urls: set[str] = set()
    unique_articles = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)

    logger.info(f"合計: {len(unique_articles)}件の新規記事（重複除去後）")
    return unique_articles
