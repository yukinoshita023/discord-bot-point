import discord
from firebase_config import db

async def setup(bot):

    @bot.tree.command(name="myrecord", description="自分のと通話記録を見ることができます")
    async def myrecord(interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
            else:
                data = {}

            points = data.get("points")
            if points is None:
                points = {}

            categories = ["モクモク", "ノンビリ", "ワイワイ"]
            response_lines = []

            for cat in categories:
                point = points.get(cat, 0)
                minutes = point * 5
                response_lines.append(f"**{cat}**：{minutes} 分")

            message = "\n".join(response_lines)
            await interaction.response.send_message(f"{interaction.user.mention} さんの通話記録：\n{message}")

        except Exception as e:
            print(f"[myrecord] エラー: {e}")
            await interaction.response.send_message("データ取得中にエラーが発生しました。")
