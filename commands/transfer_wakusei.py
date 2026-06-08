import discord
from discord import app_commands
from discord.ext import commands
from google.cloud import firestore as gcf
from firebase_config import db

WAKUSEI_KEY = "わくせい"

class TransferWakusei(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="transfer_wakusei", description="わくせいポイントを相手に譲渡します")
    @app_commands.describe(user="譲渡先のユーザー", amount="譲渡するポイント数（1以上）")
    async def transfer_wakusei(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        sender = interaction.user

        if user.id == sender.id:
            return await interaction.response.send_message("自分自身には譲渡できません。", ephemeral=True)

        if user.bot:
            return await interaction.response.send_message("Botには譲渡できません。", ephemeral=True)

        if amount <= 0:
            return await interaction.response.send_message("譲渡するポイントは1以上で指定してください。", ephemeral=True)

        sender_ref = db.collection("users").document(str(sender.id))
        receiver_ref = db.collection("users").document(str(user.id))

        result = {"ok": False, "sender_new": 0, "receiver_new": 0}

        @gcf.transactional
        def _tx(tx, s_ref, r_ref):
            s_snap = s_ref.get(transaction=tx)
            sender_cur = 0
            if s_snap.exists:
                sender_cur = int((s_snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0))

            if sender_cur < amount:
                result["ok"] = False
                return

            r_snap = r_ref.get(transaction=tx)
            receiver_cur = 0
            if r_snap.exists:
                receiver_cur = int((r_snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0))

            sender_new = sender_cur - amount
            receiver_new = receiver_cur + amount

            tx.set(s_ref, {"points": {WAKUSEI_KEY: sender_new}}, merge=True)
            tx.set(r_ref, {"points": {WAKUSEI_KEY: receiver_new}}, merge=True)

            result["ok"] = True
            result["sender_new"] = sender_new
            result["receiver_new"] = receiver_new

        _tx(db.transaction(), sender_ref, receiver_ref)

        if not result["ok"]:
            return await interaction.response.send_message("ポイントが不足しています。", ephemeral=True)

        await interaction.response.send_message(
            f"{sender.mention} → {user.mention} に **{amount}** pt を譲渡しました\n"
            f"{sender.mention} の残高：**{result['sender_new']}** pt\n"
            f"{user.mention} の残高：**{result['receiver_new']}** pt"
        )

async def setup(bot: discord.Client):
    await bot.add_cog(TransferWakusei(bot))
