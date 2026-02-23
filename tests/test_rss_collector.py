"""rss_collector モジュールのテスト。"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from rss_collector import (
    _extract_summary,
    _get_article_time,
    _is_within_hours,
    collect_articles,
    normalize_url,
)


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------
# RSSフィードから取得したURLには、トラッキング用のクエリパラメータ(?utm_source=...)や
# フラグメント(#section)、末尾スラッシュが付いていることがある。
# これらが違うだけの同一記事を別物扱いしないよう、正規化して統一する。
# ---------------------------------------------------------------------------


class TestNormalizeUrl:
    # ?utm_source=feed のようなクエリパラメータが消えること
    def test_クエリパラメータを除去(self):
        assert normalize_url("https://zenn.dev/articles/abc?utm_source=feed") == "https://zenn.dev/articles/abc"

    # #section1 のようなフラグメントが消えること
    def test_フラグメントを除去(self):
        assert normalize_url("https://zenn.dev/articles/abc#section1") == "https://zenn.dev/articles/abc"

    # 末尾の / が消えること（/articles/abc/ → /articles/abc）
    def test_末尾スラッシュを除去(self):
        assert normalize_url("https://zenn.dev/articles/abc/") == "https://zenn.dev/articles/abc"

    # クエリ・フラグメント・末尾スラッシュが全部ついていても正しく除去できること
    def test_全部まとめて除去(self):
        assert normalize_url("https://zenn.dev/articles/abc/?ref=top#s1") == "https://zenn.dev/articles/abc"

    # 余計なものがないURLは何も変わらずそのまま返ること
    def test_既に正規化済みのURLはそのまま(self):
        assert normalize_url("https://zenn.dev/articles/abc") == "https://zenn.dev/articles/abc"


# ---------------------------------------------------------------------------
# _get_article_time
# ---------------------------------------------------------------------------
# feedparser が返す記事の日時フィールドは、フィード形式によって名前が異なる。
# Atom フィードは updated_parsed、RSS 2.0 は published_parsed を持つことが多い。
# 両方ある場合は updated_parsed を優先し、両方なければ None を返す。
# ---------------------------------------------------------------------------


def _make_time_struct(dt: datetime) -> time.struct_time:
    """datetime から feedparser 互換の time.struct_time を作るヘルパー。"""
    return dt.timetuple()


class TestGetArticleTime:
    # updated_parsed と published_parsed が両方あるとき、updated_parsed の日時が返ること
    def test_updated_parsedを優先(self):
        updated = datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.utc)
        published = datetime(2026, 2, 19, 10, 0, 0, tzinfo=timezone.utc)
        entry = {
            "updated_parsed": _make_time_struct(updated),
            "published_parsed": _make_time_struct(published),
        }
        result = _get_article_time(entry)
        assert result == updated

    # updated_parsed がないとき、published_parsed の日時が返ること
    def test_updated_parsedが無ければpublished_parsedを使用(self):
        published = datetime(2026, 2, 19, 10, 0, 0, tzinfo=timezone.utc)
        entry = {"published_parsed": _make_time_struct(published)}
        result = _get_article_time(entry)
        assert result == published

    # どちらもないとき、None が返ること
    def test_両方無ければNone(self):
        entry = {}
        assert _get_article_time(entry) is None


# ---------------------------------------------------------------------------
# _is_within_hours
# ---------------------------------------------------------------------------
# 指定時間以内に公開された記事だけを残すためのフィルタ。
# 日時が不明(None)の記事は、取りこぼさないよう「含める」判定にする。
# ---------------------------------------------------------------------------


class TestIsWithinHours:
    # 12時間前の記事 → 24時間以内なので含まれる
    def test_24時間以内ならTrue(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=12)
        assert _is_within_hours(recent, 24) is True

    # 25時間前の記事 → 24時間を超えているので除外される
    def test_24時間超ならFalse(self):
        old = datetime.now(timezone.utc) - timedelta(hours=25)
        assert _is_within_hours(old, 24) is False

    # 24時間前ギリギリ（1秒だけ新しい）の記事 → 含まれる
    def test_ちょうど境界付近はTrue(self):
        almost_boundary = datetime.now(timezone.utc) - timedelta(hours=24) + timedelta(seconds=1)
        assert _is_within_hours(almost_boundary, 24) is True

    # 日時が不明（None）の記事 → 取りこぼし防止のため含める
    def test_NoneならTrue_取りこぼし防止(self):
        assert _is_within_hours(None, 24) is True


# ---------------------------------------------------------------------------
# _extract_summary
# ---------------------------------------------------------------------------
# RSSフィードの概要テキストは、フィード形式によって格納場所が異なる。
# まず summary フィールドを探し、なければ content フィールドから取る。
# ---------------------------------------------------------------------------


class TestExtractSummary:
    # summary フィールドに値があれば、それがそのまま返ること
    def test_summaryフィールドから取得(self):
        entry = {"summary": "これは概要です"}
        assert _extract_summary(entry) == "これは概要です"

    # summary が空のとき、content[0].value の値が返ること
    def test_summaryが空ならcontentにフォールバック(self):
        entry = {
            "summary": "",
            "content": [{"value": "コンテンツから取得"}],
        }
        assert _extract_summary(entry) == "コンテンツから取得"

    # summary も content もないとき、空文字が返ること
    def test_両方無ければ空文字(self):
        entry = {}
        assert _extract_summary(entry) == ""


# ---------------------------------------------------------------------------
# collect_articles
# ---------------------------------------------------------------------------
# 複数のフィードをまとめて取得し、同一URLの記事を除去して返す関数。
# 1つのフィードが失敗しても、他のフィードの記事は正常に返すことを確認する。
# （_fetch_feed をモックして、HTTPアクセスなしでテストする）
# ---------------------------------------------------------------------------


class TestCollectArticles:
    # ZennとQiitaに同じURLの記事がある場合、先に取得した方だけが残ること
    @patch("rss_collector._fetch_feed")
    def test_同一URLの記事は重複除去される(self, mock_fetch):
        mock_fetch.side_effect = [
            [
                {"title": "記事A", "url": "https://zenn.dev/articles/abc", "summary": "概要A", "source": "Zenn"},
            ],
            [
                {"title": "記事A(重複)", "url": "https://zenn.dev/articles/abc", "summary": "概要A", "source": "Qiita"},
                {"title": "記事B", "url": "https://qiita.com/items/xyz", "summary": "概要B", "source": "Qiita"},
            ],
        ]
        articles = collect_articles()
        assert len(articles) == 2
        assert articles[0]["title"] == "記事A"
        assert articles[1]["title"] == "記事B"

    # Zennのフィード取得が例外で失敗しても、Qiitaの記事は返ること
    @patch("rss_collector._fetch_feed")
    def test_フィード取得失敗でも他のフィードは処理される(self, mock_fetch):
        mock_fetch.side_effect = [
            Exception("接続エラー"),
            [{"title": "記事B", "url": "https://qiita.com/items/xyz", "summary": "概要B", "source": "Qiita"}],
        ]
        articles = collect_articles()
        assert len(articles) == 1
        assert articles[0]["source"] == "Qiita"
