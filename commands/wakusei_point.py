import discord
from discord import app_commands
from discord.ext import commands
from google.cloud import firestore as gcf
from firebase_config import db
from config import ADMIN_ROLE_ID

WAKUSEI_KEY = "わくせい"

class WakuseiPoint(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @staticmethod
    def _has_manager_role(member: discord.Member) -> bool:
        return any(role.id == ADMIN_ROLE_ID for role in member.roles)

    @app_commands.command(name="add_wakusei", description="対象ユーザーのわくせいポイントを増減します（管理者専用）")
    @app_commands.describe(user="対象ユーザー", amount="付与するポイント数（マイナスで減算）")
    async def wakusei_point(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if not isinstance(interaction.user, discord.Member) or not self._has_manager_role(interaction.user):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        if amount == 0:
            return await interaction.response.send_message("0 は指定できません", ephemeral=True)

        ref = db.collection("users").document(str(user.id))

        @gcf.transactional
        def _tx(tx, docref):
            snap = docref.get(transaction=tx)
            cur = 0
            if snap.exists:
                cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0))
            new_val = max(0, cur + amount)
            tx.set(docref, {"points": {WAKUSEI_KEY: new_val}}, merge=True)
            return new_val

        new_val = _tx(db.transaction(), ref)

        sign = f"+{amount}" if amount > 0 else str(amount)
        await interaction.response.send_message(
            f"{user.mention} のわくせいポイントを **{sign}** しました（現在 **{new_val}** pt）"
        )

async def setup(bot: discord.Client):
    await bot.add_cog(WakuseiPoint(bot))
