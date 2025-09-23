from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from firebase_config import db

EVENT_KEY = "イベント"

class ViewEvent(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="view_event", description="対象ユーザーのイベント値を表示します")
    @app_commands.describe(user="ポイントを確認する対象ユーザー（省略時は自分）")
    async def view_event(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        if not isinstance(target, discord.Member):
            return await interaction.response.send_message("ユーザーを解決できませんでした。", ephemeral=True)

        # Firestoreから現在値を取得（存在しなければ0）
        ref = db.collection("users").document(str(target.id))
        snap = ref.get()
        cur = 0
        if snap.exists:
            data = snap.to_dict() or {}
            cur = int((data.get("points") or {}).get(EVENT_KEY, 0))

        if user:
            msg = f"{target.mention} の `{EVENT_KEY}` 値は **{cur}** です。"
        else:
            msg = f"あなたの `{EVENT_KEY}` 値は **{cur}** です。"
        await interaction.response.send_message(msg)

async def setup(bot: discord.Client):
    await bot.add_cog(ViewEvent(bot))
