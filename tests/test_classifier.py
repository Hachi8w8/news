"""classifier モジュールのテスト。"""

import json
from unittest.mock import MagicMock, patch

import litellm
import pytest

import classifier
from classifier import (
    _call_llm,
    _get_article_text,
    _strip_code_block,
    classify_articles,
    get_llm_stats,
    summarize_articles,
)


def _make_response(content="response", prompt_tokens=100, completion_tokens=50):
    """テスト用のLLMレスポンスモックを生成する。"""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    resp.model = "test-model"
    return resp


# ---------------------------------------------------------------------------
# _strip_code_block
# ---------------------------------------------------------------------------
# LLMのレスポンスは ```json ... ``` のコードブロックで囲まれることがある。
# JSONパース前にこのコードブロックを除去する必要がある。
# ---------------------------------------------------------------------------


class TestStripCodeBlock:
    # ```json ... ``` で囲まれたレスポンスからJSONだけ取り出せること
    def test_jsonコードブロックを除去(self):
        text = '```json\n[{"url": "https://example.com", "category": "dev_ai"}]\n```'
        result = _strip_code_block(text)
        assert result == '[{"url": "https://example.com", "category": "dev_ai"}]'

    # ``` ... ```（言語指定なし）でも除去できること
    def test_言語指定なしのコードブロックを除去(self):
        text = '```\n[{"url": "https://example.com", "category": "dev_ai"}]\n```'
        result = _strip_code_block(text)
        assert result == '[{"url": "https://example.com", "category": "dev_ai"}]'

    # コードブロックがないプレーンなJSONはそのまま返ること
    def test_コードブロックなしはそのまま(self):
        text = '[{"url": "https://example.com", "category": "dev_ai"}]'
        result = _strip_code_block(text)
        assert result == text


# ---------------------------------------------------------------------------
# _get_article_text
# ---------------------------------------------------------------------------
# LLMに渡す入力テキストを組み立てる関数。
# 本文がある場合は全文を使い、Noneの場合はタイトル+概要で代替する。
# ---------------------------------------------------------------------------


class TestGetArticleText:
    # 本文がある場合、タイトル・URL・本文で構成されること
    def test_本文ありの場合(self):
        article = {"title": "テスト記事", "url": "https://example.com", "content": "本文テキスト", "summary": "概要"}
        result = _get_article_text(article)
        assert "本文:" in result
        assert "本文テキスト" in result
        assert "概要" not in result

    # 本文がNoneの場合、タイトル・URL・概要で代替されること
    def test_本文Noneの場合は概要で代替(self):
        article = {"title": "テスト記事", "url": "https://example.com", "content": None, "summary": "概要テキスト"}
        result = _get_article_text(article)
        assert "概要:" in result
        assert "概要テキスト" in result


# ---------------------------------------------------------------------------
# classify_articles
# ---------------------------------------------------------------------------
# 記事リストをバッチでLLMに送り、カテゴリを付与する関数。
# LLMの呼び出し(_call_llm)をモックしてテストする。
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# _call_llm（フォールバック）
# ---------------------------------------------------------------------------
# プライマリモデルでレート制限が来たらフォールバックモデルに切り替わること。
# ---------------------------------------------------------------------------


class TestCallLlmFallback:
    def setup_method(self):
        classifier._use_fallback = False
        classifier._llm_stats.update(
            primary_calls=0, fallback_calls=0, fallback_cost=0.0,
            fallback_prompt_tokens=0, fallback_completion_tokens=0,
        )

    # プライマリが成功すればそのまま返り、primary_calls がカウントされること
    @patch("classifier._call_llm_single")
    def test_プライマリ成功(self, mock_single):
        mock_single.return_value = _make_response("response")
        result = _call_llm("prompt", 0.1, "primary", "fallback")
        assert result == "response"
        mock_single.assert_called_once_with("prompt", 0.1, "primary")
        assert classifier._use_fallback is False
        assert get_llm_stats()["primary_calls"] == 1
        assert get_llm_stats()["fallback_calls"] == 0

    # プライマリで429 → フォールバックに切り替わり、fallback_calls がカウントされること
    @patch("classifier.litellm.completion_cost", return_value=0.001)
    @patch("classifier._call_llm_single")
    def test_プライマリ429でフォールバック(self, mock_single, mock_cost):
        mock_single.side_effect = [
            litellm.RateLimitError("rate limit", "model", "provider"),
            _make_response("fallback response", prompt_tokens=200, completion_tokens=80),
        ]
        result = _call_llm("prompt", 0.1, "primary", "fallback")
        assert result == "fallback response"
        assert classifier._use_fallback is True
        assert mock_single.call_count == 2
        stats = get_llm_stats()
        assert stats["primary_calls"] == 0
        assert stats["fallback_calls"] == 1
        assert stats["fallback_prompt_tokens"] == 200
        assert stats["fallback_completion_tokens"] == 80
        assert stats["fallback_cost"] == 0.001

    # フォールバック中はプライマリを試さないこと
    @patch("classifier.litellm.completion_cost", return_value=0.0005)
    @patch("classifier._call_llm_single")
    def test_フォールバック中はプライマリをスキップ(self, mock_single, mock_cost):
        classifier._use_fallback = True
        mock_single.return_value = _make_response("fallback response")
        result = _call_llm("prompt", 0.1, "primary", "fallback")
        assert result == "fallback response"
        mock_single.assert_called_once_with("prompt", 0.1, "fallback")
        assert get_llm_stats()["fallback_calls"] == 1


