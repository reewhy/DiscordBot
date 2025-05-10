import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # This line sets a name for a command and its description
    @app_commands.command(name="join", description="Simulate member joining.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def join(self, interaction: discord.Interaction, member: discord.Member):
       await self.bot.on_member_join(member)

    # This line sets a name for a command and its description
    @app_commands.command(name="leave", description="Simulate member leaving.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def leave(self, interaction: discord.Interaction, member: discord.Member):
       await self.bot.on_member_leave(member)

async def setup(bot):
    await bot.add_cog(Test(bot))
