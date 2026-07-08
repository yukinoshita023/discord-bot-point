import discord
from datetime import datetime, timezone, timedelta
from firebase_config import db

WAKUSEI_KEY = "わくせい"
LOGIN_BONUS = 500
JST = timezone(timedelta(hours=9))

async def handle_login_bonus(bot: discord.Client, member: discord.Member, before, after) -> None:
    if member.bot:
        return

    # 通話部屋への入室でなければ対象外
    if after.channel is None:
        return

    today = datetime.now(JST).strftime("%Y-%m-%d")

    user_ref = db.collection("users").document(str(member.id))
    snap = user_ref.get()
    data = snap.to_dict() if snap.exists else {}

    # 今日すでに受け取り済みなら何もしない
    if data.get("last_login_bonus") == today:
        return

    points = data.get("points", {})
    new_wakusei = int(points.get(WAKUSEI_KEY, 0)) + LOGIN_BONUS

    user_ref.set(
        {
            "points": {WAKUSEI_KEY: new_wakusei},
            "last_login_bonus": today,
        },
        merge=True,
    )

    print(f"{member.display_name} にログインボーナス {LOGIN_BONUS}WP を付与しました")

    # 入室した通話部屋内のテキストチャットに通知する
    try:
        await after.channel.send(
            f"🎁 **{member.display_name}** さんがログインボーナス **+{LOGIN_BONUS}** WP を獲得しました！（現在 **{new_wakusei}** pt）"
        )
    except discord.Forbidden:
        print(f"チャンネル {after.channel.name} への送信権限がありません")
