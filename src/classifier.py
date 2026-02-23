"""記事のAI分類と要約を行うモジュール。LiteLLM経由でLLMを呼び出す。"""

import json
import logging
import re
import time

import litellm

from config import (
    CLASSIFY_BATCH_SIZE,
    CLASSIFY_MODEL,
    CLASSIFY_TEMPERATURE,
    LLM_MAX_RETRIES,
    LLM_REQUEST_INTERVAL,
    LLM_RETRY_DELAYS,
    SUMMARY_MODEL,
    SUMMARY_TEMPERATURE,
)

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"dev_ai", "industry", "not_ai"}

CLASSIFY_PROMPT = """\
あなたは技術記事の分類アシスタントです。
以下の記事リストを読み、各記事を次の3カテゴリのいずれかに分類してください。

カテゴリ:
- dev_ai: 開発に活かせるAIツール・API・実装テクニック・プロンプト手法・AIを使った開発事例
- industry: AI業界の動向・新モデル発表・研究論文・規制動向・企業のAI戦略
- not_ai: AI無関係の技術記事（Web開発、インフラ、言語機能、キャリアなど）

判定基準:
- 記事の主題がAIに関連しているかで判断する
- AIを「使う」記事（プロンプト設計、API活用など）は dev_ai
- AIについて「報じる」記事（新モデル、業界動向など）は industry
- AIに少し触れるだけで主題が別のものは not_ai

以下のJSON形式で返答してください（JSON以外のテキストは不要です）:
[
  {{"url": "記事URL", "category": "カテゴリ名"}},
  ...
]

--- 記事リスト ---
{articles}"""

SUMMARY_PROMPT = """\
以下の技術記事を日本語で要約してください。

要件:
- 2〜3行、最大400文字以内
- 記事の核心（何を解決するか、何が新しいか、何が学べるか）を伝える
- 専門用語はそのまま使ってよい
- 要約のみを返答し、前置きや補足は不要

--- 記事 ---
タイトル: {title}
本文:
{content}"""


def _get_article_text(article: dict) -> str:
    """記事の入力テキストを構成する。本文がなければタイトル+概要で代替。"""
    if article.get("content"):
        return f"タイトル: {article['title']}\nURL: {article['url']}\n本文:\n{article['content']}"
    return f"タイトル: {article['title']}\nURL: {article['url']}\n概要:\n{article.get('summary', '')}"


def _strip_code_block(text: str) -> str:
    """LLMレスポンスからMarkdownのコードブロック記法を除去する。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _call_llm(prompt: str, temperature: float, model: str) -> str:
    """LLMを呼び出してレスポンスのテキストを返す。429/5xxエラー時はリトライする。"""
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
            return response.choices[0].message.content
        except litellm.RateLimitError:
            if attempt < LLM_MAX_RETRIES:
                delay = LLM_RETRY_DELAYS[attempt]
                logger.warning(f"レート制限（429）。{delay}秒後にリトライ [{attempt + 1}/{LLM_MAX_RETRIES}]")
                time.sleep(delay)
            else:
                raise
        except (litellm.InternalServerError, litellm.ServiceUnavailableError):
            if attempt < LLM_MAX_RETRIES:
                delay = LLM_RETRY_DELAYS[attempt]
                logger.warning(f"サーバーエラー（5xx/503）。{delay}秒後にリトライ [{attempt + 1}/{LLM_MAX_RETRIES}]")
                time.sleep(delay)
            else:
                raise


def classify_articles(articles: list[dict]) -> list[dict]:
    """記事をバッチでLLMに送り、カテゴリを付与して返す。"""
    # バッチに分割
    batches = [articles[i:i + CLASSIFY_BATCH_SIZE] for i in range(0, len(articles), CLASSIFY_BATCH_SIZE)]

    url_to_category: dict[str, str] = {}

    for batch_idx, batch in enumerate(batches):
        logger.info(f"分類バッチ [{batch_idx + 1}/{len(batches)}]: {len(batch)}件")

        articles_text = "\n\n".join(_get_article_text(a) for a in batch)
        prompt = CLASSIFY_PROMPT.format(articles=articles_text)

        try:
            raw_response = _call_llm(prompt, CLASSIFY_TEMPERATURE, CLASSIFY_MODEL)
            parsed = json.loads(_strip_code_block(raw_response))

            for item in parsed:
                url = item.get("url", "")
                category = item.get("category", "not_ai")
                if category not in VALID_CATEGORIES:
                    logger.warning(f"不明なカテゴリ '{category}' → not_ai に変更: {url}")
                    category = "not_ai"
                url_to_category[url] = category

        except Exception:
            logger.exception(f"分類バッチ {batch_idx + 1} 失敗。バッチ内の記事は not_ai として扱います")
            for a in batch:
                url_to_category[a["url"]] = "not_ai"

        if batch_idx < len(batches) - 1:
            time.sleep(LLM_REQUEST_INTERVAL)

    # 各記事に category を付与
    for article in articles:
        article["category"] = url_to_category.get(article["url"], "not_ai")

    categories_count = {}
    for a in articles:
        categories_count[a["category"]] = categories_count.get(a["category"], 0) + 1
    logger.info(f"分類結果: {categories_count}")

    return articles


def summarize_articles(articles: list[dict]) -> list[dict]:
    """各記事ごとにLLMで要約を生成する。"""
    total = len(articles)

    for i, article in enumerate(articles):
        logger.info(f"要約生成中 [{i + 1}/{total}]: {article['title'][:50]}")

        content = article.get("content") or article.get("summary", "")
        prompt = SUMMARY_PROMPT.format(title=article["title"], content=content)

        try:
            raw_response = _call_llm(prompt, SUMMARY_TEMPERATURE, SUMMARY_MODEL)
            article["ai_summary"] = raw_response.strip()[:400]
        except Exception:
            logger.exception(f"要約生成失敗: {article['url']}")
            article["ai_summary"] = ""

        if i < total - 1:
            time.sleep(LLM_REQUEST_INTERVAL)

    success = sum(1 for a in articles if a.get("ai_summary"))
    logger.info(f"要約完了: 成功 {success}件 / 失敗 {total - success}件 / 合計 {total}件")

    return articles
