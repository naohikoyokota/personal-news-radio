# Personal News Radio

RSSフィードからニュースを自動収集し、Claude APIで要約してLINEに配信するシステムです。

## 機能 (MVP)

- 日本語ニュースRSSフィードから記事を収集（5ソース）
- SQLiteで記事を管理（重複除去・配信済みフラグ）
- Claude APIでサマリ＋詳細の2パート形式に要約
- LINEにテキストで自動配信
- `--dry-run` オプションで配信なしの動作確認
- エラー時はLINEに通知
- 実行ログをファイル保存

## 環境構築

### 1. Python 3.11以上をインストール

```bash
python3 --version  # 3.11以上であることを確認
```

### 2. 仮想環境の作成と有効化

```bash
cd ~/personal-news-radio
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env.example` をコピーして `.env` を作成し、各APIキーを設定します。

```bash
cp .env.example .env
```

`.env` を編集：

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # TTS機能用（現在未使用）
LINE_CHANNEL_ACCESS_TOKEN=...
LINE_USER_ID=U...
```

#### APIキーの取得方法

**Anthropic API Key**
- https://console.anthropic.com/ にログイン
- API Keys から新しいキーを生成

**LINE Messaging API**
1. https://developers.line.biz/ でチャンネルを作成
2. Messaging API チャンネルを選択
3. 「Channel access token」を発行（長期トークン）
4. ユーザーIDは LINE アプリ → プロフィール → 「マイQRコード」画面のURLから取得、またはWebhookのuserIdを使用

### 5. 動作確認（ドライラン）

```bash
python main.py --dry-run
```

ドライランでは実際にLINEへの送信は行われず、送信内容がログに表示されます。

### 6. 本番実行

```bash
python main.py
```

## 設定

`config.yaml` で以下を変更できます：

| 設定項目 | 説明 | デフォルト |
|---------|------|---------|
| `feeds` | RSSフィードのリスト | NHK/朝日/毎日/ITmedia/Gigazine |
| `max_articles_per_feed` | フィードごとの最大取得記事数 | 5 |
| `max_delivery_articles` | 要約・配信する最大記事数 | 10 |

## 自動実行の設定

### macOS/Linux（cron）

```bash
crontab -e
```

毎朝7時に実行する例：

```cron
0 7 * * * cd ~/personal-news-radio && /path/to/.venv/bin/python main.py >> logs/cron.log 2>&1
```

## ディレクトリ構成

```
personal-news-radio/
├── main.py              # エントリーポイント
├── config.yaml          # 設定ファイル
├── requirements.txt     # 依存パッケージ
├── .env                 # APIキー（gitignore済み）
├── .env.example         # .envのサンプル
├── src/
│   ├── collector.py     # RSSフィード収集
│   ├── database.py      # SQLite管理
│   ├── summarizer.py    # Claude API要約生成
│   ├── notifier.py      # LINE配信
│   └── logger.py        # ログ設定
├── data/
│   └── news.db          # SQLiteデータベース（自動生成）
└── logs/
    └── news_radio_YYYYMMDD.log  # 実行ログ（自動生成）
```

## LINEメッセージ形式

```
＝＝＝ 本日のニュースサマリー ＝＝＝

【サマリパート】
▶ [記事タイトル1]
　[3〜5行の要約]

▶ [記事タイトル2]
　[3〜5行の要約]

...（3〜5件）

【詳細パート】
📰 [重要記事タイトル]
[読み物風の詳細解説（200〜300字）]
🔗 [元記事URL]
```

## トラブルシューティング

**記事が収集されない**
- フィードURLが有効か確認：`curl -I [URL]`
- ネットワーク接続を確認

**Claude APIエラー**
- `ANTHROPIC_API_KEY` が正しく設定されているか確認
- APIの使用量制限に達していないか確認

**LINE配信エラー**
- `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_USER_ID` を確認
- LINE Messaging API チャンネルが有効か確認
- `--dry-run` でメッセージ内容を事前確認
