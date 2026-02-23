"""notifier モジュールのテスト。"""

from unittest.mock import MagicMock, patch

import pytest

from notifier import _truncate, build_embed, notify_articles, send_bot_log


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------
# 文字列の切り詰め処理。タイトルや要約がDiscordの制限を超えないようにする。
# ---------------------------------------------------------------------------


class TestTruncate:
    # 制限以下の文字列はそのまま返ること
    def test_制限以下はそのまま(self):
        assert _truncate("短い文字列", 200) == "短い文字列"

    # ちょうど制限と同じ長さはそのまま返ること
    def test_ちょうど制限と同じ(self):
        text = "あ" * 200
        assert _truncate(text, 200) == text

    # 制限を超えた場合は切り詰めて ... が付くこと
    def test_制限超過で切り詰め(self):
        text = "あ" * 250
        result = _truncate(text, 200)
        assert len(result) == 200
        assert result.endswith("...")


# ---------------------------------------------------------------------------
# build_embed
# ---------------------------------------------------------------------------
# 記事データからDiscord Embed形式の辞書を構築する。
# ---------------------------------------------------------------------------


class TestBuildEmbed:
    # dev_ai カテゴリの記事で正しいEmbed構造が作られること
    def test_dev_aiのEmbed構築(self):
        article = {
            "title": "AI記事タイトル",
            "url": "https://example.com/a",
            "ai_summary": "AI記事の要約です",
            "category": "dev_ai",
            "source": "Zenn",
        }
        embed = build_embed(article)
        assert embed["title"] == "AI記事タイトル"
        assert embed["url"] == "https://example.com/a"
        assert embed["description"] == "AI記事の要約です"
        assert embed["color"] == 0x00FF00
        assert embed["fields"][0]["value"] == "Zenn"

    # industry カテゴリで青色が設定されること
    def test_industryは青色(self):
        article = {"title": "業界記事", "url": "https://example.com/b", "ai_summary": "要約", "category": "industry", "source": "Qiita"}
        embed = build_embed(article)
        assert embed["color"] == 0x0088FF

    # not_ai カテゴリでグレーが設定されること
    def test_not_aiはグレー(self):
        article = {"title": "技術記事", "url": "https://example.com/c", "ai_summary": "要約", "category": "not_ai", "source": "Zenn"}
        embed = build_embed(article)
        assert embed["color"] == 0x808080

    # タイトルが200文字を超える場合に切り詰められること
    def test_タイトル200文字超で切り詰め(self):
        article = {"title": "あ" * 250, "url": "https://example.com", "ai_summary": "要約", "category": "dev_ai", "source": "Zenn"}
        embed = build_embed(article)
        assert len(embed["title"]) == 200
        assert embed["title"].endswith("...")

    # 要約が400文字を超える場合に切り詰められること
    def test_要約400文字超で切り詰め(self):
        article = {"title": "タイトル", "url": "https://example.com", "ai_summary": "あ" * 500, "category": "dev_ai", "source": "Zenn"}
        embed = build_embed(article)
        assert len(embed["description"]) == 400
        assert embed["description"].endswith("...")


# ---------------------------------------------------------------------------
# notify_articles
# ---------------------------------------------------------------------------
# 記事をカテゴリ別のチャンネルにDiscord送信する。
# HTTP通信はモックする。
# ---------------------------------------------------------------------------


class TestNotifyArticles:
    # 各記事が対応するWebhookに送信されること
    @patch("notifier.time.sleep")
    @patch("notifier._send_webhook")
    def test_正常に送信される(self, mock_send, mock_sleep):
        mock_send.return_value = True
        articles = [
            {"title": "AI記事", "url": "https://example.com/a", "ai_summary": "要約", "category": "dev_ai", "source": "Zenn"},
            {"title": "業界記事", "url": "https://example.com/b", "ai_summary": "要約", "category": "industry", "source": "Qiita"},
        ]
        with patch("notifier.DISCORD_WEBHOOKS", {"dev_ai": "https://hook/1", "industry": "https://hook/2", "not_ai": "https://hook/3"}):
            stats = notify_articles(articles)

        assert stats["sent"] == 2
        assert stats["failed"] == 0
        assert mock_send.call_count == 2

    # Webhook未設定のカテゴリはスキップされること
    @patch("notifier.time.sleep")
    @patch("notifier._send_webhook")
    def test_Webhook未設定でスキップ(self, mock_send, mock_sleep):
        mock_send.return_value = True
        articles = [
            {"title": "AI記事", "url": "https://example.com/a", "ai_summary": "要約", "category": "dev_ai", "source": "Zenn"},
        ]
        with patch("notifier.DISCORD_WEBHOOKS", {"dev_ai": "", "industry": "", "not_ai": ""}):
            stats = notify_articles(articles)

        assert stats["skipped_no_webhook"] == 1
        assert stats["sent"] == 0
        assert mock_send.call_count == 0

    # 送信失敗した記事が failures に記録されること
    @patch("notifier.time.sleep")
    @patch("notifier._send_webhook")
    def test_送信失敗がfailuresに記録(self, mock_send, mock_sleep):
        mock_send.return_value = False
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "ai_summary": "要約", "category": "dev_ai", "source": "Zenn"},
        ]
        with patch("notifier.DISCORD_WEBHOOKS", {"dev_ai": "https://hook/1", "industry": "", "not_ai": ""}):
            stats = notify_articles(articles)

        assert stats["failed"] == 1
        assert len(stats["failures"]) == 1
        assert stats["failures"][0]["url"] == "https://example.com/a"


