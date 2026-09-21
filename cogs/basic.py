import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timezone
import os

from config import GUILD_ID
from utils.debug import Logger

logger = Logger(os.path.basename(__file__).replace(".py", ""))


# =========================================================================
# 1. Specialized Modals
# =========================================================================

class MainBodyModal(discord.ui.Modal, title="Modifica Contenuto Base"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.embed_title.default = view.embed_data["title"]
        self.embed_description.default = view.embed_data["description"]
        self.embed_color.default = view.embed_data["color"]

    embed_title = discord.ui.TextInput(
        label="Titolo",
        placeholder="Inserisci il titolo dell'embed...",
        max_length=256,
        required=False
    )

    embed_description = discord.ui.TextInput(
        label="Descrizione",
        style=discord.TextStyle.paragraph,
        placeholder="Supporta formattazione Markdown...",
        max_length=4000,
        required=False
    )

    embed_color = discord.ui.TextInput(
        label="Colore HEX",
        placeholder="es. #5865F2 o FF0000",
        max_length=7,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed_data["title"] = self.embed_title.value.strip()
        self.view.embed_data["description"] = self.embed_description.value.strip()
        self.view.embed_data["color"] = self.embed_color.value.strip()
        await self.view.refresh_preview(interaction)


class AuthorFooterModal(discord.ui.Modal, title="Autore e Footer"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.author_name.default = view.embed_data["author_name"]
        self.author_icon.default = view.embed_data["author_icon"]
        self.footer_text.default = view.embed_data["footer_text"]
        self.footer_icon.default = view.embed_data["footer_icon"]

    author_name = discord.ui.TextInput(
        label="Nome Autore",
        placeholder="Testo in cima all'embed...",
        max_length=256,
        required=False
    )

    author_icon = discord.ui.TextInput(
        label="URL Icona Autore",
        placeholder="https://example.com/author.png",
        required=False
    )

    footer_text = discord.ui.TextInput(
        label="Testo Footer",
        placeholder="Testo a piè di pagina...",
        max_length=2048,
        required=False
    )

    footer_icon = discord.ui.TextInput(
        label="URL Icona Footer",
        placeholder="https://example.com/footer.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed_data["author_name"] = self.author_name.value.strip()
        self.view.embed_data["author_icon"] = self.author_icon.value.strip()
        self.view.embed_data["footer_text"] = self.footer_text.value.strip()
        self.view.embed_data["footer_icon"] = self.footer_icon.value.strip()
        await self.view.refresh_preview(interaction)


class MediaModal(discord.ui.Modal, title="Immagini e Miniature"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.image_url.default = view.embed_data["image_url"]
        self.thumbnail_url.default = view.embed_data["thumbnail_url"]

    image_url = discord.ui.TextInput(
        label="URL Immagine Grande",
        placeholder="https://example.com/banner.png",
        required=False
    )

    thumbnail_url = discord.ui.TextInput(
        label="URL Miniatura (Alto a destra)",
        placeholder="https://example.com/thumb.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        self.view.embed_data["image_url"] = self.image_url.value.strip()
        self.view.embed_data["thumbnail_url"] = self.thumbnail_url.value.strip()
        await self.view.refresh_preview(interaction)


class AddFieldModal(discord.ui.Modal, title="Aggiungi un Campo"):
    def __init__(self, view):
        super().__init__()
        self.view = view

    field_name = discord.ui.TextInput(
        label="Nome Campo (Titolo)",
        placeholder="es. Regola #1",
        max_length=256,
        required=True
    )

    field_value = discord.ui.TextInput(
        label="Valore Campo",
        style=discord.TextStyle.paragraph,
        placeholder="Descrizione del campo...",
        max_length=1024,
        required=True
    )

    inline = discord.ui.TextInput(
        label="Inline? (sì / no)",
        placeholder="Digita 'si' per affiancare il campo",
        default="no",
        max_length=3,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        is_inline = self.inline.value.strip().lower() in ["si", "sì", "yes", "true", "y"]
        self.view.embed_data["fields"].append({
            "name": self.field_name.value.strip(),
            "value": self.field_value.value.strip(),
            "inline": is_inline
        })
        await self.view.refresh_preview(interaction)


# =========================================================================
# 2. Interactive Builder Dashboard (View)
# =========================================================================

class EmbedBuilderView(discord.ui.View):
    def __init__(self, user: discord.Member, target_channel: discord.TextChannel):
        super().__init__(timeout=600)
        self.user = user
        self.target_channel = target_channel

        self.embed_data = {
            "title": "Titolo di Esempio",
            "description": "Clicca sui pulsanti sotto per modificare i testi, i campi e i colori!",
            "color": "#5865F2",
            "author_name": "",
            "author_icon": "",
            "footer_text": "",
            "footer_icon": "",
            "image_url": "",
            "thumbnail_url": "",
            "timestamp": True,
            "fields": []
        }

    def build_embed(self) -> discord.Embed:
        # Colore
        color = discord.Color.blurple()
        if self.embed_data["color"]:
            clean_hex = self.embed_data["color"].lstrip("#")
            try:
                color = discord.Color(int(clean_hex, 16))
            except ValueError:
                pass

        embed = discord.Embed(
            title=self.embed_data["title"] or None,
            description=self.embed_data["description"] or None,
            color=color
        )

        if self.embed_data["timestamp"]:
            embed.timestamp = datetime.now(timezone.utc)

        # Autore
        if self.embed_data["author_name"]:
            icon = self.embed_data["author_icon"] if self.embed_data["author_icon"].startswith(("http://", "https://")) else None
            embed.set_author(name=self.embed_data["author_name"], icon_url=icon)

        # Footer
        if self.embed_data["footer_text"]:
            icon = self.embed_data["footer_icon"] if self.embed_data["footer_icon"].startswith(("http://", "https://")) else None
            embed.set_footer(text=self.embed_data["footer_text"], icon_url=icon)

        # Media
        if self.embed_data["image_url"].startswith(("http://", "https://")):
            embed.set_image(url=self.embed_data["image_url"])

        if self.embed_data["thumbnail_url"].startswith(("http://", "https://")):
            embed.set_thumbnail(url=self.embed_data["thumbnail_url"])

        # Campi aggiuntivi
        for f in self.embed_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Non puoi interagire con questo editor.", ephemeral=True)
            return False
        return True

    async def refresh_preview(self, interaction: discord.Interaction):
        embed = self.build_embed()
        await interaction.response.edit_message(
            content=f"🛠️ **Embed Builder** — Canale di invio: {self.target_channel.mention}",
            embed=embed,
            view=self
        )

    # --- Buttons Row 1: Content editing ---

    @discord.ui.button(label="Testo & Colore", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def edit_main(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MainBodyModal(self))

    @discord.ui.button(label="Autore & Footer", style=discord.ButtonStyle.primary, emoji="👤", row=0)
    async def edit_author_footer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AuthorFooterModal(self))

    @discord.ui.button(label="Immagini", style=discord.ButtonStyle.primary, emoji="🖼️", row=0)
    async def edit_media(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MediaModal(self))

    # --- Buttons Row 2: Fields & Utilities ---

    @discord.ui.button(label="Aggiungi Campo", style=discord.ButtonStyle.secondary, emoji="➕", row=1)
    async def add_field(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.embed_data["fields"]) >= 25:
            await interaction.response.send_message("❌ Hai raggiunto il limite massimo di 25 campi.", ephemeral=True)
            return
        await interaction.response.send_modal(AddFieldModal(self))

    @discord.ui.button(label="Svuota Campi", style=discord.ButtonStyle.secondary, emoji="🧹", row=1)
    async def clear_fields(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed_data["fields"] = []
        await self.refresh_preview(interaction)

    @discord.ui.button(label="Timestamp On/Off", style=discord.ButtonStyle.secondary, emoji="🕒", row=1)
    async def toggle_timestamp(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.embed_data["timestamp"] = not self.embed_data["timestamp"]
        await self.refresh_preview(interaction)

    # --- Buttons Row 3: Final actions ---

    @discord.ui.button(label="Invia Embed", style=discord.ButtonStyle.success, emoji="🚀", row=2)
    async def send_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.build_embed()
        try:
            await self.target_channel.send(embed=embed)
            await interaction.response.edit_message(
                content=f"✅ Embed inviato con successo in {self.target_channel.mention}!",
                embed=None,
                view=None
            )
            self.stop()
        except discord.Forbidden:
            await interaction.response.send_message(
                f"❌ Non ho i permessi necessari per inviare messaggi in {self.target_channel.mention}.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Errore durante l'invio: {e}", ephemeral=True)

    @discord.ui.button(label="Annulla", style=discord.ButtonStyle.danger, emoji="✖️", row=2)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="🚫 Creazione embed annullata.", embed=None, view=None)
        self.stop()


# =========================================================================
# 3. Cog Definition
# =========================================================================

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

    @app_commands.command(name="embed", description="Apre l'Embed Builder avanzato con anteprima interattiva.")
    @app_commands.describe(channel="Canale in cui inviare l'embed finale (default: canale corrente).")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guilds(*GUILD_ID)
    async def embed_builder(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        view = EmbedBuilderView(user=interaction.user, target_channel=target_channel)
        initial_embed = view.build_embed()

        await interaction.response.send_message(
            content=f"🛠️ **Embed Builder** — Canale di invio: {target_channel.mention}",
            embed=initial_embed,
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Basic(bot))