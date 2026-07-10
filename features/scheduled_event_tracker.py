from google.cloud import firestore as gcf
import discord
from firebase_config import db
from config import NOTIFICATION_CHANNEL_ID

EVENT_KEY = "イベント"
WAKUSEI_KEY = "わくせい"
WAKUSEI_EVENT_BONUS = 5000

async def handle_scheduled_event_create(bot: discord.Client, event: discord.ScheduledEvent) -> None:
    creator = event.creator
    if creator is None or creator.bot:
        return

    bonus = WAKUSEI_EVENT_BONUS

    user_ref = db.collection("users").document(str(creator.id))

    snap = user_ref.get()
    data = snap.to_dict() if snap.exists else {}
    points = data.get("points", {})

    new_event = int(points.get(EVENT_KEY, 0)) + 1
    new_wakusei = int(points.get(WAKUSEI_KEY, 0)) + bonus

    user_ref.set({"points": {EVENT_KEY: new_event, WAKUSEI_KEY: new_wakusei}}, merge=True)

    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel is None:
        print(f"通知チャンネルが見つかりません (ID: {NOTIFICATION_CHANNEL_ID})")
        return

    try:
        await channel.send(
            f"{creator.mention} の{EVENT_KEY}値を **+1** しました\n"
            f"{creator.mention} の{EVENT_KEY}値は現在 **{new_event}** です\n"
            f"{creator.mention} のわくせいポイントに **+{bonus}** 付与しました（現在 **{new_wakusei}** pt）"
        )
    except discord.Forbidden:
        print(f"チャンネル {NOTIFICATION_CHANNEL_ID} への送信権限がありません")
