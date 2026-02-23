"""Discord Webhook経由で記事を通知するモジュール。"""

import logging
import time

import requests

from config import (
    DISCORD_COLORS,
    DISCORD_MAX_RETRIES,
    DISCORD_SEND_INTERVAL,
    DISCORD_WEBHOOK_BOT_LOG,
    DISCORD_WEBHOOKS,
)

logger = logging.getLogger(__name__)


def _truncate(text: str, max_len: int) -> str:
    """文字列が max_len を超える場合、末尾を切り詰めて '...' を付ける。"""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def build_embed(article: dict) -> dict:
    """記事データからDiscord Embed辞書を構築する。"""
    category = article.get("category", "not_ai")
    return {
        "title": _truncate(article.get("title", ""), 200),
        "url": article.get("url", ""),
        "description": _truncate(article.get("ai_summary", ""), 400),
        "color": DISCORD_COLORS.get(category, 0x808080),
        "fields": [
            {
                "name": "出典",
                "value": article.get("source", "不明"),
                "inline": True,
            }
        ],
    }


def _send_webhook(webhook_url: str, payload: dict) -> bool:
    """Webhookにペイロードを送信する。429/5xx時はリトライ。成功でTrue。"""
    for attempt in range(DISCORD_MAX_RETRIES + 1):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)

            if resp.status_code == 204:
                return True

            if resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                logger.warning(f"レート制限（429）。{retry_after}秒後にリトライ [{attempt + 1}/{DISCORD_MAX_RETRIES}]")
                time.sleep(retry_after)
                continue

            if resp.status_code >= 500:
                logger.warning(f"サーバーエラー（{resp.status_code}）。リトライ [{attempt + 1}/{DISCORD_MAX_RETRIES}]")
                time.sleep(2)
                continue

            logger.error(f"Discord送信失敗（{resp.status_code}）: {resp.text[:200]}")
            return False

        except requests.RequestException as e:
            logger.error(f"Discord送信例外: {e}")
            if attempt < DISCORD_MAX_RETRIES:
                time.sleep(2)
                continue
            return False

    logger.error("Discord送信: リトライ上限に達しました")
    return False


def notify_articles(articles: list[dict]) -> dict:
    """記事をカテゴリ別のチャンネルにDiscord通知する。送信結果の集計を返す。"""
    stats = {"sent": 0, "failed": 0, "skipped_no_webhook": 0, "failures": []}

    for i, article in enumerate(articles):
        category = article.get("category", "not_ai")
        webhook_url = DISCORD_WEBHOOKS.get(category, "")

        if not webhook_url:
            logger.warning(f"Webhook未設定のためスキップ: {category}")
            stats["skipped_no_webhook"] += 1
            continue

        embed = build_embed(article)
        payload = {"embeds": [embed]}

        logger.info(f"Discord送信 [{i + 1}/{len(articles)}] [{category}]: {article['title'][:50]}")

        if _send_webhook(webhook_url, payload):
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            stats["failures"].append({"url": article["url"], "reason": "送信失敗"})

        if i < len(articles) - 1:
            time.sleep(DISCORD_SEND_INTERVAL)

    logger.info(
        f"Discord通知完了: 送信 {stats['sent']}件 / 失敗 {stats['failed']}件"
        f" / Webhook未設定スキップ {stats['skipped_no_webhook']}件"
    )
    return stats


def send_bot_log(articles: list[dict], stats: dict) -> None:
    """実行結果サマリーを #bot-log チャンネルに送信する。"""
    if not DISCORD_WEBHOOK_BOT_LOG:
        logger.warning("DISCORD_WEBHOOK_BOT_LOG が未設定。サマリー送信をスキップ")
        return

    categories_count = {}
    for a in articles:
        cat = a.get("category", "not_ai")
        categories_count[cat] = categories_count.get(cat, 0) + 1

    lines = [
        f"**処理件数**: {len(articles)}件",
        f"**分類内訳**: dev_ai={categories_count.get('dev_ai', 0)} / industry={categories_count.get('industry', 0)} / not_ai={categories_count.get('not_ai', 0)}",
        f"**Discord送信**: 成功 {stats['sent']}件 / 失敗 {stats['failed']}件",
    ]

    if stats["failures"]:
        lines.append("**失敗した記事**:")
        for f in stats["failures"]:
            lines.append(f"- {f['url']} ({f['reason']})")

    payload = {
        "embeds": [
            {
                "title": "実行結果サマリー",
                "description": "\n".join(lines),
                "color": 0xFF0000 if stats["failed"] else 0x00FF00,
            }
        ]
    }

    if _send_webhook(DISCORD_WEBHOOK_BOT_LOG, payload):
        logger.info("bot-log サマリー送信完了")
    else:
        logger.error("bot-log サマリー送信失敗")
