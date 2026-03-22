# emoji-stat

Discordサーバー内の絵文字使用統計を集計し、グラフ（PNG）とCSVで出力するBotです。

スラッシュコマンド `/emoji_stat` を実行すると、全テキストチャンネルのメッセージ履歴を遡り、カスタム絵文字・デフォルト絵文字の使用回数をリアクション含めて集計します。

## セットアップ

### 1. Discord Botの作成

1. [Discord Developer Portal](https://discord.com/developers/applications/) でアプリケーションを作成
2. **Bot** ページで Bot を作成し、トークンをコピー
3. **Privileged Gateway Intents** で **MESSAGE CONTENT INTENT** を有効化
4. **OAuth2 > URL Generator** で以下を選択し、生成されたURLからBotをサーバーに招待
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions:
     - チャンネルを表示
     - メッセージを送る
     - メッセージ履歴を読む

### 2. インストール

Python 3.12 以上と [uv](https://docs.astral.sh/uv/) が必要です。

```bash
git clone https://github.com/your-username/emoji-stat.git
cd emoji-stat
uv sync
```

### 3. 実行

```bash
uv run main.py --token YOUR_BOT_TOKEN
```

## 使い方

1. BotをDiscordサーバーに招待
2. Botを起動
3. サーバー内の任意のテキストチャンネルで `/emoji_stat` を実行
4. スキャン完了後、`output/{サーバー名}_{タイムスタンプ}/` にグラフとCSVが保存されます

## 出力ファイル

### グラフ（PNG）

#### 全絵文字

| # | ファイル名 | 内容 |
|---|-----------|------|
| 01 | `01_total_count.png` | 使用回数 Top 25 |
| 02 | `02_msg_vs_reaction.png` | 本文 vs リアクション Top 25 |
| 03 | `03_message_count.png` | メッセージ本文 Top 25 |
| 04 | `04_reaction_count.png` | リアクション Top 25 |
| 05 | `05_channel_spread.png` | チャンネル使用数 Top 25 |
| 06 | `06_total_count_bottom.png` | 使用回数 Bottom 25 |
| 07 | `07_message_count_bottom.png` | メッセージ本文 Bottom 25 |
| 08 | `08_reaction_count_bottom.png` | リアクション Bottom 25 |
| 09 | `09_channel_spread_bottom.png` | チャンネル使用数 Bottom 25 |
| 10 | `10_channel_heatmap.png` | チャンネル x 絵文字 ヒートマップ |

#### カスタム絵文字のみ

| # | ファイル名 | 内容 |
|---|-----------|------|
| 11 | `11_custom_total_count.png` | 使用回数 Top 25 |
| 12 | `12_custom_msg_vs_reaction.png` | 本文 vs リアクション Top 25 |
| 13 | `13_custom_message_count.png` | メッセージ本文 Top 25 |
| 14 | `14_custom_reaction_count.png` | リアクション Top 25 |
| 15 | `15_custom_channel_spread.png` | チャンネル使用数 Top 25 |
| 16 | `16_custom_total_count_bottom.png` | 使用回数 Bottom 25 |
| 17 | `17_custom_message_count_bottom.png` | メッセージ本文 Bottom 25 |
| 18 | `18_custom_reaction_count_bottom.png` | リアクション Bottom 25 |
| 19 | `19_custom_channel_spread_bottom.png` | チャンネル使用数 Bottom 25 |
| 20 | `20_custom_channel_heatmap.png` | チャンネル x 絵文字 ヒートマップ |

### CSV

| ファイル名 | 内容 |
|-----------|------|
| `emoji_summary.csv` | 絵文字ごとの集計（使用回数、チャンネル数など） |
| `emoji_per_channel.csv` | チャンネル x 絵文字の使用回数マトリクス |

### その他

| ファイル名 | 内容 |
|-----------|------|
| `scan_info.txt` | スキャン情報（サーバー名、日時、チャンネル数、メッセージ数など） |

## 技術スタック

- [py-cord](https://github.com/Pycord-Development/pycord) — Discord Bot フレームワーク
- [Plotly](https://plotly.com/python/) + [Kaleido](https://github.com/plotly/Kaleido) — グラフ生成・PNG出力
