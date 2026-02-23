"""cache_manager モジュールのテスト。"""

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from cache_manager import filter_new_articles, load_cache, save_cache


# ---------------------------------------------------------------------------
# load_cache
# ---------------------------------------------------------------------------
# キャッシュファイルの読み込みをテストする。
# ファイルが存在しない場合や壊れている場合でもエラーにならないことが重要。
# ---------------------------------------------------------------------------


class TestLoadCache:
    # キャッシュファイルが存在しない場合、空リストを返すこと
    def test_ファイルなしで空リスト(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(tmp_path / "nonexistent.json"))
        result = load_cache()
        assert result == []

    # 正常なキャッシュファイルから処理済みURLを読み込めること
    def test_正常なファイルから読み込み(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        data = {"articles": [{"url": "https://example.com/a", "processed_at": "2026-02-20T00:00:00+00:00"}]}
        cache_file.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))

        result = load_cache()
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/a"

    # JSONが壊れている場合、空リストを返すこと（エラーで止まらない）
    def test_壊れたJSONで空リスト(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        cache_file.write_text("{broken json", encoding="utf-8")
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))

        result = load_cache()
        assert result == []

    # articles キーがない場合、空リストを返すこと
    def test_articlesキーなしで空リスト(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        cache_file.write_text("{}", encoding="utf-8")
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))

        result = load_cache()
        assert result == []


# ---------------------------------------------------------------------------
# filter_new_articles
# ---------------------------------------------------------------------------
# 記事リストからキャッシュ済みのものを除外する。
# ---------------------------------------------------------------------------


class TestFilterNewArticles:
    # キャッシュにないURLの記事だけが返ること
    def test_キャッシュ済みの記事を除外(self):
        articles = [
            {"title": "記事A", "url": "https://example.com/a"},
            {"title": "記事B", "url": "https://example.com/b"},
            {"title": "記事C", "url": "https://example.com/c"},
        ]
        cache = [
            {"url": "https://example.com/a", "processed_at": "2026-02-20T00:00:00+00:00"},
        ]

        result = filter_new_articles(articles, cache)
        assert len(result) == 2
        assert result[0]["url"] == "https://example.com/b"
        assert result[1]["url"] == "https://example.com/c"

    # キャッシュが空なら全記事が返ること
    def test_キャッシュ空で全記事(self):
        articles = [
            {"title": "記事A", "url": "https://example.com/a"},
            {"title": "記事B", "url": "https://example.com/b"},
        ]
        result = filter_new_articles(articles, [])
        assert len(result) == 2

    # 全記事がキャッシュ済みなら空リストが返ること
    def test_全記事キャッシュ済みで空(self):
        articles = [
            {"title": "記事A", "url": "https://example.com/a"},
        ]
        cache = [
            {"url": "https://example.com/a", "processed_at": "2026-02-20T00:00:00+00:00"},
        ]
        result = filter_new_articles(articles, cache)
        assert result == []


# ---------------------------------------------------------------------------
# save_cache
# ---------------------------------------------------------------------------
# 処理済みURLの追記と、30日超の古いエントリの自動削除をテストする。
# ---------------------------------------------------------------------------


class TestSaveCache:
    # 新規記事がキャッシュファイルに追記されること
    def test_新規URLが追記される(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))
        monkeypatch.setattr("cache_manager.CACHE_DIR", str(tmp_path))

        cache = []
        new_articles = [
            {"url": "https://example.com/a", "title": "記事A"},
            {"url": "https://example.com/b", "title": "記事B"},
        ]

        save_cache(cache, new_articles)

        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert len(saved["articles"]) == 2
        urls = {a["url"] for a in saved["articles"]}
        assert urls == {"https://example.com/a", "https://example.com/b"}

    # 既存のキャッシュに新規分が追加されること
    def test_既存キャッシュに追記(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))
        monkeypatch.setattr("cache_manager.CACHE_DIR", str(tmp_path))

        now = datetime.now(timezone.utc).isoformat()
        cache = [{"url": "https://example.com/old", "processed_at": now}]
        new_articles = [{"url": "https://example.com/new", "title": "新記事"}]

        save_cache(cache, new_articles)

        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert len(saved["articles"]) == 2

    # 30日以上古いエントリが削除されること
    def test_30日超の古いURLが削除される(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "processed_urls.json"
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))
        monkeypatch.setattr("cache_manager.CACHE_DIR", str(tmp_path))

        old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        recent_date = datetime.now(timezone.utc).isoformat()

        cache = [
            {"url": "https://example.com/old", "processed_at": old_date},
            {"url": "https://example.com/recent", "processed_at": recent_date},
        ]

        save_cache(cache, [])

        saved = json.loads(cache_file.read_text(encoding="utf-8"))
        assert len(saved["articles"]) == 1
        assert saved["articles"][0]["url"] == "https://example.com/recent"

    # .cache ディレクトリが存在しなくても自動で作成されること
    def test_ディレクトリ自動作成(self, tmp_path, monkeypatch):
        cache_dir = tmp_path / "new_cache_dir"
        cache_file = cache_dir / "processed_urls.json"
        monkeypatch.setattr("cache_manager.CACHE_FILE", str(cache_file))
        monkeypatch.setattr("cache_manager.CACHE_DIR", str(cache_dir))

        save_cache([], [{"url": "https://example.com/a", "title": "記事"}])

        assert cache_dir.exists()
        assert cache_file.exists()
