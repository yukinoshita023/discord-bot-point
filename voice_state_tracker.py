from firebase_config import db
from config import CATEGORY_VC_MAPPING
import discord
from datetime import datetime
import asyncio

user_states = {}
user_tasks = {}

async def handle_voice_state_update(member: discord.Member, before, after):
    user_id = str(member.id)

    # カテゴリID取得（入室先）
    if after.channel and after.channel.category_id in CATEGORY_VC_MAPPING:
        category_id = after.channel.category_id

        # 移動 or 初参加の場合
        if user_id not in user_states or user_states[user_id]["category_id"] != category_id:
            # 既存のループがあればキャンセル
            if user_id in user_tasks:
                user_tasks[user_id].cancel()

            user_states[user_id] = {
                "joined_at": datetime.utcnow(),
                "category_id": category_id
            }

            # ログ出力
            print(f"[LOG] {member.display_name} が「{CATEGORY_VC_MAPPING[category_id]}」カテゴリに入室しました。")

            # 新しくループ開始
            task = asyncio.create_task(grant_points_loop(user_id))
            user_tasks[user_id] = task

    # VC退出時
    elif before.channel and before.channel.category_id in CATEGORY_VC_MAPPING:
        if user_id in user_states:
            print(f"[LOG] {member.display_name} が「{CATEGORY_VC_MAPPING[before.channel.category_id]}」カテゴリから退出しました。")
            user_states.pop(user_id)

        if user_id in user_tasks:
            user_tasks[user_id].cancel()
            user_tasks.pop(user_id)

async def grant_points_loop(user_id):
    try:
        while user_id in user_states:
            await asyncio.sleep(300)  # 5分

            category_id = user_states[user_id]["category_id"]
            category_name = CATEGORY_VC_MAPPING[category_id]

            user_ref = db.collection("users").document(user_id)
            doc = user_ref.get()

            if doc.exists:
                data = doc.to_dict()
                points = data.get("points", {})
            else:
                points = {}

            # ポイント加算
            current = points.get(category_name, 0)
            points[category_name] = current + 1

            # merge=True なので、既存の質問回答は上書きされず、pointsだけ更新される
            user_ref.set({"points": points}, merge=True)

    except asyncio.CancelledError:
        # 退出やVC移動でキャンセルされた場合
        pass
