import datetime
import os
from discord import app_commands
from discord.ext import commands
import discord

from config import GUILD_ID
from utils.bd_system import BirthdaySystem
from utils.debug import Logger
from utils.embed_factory import EmbedFactory

logger = Logger(os.path.basename(__file__).replace(".py", ""))


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
    @app_commands.describe(
        compleanno="Inserisci la data nel formato GG-MM-AAAA (es. 25-12-2000)"
    )
    async def set(self, interaction: discord.Interaction, compleanno: str):
      await interaction.response.defer(ephemeral=True)

      # Try parsing the date string (accepts DD-MM-YYYY or YYYY-MM-DD)
      parsed_date = None
      for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
          parsed_date = datetime.datetime.strptime(compleanno, fmt).date()
          break
        except ValueError:
          continue

      if not parsed_date:
        await interaction.followup.send(
            "Formato data non valido! Usa **GG-MM-AAAA** (es. `25-12-2000`).",
            ephemeral=True,
        )
        return

      self.birthday_system.set_birthday(interaction.user.id, parsed_date)
      await interaction.followup.send(
          f"La tua data di nascita ({parsed_date.strftime('%d/%m/%Y')}) è stata registrata.",
          ephemeral=True,
      )

    @app_commands.command(name="remove", description="Rimuovi compleanno")
    async def remove(self, interaction: discord.Interaction):
      self.birthday_system.remove_birthday(interaction.user.id)
      await interaction.response.send_message(
          "La tua data di nascita è stata rimossa.", ephemeral=True
      )

    @app_commands.command(
        name="check",
        description="Controlla la data di compleanno di un determinato user",
    )
    @app_commands.describe(
        user="Utente di cui si vuole controllare il compleanno."
    )
    async def check(
            self, interaction: discord.Interaction, user: discord.User = None
    ):
        await interaction.response.defer(ephemeral=True)

        target_user = user or interaction.user
        birthday_data = self.birthday_system.get_birthday(target_user.id)

        if not birthday_data:
            error_embed = EmbedFactory.create_embed(
                title="Errore",
                description=(
                    f"Il compleanno di {target_user.mention} non è stato"
                    " registrato."
                ),
                colour=discord.Color.red(),
                author="Birthday System",
                interaction=interaction,
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)
            return

        # Unpack the actual date from the database tuple (e.g., (date, ) -> date)
        birthday = (
            birthday_data[0]
            if isinstance(birthday_data, (tuple, list))
            else birthday_data
        )

        result = EmbedFactory.create_embed(
            title="Compleanno",
            description=(
                f"Il compleanno di {target_user.mention} è il"
                f" {birthday.strftime('%d/%m/%Y')}."
            ),
            colour=discord.Color.random(),
            author="Birthday System",
            interaction=interaction,
            thumbnail=target_user.avatar.url if target_user.avatar else None,
        )

        await interaction.followup.send(embed=result, ephemeral=True)