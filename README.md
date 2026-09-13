# Discord Weather / Utility Bot

各種APIから取得した気象情報等をDiscordへ通知するBotシステムです。自宅Linuxサーバーで運用しています。

## 技術スタック
- **Language**: Python 3 (discord.py)
- **Infrastructure**: Docker, Ubuntu 24.04 LTS (Home Server)

## 工夫した点
- 継続稼働のため、機能群をDockerコンテナ化し自宅サーバーにデプロイ・分離。
- 秘密鍵（.env等）の分離と、コンテナのポータビリティを意識した設計を行っています。

## 設定

`.env` に `DISCORD_TOKEN` を設定し、`config.example.json` を `config.json` へコピーして各値を設定します。両ファイルの実値はGitへ追加しません。過去に使用した資格情報は提供元でローテーションしてください。

## コマンド

- `/tenki`: 現在と10分後の雨予報を表示
- `/pause duration`: 通知を一時停止。`30m`（30分）、`2h`（2時間）、`1d`（1日）の形式で最長7日。数字だけなら分
- `/resume`: 通知をすぐ再開
- `/status`: 停止状態と通知時間帯を表示
- `/set_time start end`: 通知時間帯を設定。開始と終了を同じにすると24時間通知
- `/test`: 本番チャンネルへ投稿せず、自分だけにテスト表示

一時停止の期限と通知時間帯は `config.json` に保存されるため、Botを再起動しても維持されます。時刻の判定には `timezone`（初期値 `Asia/Tokyo`）を使用します。
