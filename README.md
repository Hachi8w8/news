# AI News Discord Bot

ZennとQiitaのRSS記事をAIで分類・要約し、Discordに通知するBot。

---

## 開発環境のセットアップ

### 1. uv のインストール

`uv` はパッケージ管理と仮想環境を一括で扱える高速なPythonツール。

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

インストール後、ターミナルを再起動（またはシェルをリロード）してパスを反映させる。

```bash
# インストール確認
uv --version
```

### 2. プロジェクトの依存関係をインストール

```bash
# プロジェクトルートで実行
uv sync
```

これで仮想環境の作成とパッケージのインストールが一気に完了する。

### 3. スクリプトの実行

```bash
uv run python src/main.py
```

`python src/main.py` ではなく `uv run` を頭につけて実行する。仮想環境を自分で有効化する必要はない。

---

## 依存パッケージの追加方法

```bash
uv add パッケージ名
```

`pyproject.toml` と `uv.lock` が自動で更新される。

---

## 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各値を設定する。

```bash
cp .env.example .env
```

---

## ドキュメント

- `docs/REQUIREMENTS.md` - 要件定義
- `docs/rss/DESIGN.md` - RSS機能 設計書
- `docs/rss/PLAN_phase*.md` - RSS機能 実装計画（フェーズ別）
