import discord
from discord import app_commands
from discord.ext import commands
from google.cloud import firestore as gcf
from firebase_config import db
from config import ADMIN_ROLE_ID

SHOP_CHANNEL_ID = 1513541236261257306
IMAGE_PATH = "images/RED PLANET-description.png"
RED_PLANET_ROLE_ID = 1543216546086785135
WAKUSEI_KEY = "わくせい"
REQUIRED_POINTS = 1_000_000


class BuyRedPlanetRoleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="RED PLANETロールを購入する",
            style=discord.ButtonStyle.danger,
            custom_id="buy_red_planet_role",
        )

    async def callback(self, interaction: discord.Interaction):
        member = interaction.user
        if not isinstance(member, discord.Member):
            return await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

        role = interaction.guild.get_role(RED_PLANET_ROLE_ID)
        if role is None:
            return await interaction.response.send_message("ロールが見つかりませんでした。管理者にお問い合わせください。", ephemeral=True)

        if role in member.roles:
            return await interaction.response.send_message("すでにRED PLANETロールを持っています！", ephemeral=True)

        ref = db.collection("users").document(str(member.id))

        @gcf.transactional
        def _tx(tx, docref):
            snap = docref.get(transaction=tx)
            cur = int((snap.to_dict() or {}).get("points", {}).get(WAKUSEI_KEY, 0)) if snap.exists else 0
            if cur < REQUIRED_POINTS:
                return None, cur
            new_val = cur - REQUIRED_POINTS
            tx.set(docref, {"points": {WAKUSEI_KEY: new_val}}, merge=True)
            return new_val, cur

        new_val, cur = _tx(db.transaction(), ref)

        if new_val is None:
            needed = REQUIRED_POINTS - cur
            return await interaction.response.send_message(
                f"わくせいポイントが足りません。\n"
                f"現在：**{cur:,} wp** ／ 必要：**{REQUIRED_POINTS:,} wp**（あと **{needed:,} wp** 不足）",
                ephemeral=True,
            )

        await member.add_roles(role, reason="わくせいポイントによるRED PLANETロール購入")
        await interaction.response.send_message(
            f"🎉 RED PLANETロールを購入しました！\n"
            f"残りわくせいポイント：**{new_val:,} wp**",
            ephemeral=True,
        )


class RedPlanetShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(BuyRedPlanetRoleButton())


class RedPlanetShop(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    @app_commands.command(name="post_wakusei_red_planet_shop", description="RED PLANETロールショップメッセージをチャンネルに投稿します（管理者専用）")
    async def post_wakusei_red_planet_shop(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not any(r.id == ADMIN_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("権限がありません", ephemeral=True)

        channel = self.bot.get_channel(SHOP_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return await interaction.response.send_message("チャンネルが見つかりませんでした。", ephemeral=True)

        await channel.send(file=discord.File(IMAGE_PATH))
        await channel.send(view=RedPlanetShopView())
        await interaction.response.send_message("ショップメッセージを投稿しました！", ephemeral=True)


async def setup(bot: discord.Client):
    bot.add_view(RedPlanetShopView())
    await bot.add_cog(RedPlanetShop(bot))
