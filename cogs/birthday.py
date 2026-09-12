import datetime

import discord
from discord.ext import commands
from discord import app_commands
import os

from config import GUILD_ID
from utils.bd_system import BirthdaySystem
from utils.debug import Logger
from utils.embed_factory import EmbedFactory
from utils.board_system import BoardSystem

logger = Logger(os.path.basename(__file__).replace('.py', ''))

class BirthdayCog(commands.Cog):
    def __init__(self, bot, birthday_system: BirthdaySystem):
        self.bot = bot
        self.birthday_system = birthday_system
        self.bot.tree.add_command(self.Birthday(birthday_system, bot))

    @app_commands.guilds(*GUILD_ID)
    class Birthday(app_commands.Group):
        def __init__(self, birthday_system: BirthdaySystem, bot: commands.Bot):
            super().__init__(name="birthday", description="Boh")
            self.birthday_system = birthday_system
            self.bot = bot

        @app_commands.command(name="set", description="Imposta compleanno")
        async def set(self, interaction: discord.Interaction, compleanno: datetime.date):
            await interaction.response.defer()

            self.birthday_system.set_birthday(interaction.user.id, compleanno)

            await interaction.followup.send("La tua data di nascita è stata registrata.", ephemeral=True)

        @app_commands.command(name="remove", description="Rimuovi compleanno")
        async def remove(self, interaction: discord.Interaction):
            self.birthday_system.remove_birthday(interaction.user.id)

            await interaction.response.send_message("La tua data di nascita è stata rimossa.", ephemeral=True)

