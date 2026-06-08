import discord
from discord import app_commands
from discord.ext import commands
from firebase_config import db

WAKUSEI_KEY = "わくせい"

class ViewWakusei(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="view_wakusei", description="自分のわくせいポイントを確認します")
    async def view_wakusei(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        ref = db.collection("users").document(user_id)
        snap = ref.get()
        cur = 0
        if snap.exists:
            cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0))

        await interaction.response.send_message(
            f"あなたのわくせいポイントは **{cur}** pt です。",
            ephemeral=True
        )

async def setup(bot: discord.Client):
    await bot.add_cog(ViewWakusei(bot))
