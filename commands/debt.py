import discord
from discord import app_commands
from discord.ext import commands
from google.cloud import firestore as gcf
from firebase_config import db
from config import DEBTOR_ROLE_ID

WAKUSEI_KEY = "わくせい"
DEBT_LIMIT = 3000


def _read_balances(snap) -> tuple[int, int]:
    data = snap.to_dict() or {}
    points = int(data.get("points", {}).get(WAKUSEI_KEY, 0))
    debt = int(data.get("debt", {}).get("amount", 0))
    return points, debt


@gcf.transactional
def _borrow(tx, ref, amount: int) -> tuple[bool, int, int]:
    points, debt = _read_balances(ref.get(transaction=tx))
    if debt + amount > DEBT_LIMIT:
        return False, points, debt
    points += amount
    debt += amount
    tx.set(ref, {"points": {WAKUSEI_KEY: points}, "debt": {"amount": debt}}, merge=True)
    return True, points, debt


@gcf.transactional
def _repay(tx, ref, amount: int) -> tuple[int, int, int]:
    points, debt = _read_balances(ref.get(transaction=tx))
    paid = min(amount, debt)
    if paid == 0 or points < paid:
        return 0, points, debt
    points -= paid
    debt -= paid
    tx.set(ref, {"points": {WAKUSEI_KEY: points}, "debt": {"amount": debt}}, merge=True)
    return paid, points, debt


async def _sync_debtor_role(member: discord.Member, debt: int) -> bool:
    role = member.guild.get_role(DEBTOR_ROLE_ID)
    if role is None:
        print(f"ロールが見つかりませんでした: {DEBTOR_ROLE_ID}")
        return False

    try:
        if debt > 0 and role not in member.roles:
            await member.add_roles(role, reason="わくせいポイントの借入")
        elif debt == 0 and role in member.roles:
            await member.remove_roles(role, reason="わくせいポイントの完済")
    except discord.HTTPException as e:
        print(f"{member.name} の借金ロール更新に失敗しました: {e}")
        return False
    return True


class Debt(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @staticmethod
    async def _reply(interaction: discord.Interaction, member: discord.Member, debt: int, message: str, ephemeral: bool):
        await interaction.response.send_message(message, ephemeral=ephemeral)
        if not await _sync_debtor_role(member, debt):
            await interaction.followup.send("借金ロールの更新に失敗しました。管理者にお問い合わせください。", ephemeral=True)

    @app_commands.command(name="borrow", description=f"わくせいポイントを借ります（残債の上限は {DEBT_LIMIT:,} wp）")
    @app_commands.describe(amount="借りるポイント数")
    async def borrow(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, DEBT_LIMIT]):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        ref = db.collection("users").document(str(member.id))
        ok, points, debt = _borrow(db.transaction(), ref, amount)

        if not ok:
            message = (
                f"借入上限を超えています。\n"
                f"現在の残債：**{debt:,} wp** ／ あと借りられる額：**{DEBT_LIMIT - debt:,} wp**"
            )
            return await self._reply(interaction, member, debt, message, ephemeral=True)

        message = (
            f"💸 {member.mention} さんが **{amount:,} wp** を借りました。\n"
            f"現在の残高：**{points:,} wp** ／ 残債：**{debt:,} wp**"
        )
        await self._reply(interaction, member, debt, message, ephemeral=False)

    @app_commands.command(name="repay", description="借りたわくせいポイントを返済します")
    @app_commands.describe(amount="返済するポイント数（残債より多い場合は残債分だけ返済します）")
    async def repay(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        ref = db.collection("users").document(str(member.id))
        paid, points, debt = _repay(db.transaction(), ref, amount)

        if debt == 0 and paid == 0:
            return await self._reply(interaction, member, debt, "借金はありません。", ephemeral=True)

        if paid == 0:
            message = (
                f"わくせいポイントが足りません。\n"
                f"現在の残高：**{points:,} wp** ／ 残債：**{debt:,} wp**"
            )
            return await self._reply(interaction, member, debt, message, ephemeral=True)

        if debt == 0:
            message = (
                f"🎉 {member.mention} さんが **{paid:,} wp** を返済し、完済しました！\n"
                f"現在の残高：**{points:,} wp**"
            )
        else:
            message = (
                f"💰 {member.mention} さんが **{paid:,} wp** を返済しました。\n"
                f"現在の残高：**{points:,} wp** ／ 残債：**{debt:,} wp**"
            )
        await self._reply(interaction, member, debt, message, ephemeral=False)


async def setup(bot: discord.Client):
    await bot.add_cog(Debt(bot))
