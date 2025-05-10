import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

async def rps(action: int) -> int:
    x = random.randint(0, 2)

    # 0 = rock
    # 1 = paper
    # 2 = scissor

    if x == action: return 0
    elif action == 0:
        if x == 1:
            return -1
        else:
            return 1
    elif action == 1:
        if x == 0:
            return 1
        else:
            return -1
    else:
        if x == 0:
            return -1
        else:
            return 1


async def send_result(x: int, interaction: discord.Interaction):
    if x == 0:
        await interaction.response.send_message("You chose the same action.")
    elif x == 1:
        await interaction.response.send_message("You won!")
    else:
        await interaction.response.send_message("You lost.")

# Create a groyp of commands
@app_commands.guilds(GUILD_ID)
class RockPaperScissor(app_commands.Group):
    def __init__(self):
        super().__init__(name="rps", description="Play rock, paper, scissor")

    @app_commands.command(name="rock", description="Play rock")
    @app_commands.guilds(GUILD_ID)
    async def rock(self, interaction: discord.Interaction):
        x = await rps(0)
        await send_result(x, interaction)

    @app_commands.command(name="paper", description="Play paper.")
    @app_commands.guilds(GUILD_ID)
    async def paper(self, interaction: discord.Interaction):
        x = await rps(1)
        await send_result(x, interaction)

    @app_commands.command(name="scissor", description="Play scissor.")
    @app_commands.guilds(GUILD_ID)
    async def scissor(self, interaction: discord.Interaction):
        x = await rps(2)
        await send_result(x, interaction)

# All cogs need to inherit the class commands.Cog
class GroupCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Add a group of commands
        self.bot.tree.add_command(RockPaperScissor())
    
    # This line sets a name for a command and its description
    @app_commands.command(name="hi", description="Send a message from the bot.")
    # With this function you're able to describe each parameter in your command
    @app_commands.describe(msg = "Message to send.")
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def hi(self, interaction: discord.Interaction, msg: str = ""):
        await interaction.response.send_message(f"Hello, {msg}!")

async def setup(bot):
    await bot.add_cog(GroupCommands(bot))
