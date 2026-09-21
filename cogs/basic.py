import discord
from discord.ext import commands
import random
from discord import app_commands
from datetime import datetime, timezone
import os

from config import GUILD_ID
from utils.debug import Logger

logger = Logger(os.path.basename(__file__).replace(".py", ""))


class EmbedModal(discord.ui.Modal, title="Crea un Embed"):
    """Pop-up modal form to create a custom embed."""

    embed_title = discord.ui.TextInput(
        label="Titolo",
        placeholder="Inserisci il titolo dell'embed...",
        max_length=256,
        required=True
    )

    embed_description = discord.ui.TextInput(
        label="Descrizione",
        style=discord.TextStyle.paragraph,
        placeholder="Inserisci il contenuto dell'embed...",
        max_length=4000,
        required=True
    )

    embed_color = discord.ui.TextInput(
        label="Colore HEX (Opzionale)",
        placeholder="es. #5865F2 o lascia vuoto per blu predefinito",
        max_length=7,
        required=False
    )

    embed_image = discord.ui.TextInput(
        label="URL Immagine (Opzionale)",
        placeholder="https://example.com/image.png",
        required=False
    )

    embed_footer = discord.ui.TextInput(
        label="Footer (Opzionale)",
        placeholder="Testo a piè di pagina...",
        max_length=2048,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Parse color if provided, default to Blurple
        color = discord.Color.blurple()
        if self.embed_color.value:
            clean_hex = self.embed_color.value.lstrip("#")
            try:
                color = discord.Color(int(clean_hex, 16))
            except ValueError:
                pass

        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.embed_description.value,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )

        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        if self.embed_image.value.strip().startswith(("http://", "https://")):
            embed.set_image(url=self.embed_image.value.strip())

        if self.embed_footer.value.strip():
            embed.set_footer(text=self.embed_footer.value.strip())

        # Send the embed to the channel
        await interaction.response.send_message(embed=embed)
        logger.info(f"Custom embed created via modal by {interaction.user.name}")


class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dice", description="Rolls a dice within a custom range.")
    @app_commands.describe(minimum="Minimum rollable number", maximum="Maximum rollable number.")
    @app_commands.guilds(*GUILD_ID)
    async def dice(self, interaction: discord.Interaction, minimum: int, maximum: int):
        if minimum > maximum:
            await interaction.response.send_message(
                "❌ Il valore minimo non può essere maggiore del valore massimo.",
                ephemeral=True
            )
            return

        x = random.randint(minimum, maximum)
        await interaction.response.send_message(f"🎲 You rolled a **{x}**!")

    # ---------------------------------------------------------
    # Option 1: Modal Builder (Interactive UI Pop-up)
    # ---------------------------------------------------------
    @app_commands.command(name="embed", description="Apre un modulo per creare un embed personalizzato.")
    @app_commands.guilds(*GUILD_ID)
    @app_commands.checks.has_permissions(administrator=True)
    async def create_embed_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EmbedModal())

    # ---------------------------------------------------------
    # Option 2: Quick Slash Command Builder (Direct Parameters)
    # ---------------------------------------------------------
    @app_commands.command(name="quickembed", description="Invia rapidamente un embed specificando i parametri.")
    @app_commands.describe(
        title="Titolo dell'embed.",
        description="Testo principale dell'embed.",
        color_hex="Colore HEX (es. #FF0000).",
        image_url="URL di un'immagine da mostrare in grande.",
        thumbnail_url="URL di una miniatura da mostrare in alto a destra."
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def quick_embed(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color_hex: str = None,
        image_url: str = None,
        thumbnail_url: str = None
    ):
        color = discord.Color.blurple()
        if color_hex:
            try:
                color = discord.Color(int(color_hex.lstrip("#"), 16))
            except ValueError:
                pass

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        if image_url and image_url.startswith(("http://", "https://")):
            embed.set_image(url=image_url)

        if thumbnail_url and thumbnail_url.startswith(("http://", "https://")):
            embed.set_thumbnail(url=thumbnail_url)

        await interaction.response.send_message(embed=embed)
        logger.info(f"Quick embed sent by {interaction.user.name}")


async def setup(bot):
    await bot.add_cog(Basic(bot))