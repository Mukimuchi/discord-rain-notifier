import asyncio
import datetime
import json
import os
from pathlib import Path
from typing import Optional

import discord
import requests
from discord import app_commands
from discord.ext import tasks

from rain_logic import get_timezone, is_in_notification_window, parse_pause_duration, parse_stored_datetime


CONFIG_FILE = Path("config.json")
with CONFIG_FILE.open("r", encoding="utf-8") as file:
    config = json.load(file)
config.setdefault("notify_start_hour", 8)
config.setdefault("notify_end_hour", 22)
config.setdefault("timezone", "Asia/Tokyo")
LOCAL_TIMEZONE = get_timezone(config["timezone"])


def save_config() -> None:
    temporary_file = CONFIG_FILE.with_suffix(".json.tmp")
    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)
        file.write("\n")
    os.chmod(temporary_file, 0o600)
    os.replace(temporary_file, CONFIG_FILE)


def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def get_intensity_message(rainfall: float) -> str:
    if rainfall >= 30:
        return "🚨 **【警戒】猛烈な雨が降る予報です。安全を確保してください！**"
    if rainfall >= 20:
        return "⚠️ **【注意】土砂降りになる予報です。傘が必須です。**"
    if rainfall >= 10:
        return "☔ **やや強い本降りの雨になりそうです。**"
    if rainfall >= 1:
        return "🌧️ **本降りの雨になりそうです。**"
    return "🌂 **弱い雨が降り始めそうです。**"


class RainBot(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tree = app_commands.CommandTree(self)
        self.already_notified = False
        self.pause_until: Optional[datetime.datetime] = parse_stored_datetime(config.get("pause_until"))

    async def setup_hook(self) -> None:
        self.check_weather.start()
        await self.tree.sync()

    def _get_weather_info_sync(self) -> tuple[float, float]:
        response = requests.get(
            "https://map.yahooapis.jp/weather/V1/place",
            params={
                "coordinates": f"{config['longitude']},{config['latitude']}",
                "appid": config["yahoo_client_id"],
                "output": "json",
            },
            timeout=10,
        )
        response.raise_for_status()
        weather = response.json()["Feature"][0]["Property"]["WeatherList"]["Weather"]
        return float(weather[0]["Rainfall"]), float(weather[1]["Rainfall"])

    async def get_weather_info(self) -> tuple[float, float]:
        return await asyncio.to_thread(self._get_weather_info_sync)

    def create_weather_embed(self, title: str, description: str, current: float, ten_min: float) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=0x3498DB)
        embed.add_field(name="現在の雨量", value=f"{current:g} mm/h", inline=True)
        embed.add_field(name="10分後の予報", value=f"{ten_min:g} mm/h", inline=True)
        embed.add_field(
            name="🌐 雨雲レーダーを確認",
            value="[Yahoo天気・雨雲レーダーを開く](https://weather.yahoo.co.jp/weather/zoomradar/)",
            inline=False,
        )
        return embed

    def set_pause_until(self, value: Optional[datetime.datetime]) -> None:
        self.pause_until = value
        if value is None:
            config.pop("pause_until", None)
        else:
            config["pause_until"] = value.astimezone(datetime.timezone.utc).isoformat()
        save_config()

    def active_pause_until(self) -> Optional[datetime.datetime]:
        if self.pause_until is not None and utc_now() >= self.pause_until:
            self.set_pause_until(None)
        return self.pause_until

    @tasks.loop(minutes=5)
    async def check_weather(self) -> None:
        try:
            if self.active_pause_until() is not None:
                return
            local_now = utc_now().astimezone(LOCAL_TIMEZONE)
            if not is_in_notification_window(local_now, config["notify_start_hour"], config["notify_end_hour"]):
                return
            current, ten_min = await self.get_weather_info()
            channel = self.get_channel(config["channel_id"])
            if channel is None:
                print("Configured notification channel was not found.")
                return
            if current == 0 and ten_min > 0 and not self.already_notified:
                embed = self.create_weather_embed(
                    "🚨 雨通知 🚨",
                    f"約10分後に雨が降り始める予報です！\n{get_intensity_message(ten_min)}",
                    current,
                    ten_min,
                )
                await channel.send(embed=embed)
                self.already_notified = True
            elif current == 0 and ten_min == 0:
                self.already_notified = False
        except Exception as exc:
            print(f"Weather check failed: {type(exc).__name__}: {exc}")


