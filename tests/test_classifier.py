"""classifier モジュールのテスト。"""

import json
from unittest.mock import MagicMock, patch

import pytest

from classifier import (
    _get_article_text,
    _strip_code_block,
    classify_articles,
    summarize_articles,
)


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


class TestClassifyArticles:
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
