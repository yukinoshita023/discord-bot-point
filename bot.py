import discord
from config import TOKEN
from commands import setup_commands
from voice_state_tracker import handle_voice_state_update
from reaction_tracker import handle_reaction_add, handle_reaction_remove

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self):
        await setup_commands(self)
        print("全コマンドを追加しました")

        await self.tree.sync()
        print("スラッシュコマンドを同期しました")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user}")

@bot.event
async def on_voice_state_update(member, before, after):
    await handle_voice_state_update(member, before, after)

# 追加: リアクション追加（カウント+1）
@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    await handle_reaction_add(bot, payload)

# 任意: リアクション削除（カウント-1したいなら有効化）
@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    await handle_reaction_remove(bot, payload)

bot.run(TOKEN)
