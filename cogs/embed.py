from asyncio import create_eager_task_factory
import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger


import os

from utils.embed_factory import EmbedFactory

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class EmbedAnswer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # This line sets a name for a command and its description
    @app_commands.command(name="embed", description="Answers with an embed message.")
    # With this function you're able to describe each parameter in your command
    @app_commands.describe(
        title="Title of the embed.",
        description="Description of the embed.",
    )
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def dice(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str
    ):
        embed = EmbedFactory.create_embed(
            description=description,
            title = title,
            interaction=interaction
        )

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EmbedAnswer(bot))

