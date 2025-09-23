from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from firebase_config import db
from google.cloud import firestore as gcf
from config import ADMIN_ROLE_ID

EVENT_KEY = "イベント"

class RemoveEvent(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @staticmethod
    def _has_manager_role(member: discord.Member) -> bool:
        return any(role.id == ADMIN_ROLE_ID for role in member.roles)

    @app_commands.command(name="remove_event", description="対象ユーザーのイベント値を -1（0未満禁止）します")
    @app_commands.describe(user="ポイントを減算する対象ユーザー")
    async def remove_event(self, interaction: discord.Interaction, user: discord.Member):

        if not isinstance(interaction.user, discord.Member) or not self._has_manager_role(interaction.user):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        ref = db.collection("users").document(str(user.id))

        # 0未満にしないためトランザクションで現在値を見てから保存
        @gcf.transactional
        def _tx(tx, docref):
            snap = docref.get(transaction=tx)
            cur = 0
            if snap.exists:
                data = snap.to_dict() or {}
                cur = int((data.get("points") or {}).get(EVENT_KEY, 0))
            new_val = max(0, cur - 1)
            tx.set(docref, {"points": {EVENT_KEY: new_val}}, merge=True)

        _tx(db.transaction(), ref)

        await interaction.response.send_message(
            f"{user.mention} の `{EVENT_KEY}` 値を **-1** しました。"
        )

async def setup(bot: discord.Client):
    await bot.add_cog(RemoveEvent(bot))
