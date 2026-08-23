import discord
from discord import app_commands
from discord.ext import commands
from google.cloud import firestore as gcf
from firebase_config import db

WAKUSEI_KEY = "わくせい"


@gcf.transactional
def _try_deduct(tx, ref, amount: int) -> bool:
    snap = ref.get(transaction=tx)
    cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0)) if snap.exists else 0
    if cur < amount:
        return False
    tx.set(ref, {"points": {WAKUSEI_KEY: cur - amount}}, merge=True)
    return True


@gcf.transactional
def _add_points(tx, ref, amount: int) -> int:
    snap = ref.get(transaction=tx)
    cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0)) if snap.exists else 0
    new_val = cur + amount
    tx.set(ref, {"points": {WAKUSEI_KEY: new_val}}, merge=True)
    return new_val


class GambleView(discord.ui.View):
    def __init__(self, host: discord.Member, amount: int, voice_channel_id: int):
        super().__init__(timeout=1800)  # 30分
        self.host = host
        self.amount = amount
        self.voice_channel_id = voice_channel_id
        self.participants: dict[int, discord.Member] = {}
        self.confirmed = False
        self.pot = 0
        self.message: discord.Message | None = None

        self.join_button = JoinButton()
        self.confirm_button = ConfirmButton()
        self.add_item(self.join_button)
        self.add_item(self.confirm_button)

    def build_embed(self) -> discord.Embed:
        names = "\n".join(m.display_name for m in self.participants.values()) or "（まだいません）"
        return discord.Embed(
            title="🎲 賭博会",
            description=(
                f"主催者：{self.host.display_name}\n"
                f"掛け金：**{self.amount:,}** wp / 人\n\n"
                f"**参加者（{len(self.participants)}人）**\n{names}"
            ),
            color=discord.Color.gold(),
        )

    async def on_timeout(self):
        if self.confirmed:
            return
        self.join_button.disabled = True
        self.confirm_button.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⏰ タイムアウトしたため終了しました。", view=self)
            except discord.HTTPException:
                pass


class JoinButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="参加する", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        view: GambleView = self.view
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        if view.confirmed:
            return await interaction.response.send_message("すでに確定済みです。", ephemeral=True)

        voice_state = member.voice
        if voice_state is None or voice_state.channel is None or voice_state.channel.id != view.voice_channel_id:
            return await interaction.response.send_message("主催者と同じ通話部屋にいる人だけ参加できます。", ephemeral=True)

        if member.id in view.participants:
            view.participants.pop(member.id)
        else:
            view.participants[member.id] = member

        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="確定する", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: GambleView = self.view

        if interaction.user.id != view.host.id:
            return await interaction.response.send_message("主催者だけが確定できます。", ephemeral=True)

        if view.confirmed:
            return await interaction.response.send_message("すでに確定済みです。", ephemeral=True)

        if len(view.participants) < 2:
            return await interaction.response.send_message("参加者が2人以上集まってから確定してください。", ephemeral=True)

        view.confirmed = True

        insufficient = []
        for user_id, member in list(view.participants.items()):
            ref = db.collection("users").document(str(user_id))
            ok = _try_deduct(db.transaction(), ref, view.amount)
            if not ok:
                insufficient.append(member)
                view.participants.pop(user_id)

        if insufficient:
            names = "、".join(m.display_name for m in insufficient)
            await interaction.channel.send(f"⚠️ {names} は残高不足のため賭けから除外されました。")

        if len(view.participants) < 2:
            # 集まった掛け金は徴収済みの参加者へ返金して中止
            for user_id in view.participants:
                ref = db.collection("users").document(str(user_id))
                _add_points(db.transaction(), ref, view.amount)

            view.join_button.disabled = True
            view.confirm_button.disabled = True
            view.stop()
            return await interaction.response.edit_message(
                content="参加者が不足したため賭博は中止されました（徴収済みの掛け金は返金しました）。",
                embed=view.build_embed(),
                view=view,
            )

        view.pot = view.amount * len(view.participants)
        view.join_button.disabled = True
        view.confirm_button.disabled = True
        view.stop()

        select_view = WinnerSelectView(view)
        await interaction.response.edit_message(
            content=f"💰 掛け金を徴収しました。合計 **{view.pot:,}** wp。主催者は勝者を選んでください。",
            embed=view.build_embed(),
            view=select_view,
        )
        select_view.message = await interaction.original_response()


class WinnerSelectView(discord.ui.View):
    def __init__(self, gamble: GambleView):
        super().__init__(timeout=600)  # 10分
        self.gamble = gamble
        self.resolved = False
        self.message: discord.Message | None = None
        self.add_item(WinnerSelect(gamble, self))

    async def on_timeout(self):
        if self.resolved:
            return
        # 勝者未選択のままタイムアウトした場合は全員に返金
        for user_id in self.gamble.participants:
            ref = db.collection("users").document(str(user_id))
            _add_points(db.transaction(), ref, self.gamble.amount)

        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(
                    content="⏰ 勝者が選択されないままタイムアウトしたため、掛け金を全員に返金しました。",
                    view=self,
                )
            except discord.HTTPException:
                pass


class WinnerSelect(discord.ui.Select):
    def __init__(self, gamble: GambleView, parent_view: WinnerSelectView):
        options = [
            discord.SelectOption(label=member.display_name, value=str(user_id))
            for user_id, member in gamble.participants.items()
        ]
        super().__init__(placeholder="勝者を選択してください", options=options)
        self.gamble = gamble
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.gamble.host.id:
            return await interaction.response.send_message("主催者だけが選択できます。", ephemeral=True)

        if self.parent_view.resolved:
            return await interaction.response.send_message("すでに勝者が決定しています。", ephemeral=True)

        winner_id = int(self.values[0])
        winner = self.gamble.participants[winner_id]
        pot = self.gamble.pot

        ref = db.collection("users").document(str(winner_id))
        new_val = _add_points(db.transaction(), ref, pot)

        self.parent_view.resolved = True
        self.disabled = True
        await interaction.response.edit_message(
            content=f"🎉 **{winner.display_name}** さんの勝利！ **{pot:,}** wp を獲得しました（現在 **{new_val:,}** pt）",
            view=self.parent_view,
        )


class Gamble(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="gamble", description="賭博会を開始します（同じ通話部屋の人が参加できます）")
    @app_commands.describe(amount="1人あたりの掛け金（わくせいポイント）")
    async def gamble(self, interaction: discord.Interaction, amount: int):
        host = interaction.user
        if not isinstance(host, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        if amount <= 0:
            return await interaction.response.send_message("1以上の掛け金を指定してください。", ephemeral=True)

        voice_state = host.voice
        if voice_state is None or voice_state.channel is None:
            return await interaction.response.send_message("通話部屋に入ってから実行してください。", ephemeral=True)

        view = GambleView(host, amount, voice_state.channel.id)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: discord.Client):
    await bot.add_cog(Gamble(bot))
