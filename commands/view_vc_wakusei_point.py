import discord
from discord import app_commands
from discord.ext import commands
from firebase_config import db

WAKUSEI_KEY = "わくせい"

class ViewVCWakuseiPoint(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="view_vc_wakusei_point", description="自分がいる通話部屋のメンバーのわくせいポイントを一覧表示します")
    async def view_vc_wakusei_point(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        voice_state = member.voice
        if voice_state is None or voice_state.channel is None:
            return await interaction.response.send_message("通話部屋に入ってから実行してください。", ephemeral=True)

        channel_members = [m for m in voice_state.channel.members if not m.bot]
        if not channel_members:
            return await interaction.response.send_message("通話部屋にメンバーがいません。", ephemeral=True)

        results = []
        for m in channel_members:
            ref = db.collection("users").document(str(m.id))
            snap = ref.get()
            cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0)) if snap.exists else 0
            results.append((m.display_name, cur))

        results.sort(key=lambda x: x[1], reverse=True)
        body = "\n".join(f"{name}：**{pt:,}** pt" for name, pt in results)

        await interaction.response.send_message(
            f"🔊 **{voice_state.channel.name}** のメンバーのわくせいポイント\n{body}"
        )

async def setup(bot: discord.Client):
    await bot.add_cog(ViewVCWakuseiPoint(bot))
