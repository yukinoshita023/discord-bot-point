from google.cloud import firestore as gcf
import discord
from firebase_config import db
from config import NOTIFICATION_CHANNEL_ID

EVENT_KEY = "イベント"
WAKUSEI_KEY = "わくせい"
WAKUSEI_EVENT_BONUS = 5000

async def handle_scheduled_event_update(bot: discord.Client, before: discord.ScheduledEvent, after: discord.ScheduledEvent) -> None:
    if before.status == after.status or after.status != discord.EventStatus.active:
        return

    creator_id = after.creator_id
    if creator_id is None:
        return

    creator = after.creator
    if creator is None:
        try:
            creator = await bot.fetch_user(creator_id)
        except discord.HTTPException:
            return

    if creator.bot:
        return

    bonus = WAKUSEI_EVENT_BONUS
    occurrence_key = after.start_time.isoformat()

    user_ref = db.collection("users").document(str(creator.id))
    event_ref = db.collection("scheduled_events").document(str(after.id))

    @gcf.transactional
    def _tx(tx, u_ref, ev_ref):
        ev_snap = ev_ref.get(transaction=tx)
        if ev_snap.exists and ev_snap.to_dict().get("last_granted_start_time") == occurrence_key:
            return None

        u_snap = u_ref.get(transaction=tx)
        data = u_snap.to_dict() if u_snap.exists else {}
        points = data.get("points", {})

        new_event = int(points.get(EVENT_KEY, 0)) + 1
        new_wakusei = int(points.get(WAKUSEI_KEY, 0)) + bonus

        tx.set(u_ref, {"points": {EVENT_KEY: new_event, WAKUSEI_KEY: new_wakusei}}, merge=True)
        tx.set(ev_ref, {"last_granted_start_time": occurrence_key}, merge=True)
        return new_event, new_wakusei

    result = _tx(db.transaction(), user_ref, event_ref)
    if result is None:
        return

    new_event, new_wakusei = result

    channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
    if channel is None:
        print(f"通知チャンネルが見つかりません (ID: {NOTIFICATION_CHANNEL_ID})")
        return

    try:
        await channel.send(
            f"イベント「{after.name}」が開始しました\n"
            f"{creator.mention} の{EVENT_KEY}値を **+1** しました\n"
            f"{creator.mention} の{EVENT_KEY}値は現在 **{new_event}** です\n"
            f"{creator.mention} のわくせいポイントに **+{bonus}** 付与しました（現在 **{new_wakusei}** pt）"
        )
    except discord.Forbidden:
        print(f"チャンネル {NOTIFICATION_CHANNEL_ID} への送信権限がありません")
