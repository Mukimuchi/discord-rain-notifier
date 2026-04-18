# Discord Weather / Utility Bot

各種APIから取得した気象情報等をDiscordへ通知するBotシステムです。自宅Linuxサーバーで運用しています。

## 技術スタック
- **Language**: Python 3 (discord.py)
- **Infrastructure**: Docker, Ubuntu 24.04 LTS (Home Server)

## 工夫した点
- 継続稼働のため、機能群をDockerコンテナ化し自宅サーバーにデプロイ・分離。
- 秘密鍵（.env等）の分離と、コンテナのポータビリティを意識した設計を行っています。