class TestClassifyArticles:
    def setup_method(self):
        classifier._use_fallback = False

    # LLMが正しいJSON応答を返した場合、各記事に正しいカテゴリが付くこと
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_正常に分類される(self, mock_sleep, mock_llm):
        mock_llm.return_value = json.dumps([
            {"url": "https://example.com/a", "category": "dev_ai"},
            {"url": "https://example.com/b", "category": "not_ai"},
        ])
        articles = [
            {"title": "AI記事", "url": "https://example.com/a", "content": "AI本文", "summary": ""},
            {"title": "Web記事", "url": "https://example.com/b", "content": "Web本文", "summary": ""},
        ]
        result = classify_articles(articles)
        assert result[0]["category"] == "dev_ai"
        assert result[1]["category"] == "not_ai"

    # LLMが不明なカテゴリを返した場合、not_ai にフォールバックすること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_不明なカテゴリはnot_aiになる(self, mock_sleep, mock_llm):
        mock_llm.return_value = json.dumps([
            {"url": "https://example.com/a", "category": "unknown_category"},
        ])
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "content": "本文", "summary": ""},
        ]
        result = classify_articles(articles)
        assert result[0]["category"] == "not_ai"

    # LLM呼び出しが例外を投げた場合、バッチ内の記事が全て not_ai になること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_API失敗時はバッチ全体がnot_ai(self, mock_sleep, mock_llm):
        mock_llm.side_effect = Exception("API error")
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "content": "本文", "summary": ""},
            {"title": "記事B", "url": "https://example.com/b", "content": "本文", "summary": ""},
        ]
        result = classify_articles(articles)
        assert all(a["category"] == "not_ai" for a in result)


# ---------------------------------------------------------------------------
# summarize_articles
# ---------------------------------------------------------------------------
# 各記事1件ずつLLMで要約を生成する関数。
# LLMの呼び出し(_call_llm)をモックしてテストする。
# ---------------------------------------------------------------------------


class TestSummarizeArticles:
    def setup_method(self):
        classifier._use_fallback = False

    # LLMが要約を返した場合、ai_summary フィールドに格納されること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_正常に要約される(self, mock_sleep, mock_llm):
        mock_llm.return_value = "これはAIに関する要約です。"
        articles = [
            {"title": "AI記事", "url": "https://example.com/a", "content": "AI本文", "summary": "", "category": "dev_ai"},
        ]
        result = summarize_articles(articles)
        assert result[0]["ai_summary"] == "これはAIに関する要約です。"

    # LLM呼び出しが失敗した場合、ai_summary が空文字になり処理は続行すること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_要約失敗時は空文字で続行(self, mock_sleep, mock_llm):
        mock_llm.side_effect = [Exception("API error"), "2件目の要約"]
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "content": "本文", "summary": "", "category": "dev_ai"},
            {"title": "記事B", "url": "https://example.com/b", "content": "本文", "summary": "", "category": "not_ai"},
        ]
        result = summarize_articles(articles)
        assert result[0]["ai_summary"] == ""
        assert result[1]["ai_summary"] == "2件目の要約"

    # 400文字を超える要約は400文字で切り詰められること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_400文字超の要約は切り詰め(self, mock_sleep, mock_llm):
        mock_llm.return_value = "あ" * 500
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "content": "本文", "summary": "", "category": "dev_ai"},
        ]
        result = summarize_articles(articles)
        assert len(result[0]["ai_summary"]) == 400

    # 本文がNoneの記事でも概要を使って要約が生成されること
    @patch("classifier._call_llm")
    @patch("classifier.time.sleep")
    def test_本文Noneでも概要で要約される(self, mock_sleep, mock_llm):
        mock_llm.return_value = "概要ベースの要約"
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "content": None, "summary": "概要テキスト", "category": "dev_ai"},
        ]
        result = summarize_articles(articles)
        assert result[0]["ai_summary"] == "概要ベースの要約"
        # プロンプトに概要テキストが含まれていること
        call_args = mock_llm.call_args[0][0]
        assert "概要テキスト" in call_args
