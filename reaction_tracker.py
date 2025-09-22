from google.cloud import firestore as gcf # DBの数値を計算するモジュール
import discord
from firebase_config import db

POINT_KEY = "リアクション"

# リアクション追加で +1
async def handle_reaction_add(bot: discord.Client, payload: discord.RawReactionActionEvent) -> None:
    if bot.user and payload.user_id == bot.user.id:
        return

    user_id = str(payload.user_id)
    user_ref = db.collection("users").document(user_id)

    user_ref.set(
        {
            "points": {POINT_KEY: gcf.Increment(1)}
        },
        merge=True,
    )

# リアクション削除で -1（ただし0未満禁止）
async def handle_reaction_remove(bot: discord.Client, payload: discord.RawReactionActionEvent) -> None:
    if payload.guild_id is None:
        return
    if bot.user and payload.user_id == bot.user.id:
        return

    user_id = str(payload.user_id)
    user_ref = db.collection("users").document(user_id)

    @gcf.transactional
    def _tx(transaction, ref):
        snap = ref.get(transaction=transaction)
        cur = 0
        if snap.exists:
            cur = int(snap.to_dict().get("points", {}).get(POINT_KEY, 0))
        new_val = max(0, cur - 1)
        transaction.set(
            ref,
            {"points": {POINT_KEY: new_val}},
            merge=True,
        )

    transaction = db.transaction()
    _tx(transaction, user_ref)
