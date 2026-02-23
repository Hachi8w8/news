"""処理済みURLのキャッシュを管理するモジュール。同じ記事の二重通知を防ぐ。"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

from config import CACHE_DIR, CACHE_EXPIRE_DAYS, CACHE_FILE

logger = logging.getLogger(__name__)


def load_cache() -> list[dict]:
    """キャッシュファイルから処理済みURLリストを読み込む。

    ファイルが存在しない場合やJSONが壊れている場合は空リストを返す。
    """
    if not os.path.exists(CACHE_FILE):
        logger.info("キャッシュファイルなし（初回起動）")
        return []

    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        articles = data.get("articles", [])
        logger.info(f"キャッシュ読み込み: {len(articles)}件の処理済みURL")
        return articles
    except (json.JSONDecodeError, ValueError):
        logger.warning("キャッシュファイルが破損。空のキャッシュとして扱います")
        return []


def filter_new_articles(articles: list[dict], cache: list[dict]) -> list[dict]:
    """キャッシュに存在しない（未処理の）記事だけを返す。"""
    cached_urls = {entry["url"] for entry in cache}
    new_articles = [a for a in articles if a["url"] not in cached_urls]

    skipped = len(articles) - len(new_articles)
    logger.info(f"キャッシュ照合: 新規 {len(new_articles)}件 / スキップ {skipped}件 / 全体 {len(articles)}件")
    return new_articles


def save_cache(cache: list[dict], new_articles: list[dict]) -> None:
    """処理済みURLを追記し、古いエントリを削除してファイルに保存する。"""
    now = datetime.now(timezone.utc).isoformat()
    for article in new_articles:
        cache.append({"url": article["url"], "processed_at": now})

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_EXPIRE_DAYS)
    before = len(cache)
    cache = [
        entry for entry in cache
        if datetime.fromisoformat(entry["processed_at"]) >= cutoff
    ]
    expired = before - len(cache)
    if expired:
        logger.info(f"期限切れキャッシュ削除: {expired}件")

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump({"articles": cache}, f, ensure_ascii=False, indent=2)

    logger.info(f"キャッシュ保存: {len(cache)}件")
