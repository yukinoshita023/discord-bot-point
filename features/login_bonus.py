import discord
from datetime import datetime, timezone, timedelta
from google.cloud import firestore as gcf
from firebase_config import db
from config import LOGIN_BONUS_EXCLUDED_VC_IDS

WAKUSEI_KEY = "わくせい"
LOGIN_BONUS = 500
JST = timezone(timedelta(hours=9))


@gcf.transactional
def _grant_login_bonus(tx, ref, today: str) -> int | None:
    data = ref.get(transaction=tx).to_dict() or {}

    # 今日すでに受け取り済みなら何もしない
    if data.get("last_login_bonus") == today:
        return None

    new_wakusei = int(data.get("points", {}).get(WAKUSEI_KEY, 0)) + LOGIN_BONUS
    tx.set(
        ref,
        {
            "points": {WAKUSEI_KEY: new_wakusei},
            "last_login_bonus": today,
        },
        merge=True,
    )
    return new_wakusei


async def handle_login_bonus(bot: discord.Client, member: discord.Member, before, after) -> None:
    if member.bot:
        return

    # 通話部屋への入室でなければ対象外
    if after.channel is None:
        return

    # 自由作成部屋は対象外
    if after.channel.id in LOGIN_BONUS_EXCLUDED_VC_IDS:
        return

    today = datetime.now(JST).strftime("%Y-%m-%d")

    user_ref = db.collection("users").document(str(member.id))
    new_wakusei = _grant_login_bonus(db.transaction(), user_ref, today)
    if new_wakusei is None:
        return

    print(f"{member.display_name} にログインボーナス {LOGIN_BONUS}WP を付与しました")

    # 入室した通話部屋内のテキストチャットに通知する
    try:
        await after.channel.send(
            f"🎁 **{member.display_name}** さんがログインボーナス **+{LOGIN_BONUS}** WP を獲得しました！（現在 **{new_wakusei}** pt）"
        )
    except discord.Forbidden:
        print(f"チャンネル {after.channel.name} への送信権限がありません")
