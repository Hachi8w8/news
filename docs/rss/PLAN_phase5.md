# Phase 5: Discord通知

## 目標

Phase 3で生成した分類・要約をもとに、カテゴリに応じたDiscordチャンネルへ通知する。

**完了条件**:
- 各記事が正しいチャンネルに投稿される
- Embed形式（タイトル・要約・出典・色付き）で表示される
- 1メッセージ1記事で送信される
- レート制限エラー時にリトライして処理が継続できる

---

## 追加するファイル

```
src/
└── notifier.py   ← 新規追加
```

`main.py` も更新して、通知処理を組み込む。

---

## 環境変数の追加

`.env` に以下を追加する（`.env.example` も更新する）:

```
DISCORD_WEBHOOK_DEV_AI=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_AI_NEWS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_OTHER=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_BOT_LOG=https://discord.com/api/webhooks/...
```

**Webhook URLの取得方法**: Discordのチャンネル設定 → 「連携サービス」→「ウェブフック」から作成できる。

---

## チャンネル構成

| カテゴリ | チャンネル | 色 |
|---|---|---|
| `dev_ai` | `#ai-dev-news` | 緑 `#00FF00` |
| `industry` | `#ai-industry` | 青 `#0088FF` |
| `not_ai` | `#tech-other` | グレー `#808080` |

---

## 各ファイルの役割と留意点

### `src/notifier.py`

**役割**: 記事データをDiscord Embed形式に変換し、Webhook経由で送信するモジュール。

---

#### Embed の構成

1件の記事につき1つのEmbedを作成する。

**共通フィールド**:
- タイトル（記事タイトル、最大200文字で切り詰め）
- URL（タイトルをクリックで記事に遷移）
- 本文（要約、最大400文字で切り詰め）
- 出典フィールド（Zenn or Qiita）
- 色（カテゴリに応じて変える）

**留意点**:
- タイトルや要約が制限文字数を超える場合は末尾を切り詰めて `...` を付ける
- 1メッセージにつき `embeds` 配列に1件のEmbedを入れて送信する（バッチ分割不要）

---

#### レート制限・エラー対応

**Discord のレート制限**:
- 各メッセージ送信後に1秒スリープする
- 429エラーが返ってきた場合、レスポンスの `Retry-After` ヘッダーの値（秒）だけ待ってからリトライする
- リトライは最大3回。3回失敗したらその記事をスキップしてログに記録する

**その他のエラー**:
- 5xx系エラーはリトライ対象とする
- Webhook URLが未設定（環境変数がない）の場合はそのチャンネルの送信をスキップしてログに警告を出す

---

### `src/main.py`（更新）

**最終的な処理フロー**:

```
1. RSS収集
2. キャッシュ読み込み → 未処理記事のみ抽出
3. 本文取得（trafilatura）
4. AI分類 + 要約（LiteLLM）
5. Discord通知（カテゴリ別チャンネルへ）  ← 今回追加
6. 実行結果サマリーを #bot-log に送信     ← 今回追加
7. キャッシュ保存
```

**留意点**:
- 通知対象が0件の場合（全記事スキップ）は通知処理をスキップして正常終了する
- 各チャンネルへの送信件数をログに出力する

---

## 依存パッケージの追加

```bash
uv add requests
```

---

## テスト実行

### 手順

1. Discordでテスト用チャンネルとWebhookを作成する
2. `.env` に3つのWebhook URLを設定する
3. `uv add requests` でパッケージを追加
4. `uv run python src/main.py` を実行する

### 期待される結果

- `#ai-dev-news` に `dev_ai` 記事がEmbed形式で投稿される
- `#ai-industry` に `industry` 記事が投稿される
- `#tech-other` に `not_ai` 記事が投稿される
- 各チャンネルの投稿件数がログに表示される

### テスト時の注意

- キャッシュが残っていると記事が0件になる。テスト前に `.cache/processed_urls.json` を削除するか、`config.py` の取得期間を増やして記事を取得し直す
- Gemini APIを何度も呼ぶとレート制限に引っかかることがある。Phase 3のテスト結果データを使って通知だけ単体でテストする方法も検討する

---

## チェックリスト

- [ ] `requests` が `pyproject.toml` に追加されている
- [ ] `.env` に3つのWebhook URLが設定されている
- [ ] `src/notifier.py` が作成されている
- [ ] 各カテゴリの記事が対応するチャンネルに投稿される
- [ ] Embed にタイトル・要約・出典・色が表示される
- [ ] 1メッセージ1記事で送信される
- [ ] 実行結果サマリーが `#bot-log` に送信される
- [ ] 失敗があればサマリーに対象URLと理由が含まれる
- [ ] Webhook URLが未設定でも処理が止まらない

---

## 次のステップ

Phase 5が完了したら、Phase 6（GitHub Actions自動化）に進む。

→ `PLAN_phase6.md`
