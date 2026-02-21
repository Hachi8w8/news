# Phase 6: GitHub Actions 自動化

## 目標

GitHub Actions を使って、毎朝7時（JST）に自動でBotを実行する。

**完了条件**:
- スケジュール実行（毎朝07:00 JST）が動作する
- 処理済みURLキャッシュがワークフロー実行をまたいで引き継がれる
- APIキーなどのシークレットが安全に設定されている
- 手動実行（動作確認用）もできる

---

## 追加するファイル

```
.github/
└── workflows/
    └── rss_bot.yml   ← 新規追加
```

---

## ワークフローの設計

### 実行トリガー

- **スケジュール**: 毎日 07:00 JST（= UTC 22:00）に自動実行
- **手動実行**: GitHub ActionsのUIから手動でも実行できるようにする

### 実行環境

- OS: `ubuntu-latest`
- Python: `3.12`
- タイムアウト: 10分（処理時間見積もり約5分に対して余裕を持たせる）

### ステップ構成

```
1. リポジトリのチェックアウト
2. uv のセットアップ
3. 依存パッケージのインストール（uv sync）
4. キャッシュの復元（processed_urls.json）
5. Botの実行（python src/main.py）
6. キャッシュの保存（processed_urls.json）
```

### uv のセットアップ

GitHub Actions で `uv` を使うには、公式の `astral-sh/setup-uv` アクションを使う。

```yaml
- uses: astral-sh/setup-uv@v4
```

これにより `uv` コマンドが使えるようになり、`uv sync` で依存パッケージをインストールできる。Python のセットアップも `uv` が自動で行うため、`actions/setup-python` は不要。

---

## キャッシュ設計

### なぜキャッシュが必要か

GitHub Actions は実行のたびに環境がリセットされる。ローカルに保存した `.cache/processed_urls.json` も消えてしまうため、GitHub Actions Cache に退避・復元する仕組みが必要。

### キャッシュの復元・保存

- **復元**: Bot実行の前にキャッシュを `.cache/processed_urls.json` に展開する
- **保存**: Bot実行の後（成功・失敗問わず）にキャッシュを保存する
- キャッシュが存在しない初回は復元がスキップされ、Bot側で空のキャッシュとして扱う（Phase 4で対応済み）

**留意点**:
- キャッシュの `key` は毎回ユニーク（`run_id` を含める）にして、常に最新のファイルで上書き保存されるようにする
- `restore-keys` に共通プレフィックスを指定することで、キャッシュがない場合でも直前の実行のキャッシュから復元できる

---

## シークレットの設定

GitHub リポジトリの「Settings → Secrets and variables → Actions」から設定する。

| シークレット名 | 説明 |
|---|---|
| `GEMINI_API_KEY` | Gemini APIキー（またはOpenAI等に応じて変更） |
| `DISCORD_WEBHOOK_DEV_AI` | `#ai-dev-news` のWebhook URL |
| `DISCORD_WEBHOOK_AI_NEWS` | `#ai-industry` のWebhook URL |
| `DISCORD_WEBHOOK_OTHER` | `#tech-other` のWebhook URL |
| `DISCORD_WEBHOOK_BOT_LOG` | `#bot-log` のWebhook URL |

**留意点**:
- シークレットはワークフロー内で環境変数としてBotに渡す
- ログにシークレットの値が出力されないよう注意（GitHub Actionsはシークレット値を自動マスクするが、意図して出力するコードを書かない）

---

## 失敗時の対応

- Bot実行が失敗した場合（exit 1）、**`#bot-log` に失敗通知を送る**ステップを実行する
  - `if: failure()` 条件で、Bot 実行ステップが失敗したときだけ実行される
  - `DISCORD_WEBHOOK_BOT_LOG` を使って通知する
  - GitHub Actions のデフォルトのメール通知は Settings → Notifications → Actions で OFF にしておく
- キャッシュ保存は `if: always()` を指定して、Bot実行が失敗しても保存が走るようにする
  - これにより途中まで処理した記事がキャッシュに残り、次回の再処理を防げる

---

## テスト実行

### 手順

1. GitHub にリポジトリを作成してコードをプッシュする
2. GitHub の「Settings → Secrets」に4つのシークレットを設定する
3. GitHub Actionsのページから手動実行（`workflow_dispatch`）で動作確認する
4. 翌朝07:00にスケジュール実行されることを確認する

### 確認ポイント

- Actions のログで各ステップが正常に完了しているか
- Discord の各チャンネルに記事が投稿されているか
- キャッシュが保存・復元されているか（Actions の「Caches」タブで確認できる）
- 翌日の実行で前日の記事が重複投稿されていないか

---

## チェックリスト

- [ ] `.github/workflows/rss_bot.yml` が作成されている
- [ ] GitHubリポジトリにシークレット5つが設定されている
- [ ] 手動実行で全ステップが成功する
- [ ] Discordに記事が投稿される
- [ ] キャッシュが保存・復元されている
- [ ] 翌日のスケジュール実行で重複投稿が起きない

---

## RSS機能 完了

Phase 6まで完了すれば、RSS機能の実装は完成。

**次のフェーズ**: X（Twitter）機能の追加 → `docs/x/` 以下のドキュメントを参照