# ---------------------------------------------------------------------------
# send_bot_log
# ---------------------------------------------------------------------------
# 実行結果サマリーを #bot-log に送信する。
# ---------------------------------------------------------------------------


class TestSendBotLog:
    # サマリーが正しく送信されること
    @patch("notifier._send_webhook")
    def test_サマリーが送信される(self, mock_send):
        mock_send.return_value = True
        articles = [
            {"title": "AI記事", "url": "https://example.com/a", "category": "dev_ai"},
            {"title": "業界記事", "url": "https://example.com/b", "category": "industry"},
        ]
        stats = {"sent": 2, "failed": 0, "failures": []}

        with patch("notifier.DISCORD_WEBHOOK_BOT_LOG", "https://hook/log"):
            send_bot_log(articles, stats)

        mock_send.assert_called_once()
        payload = mock_send.call_args[0][1]
        desc = payload["embeds"][0]["description"]
        assert "2件" in desc
        assert "dev_ai=1" in desc
        assert payload["embeds"][0]["color"] == 0x00FF00

    # 失敗がある場合、赤色でサマリーが送られること
    @patch("notifier._send_webhook")
    def test_失敗ありで赤色サマリー(self, mock_send):
        mock_send.return_value = True
        articles = [{"title": "記事", "url": "https://example.com/a", "category": "dev_ai"}]
        stats = {"sent": 0, "failed": 1, "failures": [{"url": "https://example.com/a", "reason": "送信失敗"}]}

        with patch("notifier.DISCORD_WEBHOOK_BOT_LOG", "https://hook/log"):
            send_bot_log(articles, stats)

        payload = mock_send.call_args[0][1]
        assert payload["embeds"][0]["color"] == 0xFF0000
        assert "https://example.com/a" in payload["embeds"][0]["description"]

    # フォールバックなしの場合、緑色でGemini直接の件数が表示されること
    @patch("notifier._send_webhook")
    def test_フォールバックなしで緑色(self, mock_send):
        mock_send.return_value = True
        articles = [{"title": "記事", "url": "https://example.com/a", "category": "dev_ai"}]
        stats = {"sent": 1, "failed": 0, "failures": []}
        llm_stats = {"primary_calls": 2, "fallback_calls": 0, "fallback_cost": 0.0, "fallback_prompt_tokens": 0, "fallback_completion_tokens": 0}

        with patch("notifier.DISCORD_WEBHOOK_BOT_LOG", "https://hook/log"):
            send_bot_log(articles, stats, llm_stats)

        payload = mock_send.call_args[0][1]
        desc = payload["embeds"][0]["description"]
        assert "Gemini直接 2回" in desc
        assert "フォールバックなし" in desc
        assert payload["embeds"][0]["color"] == 0x00FF00

    # フォールバック発生時、黄色でコスト情報が表示されること
    @patch("notifier._send_webhook")
    def test_フォールバック発生で黄色とコスト表示(self, mock_send):
        mock_send.return_value = True
        articles = [{"title": "記事", "url": "https://example.com/a", "category": "dev_ai"}]
        stats = {"sent": 1, "failed": 0, "failures": []}
        llm_stats = {"primary_calls": 3, "fallback_calls": 6, "fallback_cost": 0.0012, "fallback_prompt_tokens": 15230, "fallback_completion_tokens": 2450}

        with patch("notifier.DISCORD_WEBHOOK_BOT_LOG", "https://hook/log"):
            send_bot_log(articles, stats, llm_stats)

        payload = mock_send.call_args[0][1]
        desc = payload["embeds"][0]["description"]
        assert "Gemini直接 3回" in desc
        assert "フォールバック(OpenRouter) 6回" in desc
        assert "$0.0012" in desc
        assert "15,230" in desc
        assert payload["embeds"][0]["color"] == 0xFFAA00

    # DISCORD_WEBHOOK_BOT_LOG 未設定なら送信しないこと
    @patch("notifier._send_webhook")
    def test_Webhook未設定で送信しない(self, mock_send):
        with patch("notifier.DISCORD_WEBHOOK_BOT_LOG", ""):
            send_bot_log([], {"sent": 0, "failed": 0, "failures": []})

        mock_send.assert_not_called()
