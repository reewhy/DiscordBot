import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dice", description="Rolls a 6-sided die.")
    @app_commands.guilds(GUILD_ID)
    async def dice(self, interaction: discord.Interaction):
        result = random.randint(1, 6)
        await interaction.response.send_message(f"You rolled a {result}!")

    @app_commands.command(name="test")
    @app_commands.guilds(GUILD_ID)
    async def test(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"You rolled a {random.randint(1, 6)}")

async def setup(bot):
    await bot.add_cog(Fun(bot))
