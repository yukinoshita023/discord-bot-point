from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from firebase_config import db
from google.cloud import firestore as gcf
from config import ADMIN_ROLE_ID

EVENT_KEY = "イベント"

class AddEvent(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @staticmethod
    def _has_manager_role(member: discord.Member) -> bool:
        return any(role.id == ADMIN_ROLE_ID for role in member.roles)

    @app_commands.command(name="add_event", description="対象ユーザーのイベント値を +1 します")
    @app_commands.describe(user="ポイントを付与する対象ユーザー")
    async def add_event(self, interaction: discord.Interaction, user: discord.Member):

        if not isinstance(interaction.user, discord.Member) or not self._has_manager_role(interaction.user):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        ref = db.collection("users").document(str(user.id))
        ref.set({"points": {EVENT_KEY: gcf.Increment(1)}}, merge=True)

        await interaction.response.send_message(
            f"{user.mention} の `{EVENT_KEY}` 値を **+1** しました。"
        )

async def setup(bot: discord.Client):
    await bot.add_cog(AddEvent(bot))
