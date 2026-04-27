from google.cloud import firestore as gcf
import discord
from firebase_config import db
from config import NOTIFICATION_CHANNEL_ID

EVENT_KEY = "イベント"

async def handle_scheduled_event_create(bot: discord.Client, event: discord.ScheduledEvent) -> None:
    creator = event.creator
    if creator is None or creator.bot:
        return

    user_ref = db.collection("users").document(str(creator.id))

    snap = user_ref.get()
    current = 0
    if snap.exists:
        current = int(snap.to_dict().get("points", {}).get(EVENT_KEY, 0))
    new_value = current + 1

    user_ref.set({"points": {EVENT_KEY: new_value}}, merge=True)

    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel is None:
        print(f"通知チャンネルが見つかりません (ID: {NOTIFICATION_CHANNEL_ID})")
        return

    try:
        await channel.send(
            f"{creator.mention} の{EVENT_KEY}値を **+1** しました\n"
            f"{creator.mention} の{EVENT_KEY}値は現在 **{new_value}** です"
        )
    except discord.Forbidden:
        print(f"チャンネル {NOTIFICATION_CHANNEL_ID} への送信権限がありません")
