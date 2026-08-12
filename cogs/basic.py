import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # This line sets a name for a command and its description
    @app_commands.command(name="dice", description="Rolls a 6-sided die.")
    # With this function you're able to describe each parameter in your command
    @app_commands.describe(minimum = "Minimun rollable number", maximum="Maximum rollable number.")
    # Specify in which server you want to activate your bot
    async def dice(self, interaction: discord.Interaction, minimum: int, maximum: int):
        x = random.randint(minimum, maximum)

        await interaction.response.send_message(f"You rolled a {x}!")

async def setup(bot):
    await bot.add_cog(Basic(bot))
