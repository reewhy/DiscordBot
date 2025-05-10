from asyncio import create_eager_task_factory
import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

async def create_embed(
    title: str,
    description: str,
    field: str,
    value: str,
    footer: str
):
    embed = discord.Embed(
        title = title,
        description = description,
        color = discord.Color.random()
    )

    embed..set_thumbnail(url = "https://plus.unsplash.com/premium_photo-1673967831980-1d377baaded2?fm=jpg&q=60&w=3000&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxzZWFyY2h8MXx8Y2F0c3xlbnwwfHwwfHx8MA%3D%3D")

    embed.add_field(name=field, value=value)

    embed.set_footer(text=footer)

    return embed

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
        field="Field name.",
        value="Value of the field.",
        footer="Footer of the field"
    )
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def dice(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        field: str,
        value: str,
        footer: str
    ):
        embed = create_embed(title, description, field, value, footer)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(EmbedAnswer(bot))

