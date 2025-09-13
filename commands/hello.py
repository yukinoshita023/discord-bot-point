import discord

async def setup(bot):
    
    @bot.tree.command(name="hello", description="このコマンドによってポイントシステムの生存確認ができます")
    async def hello(interaction: discord.Interaction):
        await interaction.response.send_message("業務遂行中だ！")