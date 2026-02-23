"""scraper モジュールのテスト。"""

from unittest.mock import patch

from scraper import fetch_content, scrape_articles


# ---------------------------------------------------------------------------
# fetch_content
# ---------------------------------------------------------------------------
# 単一URLから本文を取得する関数。trafilatura の fetch_url / extract をモックして、
# HTTPアクセスなしでテストする。
# ---------------------------------------------------------------------------


class TestFetchContent:
    # HTML取得・本文抽出ともに成功した場合、本文テキストが返ること
    @patch("scraper.trafilatura.extract")
    @patch("scraper.trafilatura.fetch_url")
    def test_正常に本文が取得できる(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html>...</html>"
        mock_extract.return_value = "A" * 200
        result = fetch_content("https://example.com/article")
        assert result == "A" * 200

    # fetch_url が None を返した場合（ネットワークエラーなど）、None が返ること
    @patch("scraper.trafilatura.fetch_url")
    def test_HTML取得失敗でNone(self, mock_fetch):
        mock_fetch.return_value = None
        result = fetch_content("https://example.com/article")
        assert result is None

    # extract が None を返した場合（本文抽出失敗）、None が返ること
    @patch("scraper.trafilatura.extract")
    @patch("scraper.trafilatura.fetch_url")
    def test_本文抽出失敗でNone(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html>...</html>"
        mock_extract.return_value = None
        result = fetch_content("https://example.com/article")
        assert result is None

    # 本文が100文字未満の場合、取得失敗とみなして None が返ること
    @patch("scraper.trafilatura.extract")
    @patch("scraper.trafilatura.fetch_url")
    def test_100文字未満は失敗扱い(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html>...</html>"
        mock_extract.return_value = "短いテキスト"
        result = fetch_content("https://example.com/article")
        assert result is None

    # ちょうど100文字の場合は成功とみなすこと
    @patch("scraper.trafilatura.extract")
    @patch("scraper.trafilatura.fetch_url")
    def test_ちょうど100文字は成功(self, mock_fetch, mock_extract):
        mock_fetch.return_value = "<html>...</html>"
        mock_extract.return_value = "A" * 100
        result = fetch_content("https://example.com/article")
        assert result == "A" * 100

    # trafilatura 内部で例外が発生しても、None を返して処理が止まらないこと
    @patch("scraper.trafilatura.fetch_url")
    def test_例外発生時もNoneを返す(self, mock_fetch):
        mock_fetch.side_effect = Exception("接続タイムアウト")
        result = fetch_content("https://example.com/article")
        assert result is None


# ---------------------------------------------------------------------------
# scrape_articles
# ---------------------------------------------------------------------------
# 記事リスト全体を処理する関数。fetch_content をモックして、
# 成功・失敗のカウントやリクエスト間隔の動作をテストする。
# ---------------------------------------------------------------------------


class TestScrapeArticles:
    # 全記事の content フィールドに本文が追加されること
    @patch("scraper.fetch_content")
    @patch("scraper.time.sleep")
    def test_各記事にcontentが追加される(self, mock_sleep, mock_fetch):
        mock_fetch.side_effect = ["本文A" * 50, "本文B" * 50]
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "summary": "", "source": "Zenn"},
            {"title": "記事B", "url": "https://example.com/b", "summary": "", "source": "Qiita"},
        ]
        result = scrape_articles(articles)
        assert result[0]["content"] == "本文A" * 50
        assert result[1]["content"] == "本文B" * 50

    # 取得失敗した記事は content=None となり、処理が止まらないこと
    @patch("scraper.fetch_content")
    @patch("scraper.time.sleep")
    def test_失敗した記事はcontentがNoneで続行(self, mock_sleep, mock_fetch):
        mock_fetch.side_effect = [None, "本文B" * 50]
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "summary": "", "source": "Zenn"},
            {"title": "記事B", "url": "https://example.com/b", "summary": "", "source": "Qiita"},
        ]
        result = scrape_articles(articles)
        assert result[0]["content"] is None
        assert result[1]["content"] == "本文B" * 50

    # 記事間に5秒のスリープが入ること（最後の記事のあとは待たない）
    @patch("scraper.fetch_content")
    @patch("scraper.time.sleep")
    def test_記事間に5秒スリープが入る(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = "本文" * 50
        articles = [
            {"title": "記事A", "url": "https://example.com/a", "summary": "", "source": "Zenn"},
            {"title": "記事B", "url": "https://example.com/b", "summary": "", "source": "Qiita"},
            {"title": "記事C", "url": "https://example.com/c", "summary": "", "source": "Zenn"},
        ]
        scrape_articles(articles)
        # 3件なのでスリープは2回（最後の記事のあとは待たない）
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(5)

    # 空の記事リストを渡してもエラーにならないこと
    @patch("scraper.fetch_content")
    @patch("scraper.time.sleep")
    def test_空リストでもエラーにならない(self, mock_sleep, mock_fetch):
        result = scrape_articles([])
        assert result == []
        mock_fetch.assert_not_called()
        mock_sleep.assert_not_called()