bot = RainBot(intents=discord.Intents.default())


@bot.tree.command(name="tenki", description="現在と10分後の雨の状況を確認します")
async def tenki(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        current, ten_min = await bot.get_weather_info()
    except Exception:
        await interaction.followup.send("❌ 天気情報を取得できませんでした。少し待ってから再度お試しください。", ephemeral=True)
        return
    if ten_min > 0:
        description = "☔ もうすぐ降りそうです！"
    elif current > 0:
        description = "🌧️ 今は雨が降っています。"
    else:
        description = "☁️ あと10分は雨の予報がありません。"
    await interaction.followup.send(embed=bot.create_weather_embed("現在の天気予報", description, current, ten_min))


@bot.tree.command(name="pause", description="雨通知を一時停止します（30m、2h、1d。数字だけなら分）")
@app_commands.describe(duration="停止時間（例: 30m、2h、1d。最長7日）")
async def pause_notifications(interaction: discord.Interaction, duration: str) -> None:
    try:
        pause_duration = parse_pause_duration(duration)
    except ValueError as exc:
        await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
        return
    target_time = utc_now() + pause_duration
    bot.set_pause_until(target_time)
    local_target = target_time.astimezone(LOCAL_TIMEZONE)
    await interaction.response.send_message(f"⏸️ 雨通知を {local_target.strftime('%m/%d %H:%M')} まで一時停止します。")


@bot.tree.command(name="resume", description="雨通知をすぐ再開します")
async def resume_notifications(interaction: discord.Interaction) -> None:
    bot.set_pause_until(None)
    await interaction.response.send_message("▶️ 雨通知を再開しました。")


@bot.tree.command(name="status", description="雨通知の停止状態と通知時間帯を確認します")
async def notification_status(interaction: discord.Interaction) -> None:
    pause_until = bot.active_pause_until()
    pause_text = "稼働中" if pause_until is None else f"一時停止中（{pause_until.astimezone(LOCAL_TIMEZONE).strftime('%m/%d %H:%M')} まで）"
    start = config["notify_start_hour"]
    end = config["notify_end_hour"]
    window = "24時間" if start == end else f"{start}:00〜{end}:00"
    await interaction.response.send_message(
        f"☔ 状態: **{pause_text}**\n⏰ 通知時間帯: **{window}**（{config['timezone']}）",
        ephemeral=True,
    )


@bot.tree.command(name="set_time", description="自動通知を行う時間帯を設定します")
@app_commands.describe(start="通知開始時刻 (0〜23)", end="通知終了時刻 (0〜23、開始と同じなら24時間)")
async def set_time(interaction: discord.Interaction, start: int, end: int) -> None:
    if not 0 <= start <= 23 or not 0 <= end <= 23:
        await interaction.response.send_message("❌ 時刻は0から23の間で指定してください。", ephemeral=True)
        return
    config["notify_start_hour"] = start
    config["notify_end_hour"] = end
    save_config()
    window = "24時間" if start == end else f"{start}:00〜{end}:00"
    await interaction.response.send_message(f"⏰ 通知時間帯を **{window}** に変更しました。")


@bot.tree.command(name="test", description="雨通知のテストプレビューを表示します")
async def test_notification(interaction: discord.Interaction) -> None:
    ten_min = 15.0
    embed = bot.create_weather_embed(
        "🚨 【テスト】雨通知プレビュー 🚨",
        f"約10分後に雨が降り始める予報です！\n{get_intensity_message(ten_min)}",
        0.0,
        ten_min,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in environment variables.")
    bot.run(token)


if __name__ == "__main__":
    main()
