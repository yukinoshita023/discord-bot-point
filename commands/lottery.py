import random
from datetime import datetime, time, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from google.cloud import firestore as gcf
from firebase_config import db
from config import ADMIN_ROLE_ID

LOTTERY_CHANNEL_ID = 1571092576059138078
WAKUSEI_KEY = "わくせい"
PRIZE = 30_000
JST = timezone(timedelta(hours=9))
DRAW_WEEKDAY = 5  # 土曜日
DRAW_TIME = time(hour=20, minute=0, tzinfo=JST)
MAX_LISTED_NAMES = 50

_rng = random.SystemRandom()


def _lottery_ref():
    return db.collection("lottery").document("current")


def _panel_ref():
    return db.collection("lottery").document("panel")


def _debt_of(snap) -> int:
    return int((snap.to_dict() or {}).get("debt", {}).get("amount", 0))


def build_embed(entrants: dict) -> discord.Embed:
    ordered = sorted(entrants.values(), key=lambda e: e.get("joined_at", 0))
    names = [e.get("name", "（不明）") for e in ordered[:MAX_LISTED_NAMES]]
    if len(ordered) > MAX_LISTED_NAMES:
        names.append(f"ほか {len(ordered) - MAX_LISTED_NAMES} 人")
    name_list = "\n".join(names) or "（まだいません）"

    return discord.Embed(
        title="🎫 わくせい宝くじ",
        description=(
            f"毎週**土曜日20時**に抽選を行い、当選者1名に **{PRIZE:,} wp** をプレゼント！\n\n"
            f"・参加は無料、ボタンを押すだけ\n"
            f"・1人1週につき1口まで\n"
            f"・借金がある人は参加できません（抽選時に借金がある場合も対象外）\n"
            f"・抽選後は参加者がリセットされるので、毎週参加してください\n\n"
            f"**今週の参加者（{len(ordered)}人）**\n{name_list}"
        ),
        color=discord.Color.gold(),
    )


@gcf.transactional
def _enter(tx, lottery_ref, user_ref, user_id: str, name: str) -> tuple[str, int, dict]:
    user_snap = user_ref.get(transaction=tx)
    entrants = (lottery_ref.get(transaction=tx).to_dict() or {}).get("entrants", {})

    debt = _debt_of(user_snap)
    if debt > 0:
        return "debt", debt, entrants
    if user_id in entrants:
        return "already", debt, entrants

    entry = {"name": name, "joined_at": datetime.now(JST).timestamp()}
    tx.set(lottery_ref, {"entrants": {user_id: entry}}, merge=True)
    return "joined", debt, {**entrants, user_id: entry}


@gcf.transactional
def _draw(tx, lottery_ref, today: str) -> tuple[str | None, int, int] | None:
    data = lottery_ref.get(transaction=tx).to_dict() or {}
    if data.get("last_draw_date") == today:
        return None

    entrants = list(data.get("entrants", {}).keys())
    user_refs = {uid: db.collection("users").document(uid) for uid in entrants}
    snaps = {uid: ref.get(transaction=tx) for uid, ref in user_refs.items()}

    # 参加後に借金した人も抽選対象外にする
    eligible = [uid for uid in entrants if _debt_of(snaps[uid]) == 0]

    winner_id = None
    if eligible:
        winner_id = _rng.choice(eligible)
        points = int((snaps[winner_id].to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0))
        tx.set(user_refs[winner_id], {"points": {WAKUSEI_KEY: points + PRIZE}}, merge=True)

    tx.set(lottery_ref, {"entrants": {}, "last_draw_date": today, "last_winner_id": winner_id})
    return winner_id, len(entrants), len(eligible)


class JoinLotteryButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="宝くじに参加する",
            style=discord.ButtonStyle.primary,
            custom_id="join_lottery",
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        user_id = str(member.id)
        user_ref = db.collection("users").document(user_id)
        status, debt, entrants = _enter(db.transaction(), _lottery_ref(), user_ref, user_id, member.display_name)

        if status == "debt":
            return await interaction.response.send_message(
                f"借金があるため宝くじには参加できません。\n"
                f"残債：**{debt:,} wp**（`/repay` で返済できます）",
                ephemeral=True,
            )

        if status == "already":
            return await interaction.response.send_message("今週の宝くじにはすでに参加しています。", ephemeral=True)

        await interaction.response.edit_message(embed=build_embed(entrants), view=LotteryView())
        await interaction.followup.send("🎫 今週の宝くじに参加しました！ 土曜日20時の発表をお待ちください。", ephemeral=True)


class LotteryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(JoinLotteryButton())


class Lottery(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.weekly_draw.start()

    async def cog_unload(self):
        self.weekly_draw.cancel()

    async def _reset_panel(self, channel: discord.TextChannel):
        panel = _panel_ref().get().to_dict() or {}
        message_id = panel.get("message_id")
        if not message_id:
            return
        try:
            await channel.get_partial_message(int(message_id)).edit(embed=build_embed({}), view=LotteryView())
        except discord.HTTPException as e:
            print(f"[lottery] 参加者パネルのリセットに失敗しました: {e}")

    @tasks.loop(time=DRAW_TIME)
    async def weekly_draw(self):
        now = datetime.now(JST)
        if now.weekday() != DRAW_WEEKDAY:
            return

        try:
            result = _draw(db.transaction(), _lottery_ref(), now.strftime("%Y-%m-%d"))
        except Exception as e:
            print(f"[lottery] 抽選中にエラーが発生しました: {e}")
            return

        if result is None:
            return

        winner_id, total, eligible = result
        if winner_id:
            print(f"[lottery] 当選者 {winner_id} に {PRIZE}WP を付与しました（参加 {total} 人、抽選対象 {eligible} 人）")
            message = (
                f"🎉 **今週の宝くじ当選者は <@{winner_id}> さん！**\n"
                f"**{PRIZE:,} wp** を獲得しました！（参加者 {eligible} 人）\n"
                f"次回の抽選は来週土曜日20時です。"
            )
        else:
            message = "今週の宝くじは抽選対象の参加者がいなかったため、当選者はいませんでした。"

        channel = self.bot.get_channel(LOTTERY_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            print(f"[lottery] チャンネルが見つからないため発表できませんでした: {LOTTERY_CHANNEL_ID}")
            return
        await self._reset_panel(channel)
        await channel.send(message)

    @weekly_draw.before_loop
    async def before_weekly_draw(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="post_wakusei_lottery", description="宝くじの説明と参加ボタンをチャンネルに投稿します（管理者専用）")
    async def post_wakusei_lottery(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        channel = self.bot.get_channel(LOTTERY_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("チャンネルが見つかりませんでした。", ephemeral=True)

        entrants = (_lottery_ref().get().to_dict() or {}).get("entrants", {})
        message = await channel.send(embed=build_embed(entrants), view=LotteryView())
        _panel_ref().set({"message_id": str(message.id)})
        await interaction.response.send_message("宝くじメッセージを投稿しました！", ephemeral=True)


async def setup(bot: commands.Bot):
    bot.add_view(LotteryView())
    await bot.add_cog(Lottery(bot))
