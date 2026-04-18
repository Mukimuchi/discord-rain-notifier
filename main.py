import discord
from discord import app_commands
from discord.ext import tasks
import requests
import json
import datetime
import os
import io

from typing import Optional

# 設定の読み込みと保存機能
CONFIG_FILE = 'config.json'
with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# デフォルト設定がなければ追加
if 'notify_start_hour' not in config:
    config['notify_start_hour'] = 8
if 'notify_end_hour' not in config:
    config['notify_end_hour'] = 22

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_intensity_message(rainfall: float) -> str:
    """降水量(mm/h)に応じた警告メッセージを返す"""
    if rainfall >= 30:
        return "🚨 **【警戒】ゲリラ豪雨レベルの猛烈な雨が降ります！安全を確保してください！**"
    elif rainfall >= 20:
        return "⚠️ **【注意】土砂降りの雨になります！傘が必須です。**"
    elif rainfall >= 10:
        return "☔ **やや強い本降りの雨になりそうです。**"
    elif rainfall >= 1:
        return "🌧️ **本降りの雨になりそうです。**"
    else:
        return "🌂 **パラパラと小雨が降り始めそうです。**"

class RainBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # スラッシュコマンド用のツリーを作成
        self.tree = app_commands.CommandTree(self)
        self.already_notified = False
        self.pause_until: Optional[datetime.datetime] = None

    async def setup_hook(self):
        # 起動時に自動監視を開始
        self.check_weather.start()
        # スラッシュコマンドをDiscordに登録
        await self.tree.sync()

    def get_weather_info(self):
        """Yahoo APIから天気を取得する共通関数"""
        url = f"https://map.yahooapis.jp/weather/V1/place?coordinates={config['longitude']},{config['latitude']}&appid={config['yahoo_client_id']}&output=json"
        response = requests.get(url).json()
        weather_list = response['Feature'][0]['Property']['WeatherList']['Weather']
        return weather_list[0]['Rainfall'], weather_list[1]['Rainfall']

    def create_weather_embed(self, title, description, current, ten_min):
        """雨雲レーダー付きのリッチな通知パネル(Embed)を作成"""
        embed = discord.Embed(title=title, description=description, color=0x3498db)
        embed.add_field(name="現在の雨量", value=f"{current} mm/h", inline=True)
        embed.add_field(name="10分後の予報", value=f"{ten_min} mm/h", inline=True)
        
        radar_link = "https://weather.yahoo.co.jp/weather/zoomradar/"
        embed.add_field(name="🌐 雨雲レーダーを確認", value=f"[Yahoo天気・雨雲レーダーを開く]({radar_link})", inline=False)
        return embed

    def create_weather_embed(self, title, description, current, ten_min):
        """雨雲レーダーのリンク付きのリッチな通知パネル(Embed)を作成"""
        embed = discord.Embed(title=title, description=description, color=0x3498db)
        embed.add_field(name="現在の雨量", value=f"{current} mm/h", inline=True)
        embed.add_field(name="10分後の予報", value=f"{ten_min} mm/h", inline=True)
        
        radar_link = "https://weather.yahoo.co.jp/weather/zoomradar/"
        embed.add_field(name="🌐 雨雲レーダーを確認", value=f"[Yahoo天気・雨雲レーダーを開く]({radar_link})", inline=False)
        return embed

    @tasks.loop(minutes=5)
    async def check_weather(self):
        """5分ごとの自動チェック"""
        try:
            # 一時停止中の場合はスキップ
            pause_time = self.pause_until
            if pause_time is not None and datetime.datetime.now() < pause_time:
                return

            # 時間帯制限のチェック
            current_hour = datetime.datetime.now().hour
            start_h = config.get('notify_start_hour', 0)
            end_h = config.get('notify_end_hour', 24)
            
            # 時間外なら通知しない (0時回りの設定も考慮)
            in_time_range = False
            if start_h <= end_h:
                in_time_range = (start_h <= current_hour < end_h)
            else:
                in_time_range = (current_hour >= start_h or current_hour < end_h)
                
            if not in_time_range:
                return

            current, ten_min = self.get_weather_info()
            channel = self.get_channel(config['channel_id'])
            if not channel: return

            if current == 0 and ten_min > 0:
                if not self.already_notified:
                    msg = get_intensity_message(ten_min)
                    embed = self.create_weather_embed(
                        title="🚨 雨通知 🚨", 
                        description=f"約10分後に雨が降り始める予報です！\n{msg}",
                        current=current, 
                        ten_min=ten_min
                    )
                    await channel.send(embed=embed)
                    self.already_notified = True
            elif current == 0:
                self.already_notified = False
        except Exception as e:
            print(f"Error in loop: {e}")

# ここから追加：聞かれたときに答える機能
bot = RainBot(intents=discord.Intents.default())

@bot.tree.command(name="tenki", description="現在の雨の状況とレーダー画像を確認します")
async def tenki(interaction: discord.Interaction):
    current, ten_min = bot.get_weather_info()
    
    desc = ""
    if ten_min > 0:
        desc = "☔ もうすぐ降りそうです！急いで！"
    elif current > 0:
        desc = "🌧️ 今は降っています。"
    else:
        desc = "☁️ あと10分は大丈夫そうです。"
        
    embed = bot.create_weather_embed("現在の天気予報", desc, current, ten_min)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pause", description="雨の通知を一時的に停止します（例: 2 を指定で2時間停止）")
@app_commands.describe(hours="停止する時間（時間）")
async def pause_notifications(interaction: discord.Interaction, hours: int):
    target_time = datetime.datetime.now() + datetime.timedelta(hours=hours)
    bot.pause_until = target_time
    await interaction.response.send_message(f"⏸️ 今から {hours} 時間（{target_time.strftime('%H:%M')} まで）、雨の通知を一時停止します。")

@bot.tree.command(name="resume", description="雨の通知を再開します")
async def resume_notifications(interaction: discord.Interaction):
    bot.pause_until = None
    await interaction.response.send_message("▶️ 雨の通知を再開しました！")

@bot.tree.command(name="set_time", description="自動通知を行う時間帯を設定します（例: 開始 8 終了 22）")
@app_commands.describe(start="通知開始時間 (0-23)", end="通知終了時間 (0-23)")
async def set_time(interaction: discord.Interaction, start: int, end: int):
    if not (0 <= start <= 23) or not (0 <= end <= 23):
        await interaction.response.send_message("❌ 時間は0から23の間で指定してください。")
        return
    
    config['notify_start_hour'] = start
    config['notify_end_hour'] = end
    save_config()
    await interaction.response.send_message(f"⏰ 通知時間帯を `{start}:00` から `{end}:00` の間に変更し、設定を保存しました。")

@bot.tree.command(name="test", description="雨の通知がどのように表示されるかテストプレビューを送信します")
async def test_notification(interaction: discord.Interaction):
    # ダミーデータ（やや強い雨）でパネルを作成して送信
    dummy_current = 0.0
    dummy_ten_min = 15.0
    msg = get_intensity_message(dummy_ten_min)
    
    embed = bot.create_weather_embed(
        title="🚨 【テスト】雨通知プレビュー 🚨",
        description=f"約10分後に雨が降り始める予報です！\n{msg}",
        current=dummy_current,
        ten_min=dummy_ten_min
    )
    
    await interaction.response.send_message("✅ テスト通知をチャンネルに送信しました！", ephemeral=True)
    await interaction.channel.send(embed=embed)

token = os.getenv('DISCORD_TOKEN')
if not token:
    print("Error: DISCORD_TOKEN is not set in environment variables.")
    exit(1)

bot.run(token)