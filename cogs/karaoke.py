import os
from pathlib import Path

import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from karaoke_server.web import KaraokeSettings, create_app
from utils.debug import Logger
from utils.karaoke_system import KaraokeSystem

logger = Logger(os.path.basename(__file__).replace(".py", ""))

# Cartella "dist" del frontend compilato. Cambiala se metti il progetto altrove.
DEFAULT_DIST = Path(__file__).resolve().parent.parent / "karaoke_client" / "dist"


class KaraokeCog(commands.Cog):
    """Avvia il server web del karaoke dentro il bot e fornisce i comandi collegati."""

    def __init__(self, bot: commands.Bot, system: KaraokeSystem):
        self.bot = bot
        self.system = system
        self.runner: web.AppRunner | None = None

    # ------------------------------------------------------------------
    # Ciclo di vita: il server web parte e si ferma insieme al cog
    # ------------------------------------------------------------------
    async def cog_load(self):
        settings = KaraokeSettings(
            # Il Client ID di un'applicazione Discord coincide con l'ID del bot.
            client_id=os.getenv("DISCORD_CLIENT_ID") or str(self.bot.application_id),
            client_secret=os.getenv("DISCORD_CLIENT_SECRET", ""),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY", ""),
            dist_dir=Path(os.getenv("KARAOKE_DIST", DEFAULT_DIST)),
        )
        if not settings.client_secret:
            logger.warning("DISCORD_CLIENT_SECRET mancante: il login dell'Activity non funzionerà.")
        if not settings.youtube_api_key:
            logger.warning("YOUTUBE_API_KEY mancante: la ricerca dei brani non funzionerà.")

        host = os.getenv("KARAOKE_HOST", "0.0.0.0")
        port = int(os.getenv("KARAOKE_PORT", "3001"))
        try:
            self.runner = web.AppRunner(create_app(settings, self.system))
            await self.runner.setup()
            await web.TCPSite(self.runner, host, port).start()
            logger.info(f"Karaoke web server in ascolto su {host}:{port}")
        except OSError as e:
            # Es. porta già occupata: il bot deve comunque partire.
            logger.error(f"Impossibile avviare il server karaoke sulla porta {port}", exc_info=e)
            self.runner = None

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None

    # ------------------------------------------------------------------
    # Comandi
    # ------------------------------------------------------------------
    @app_commands.command(name="karaoke", description="Avvia il karaoke in questo canale vocale.")
    @app_commands.guilds(*GUILD_ID)
    @app_commands.guild_only()
    async def karaoke(self, interaction: discord.Interaction):
        try:
            await interaction.response.launch_activity()
        except discord.HTTPException as e:
            logger.error("launch_activity fallito", exc_info=e)
            await interaction.response.send_message(
                "❌ Non riesco ad avviare l'Activity. Controlla che sia abilitata nel Developer Portal.",
                ephemeral=True,
            )

    @app_commands.command(name="karaoke_top", description="Brani e cantanti più gettonati del server.")
    @app_commands.guilds(*GUILD_ID)
    @app_commands.guild_only()
    async def karaoke_top(self, interaction: discord.Interaction):
        songs = self.system.top_songs(interaction.guild_id, limit=5)
        singers = self.system.top_singers(interaction.guild_id, limit=5)

        if not songs:
            await interaction.response.send_message(
                "🎤 Nessun brano è ancora andato in scena. Usa `/karaoke` per iniziare!", ephemeral=True
            )
            return

        embed = discord.Embed(title="🎤 Classifica karaoke", colour=discord.Color.gold())
        embed.add_field(
            name="Brani più cantati",
            value="\n".join(
                f"{i}. [{s['title']}](https://www.youtube.com/watch?v={s['video_id']}) — {s['plays']}×"
                for i, s in enumerate(songs, 1)
            ),
            inline=False,
        )
        embed.add_field(
            name="Cantanti più attivi",
            value="\n".join(
                f"{i}. <@{s['singer_id']}> — {s['plays']} brani" for i, s in enumerate(singers, 1)
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, allowed_mentions=discord.AllowedMentions.none())


async def setup(bot):
    # Registrazione manuale come negli altri cog: serve il KaraokeSystem già creato nel main.
    raise RuntimeError("Usa bot.add_cog(KaraokeCog(bot, karaoke_system)) nel setup_hook.")
