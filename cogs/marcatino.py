import asyncio
import os

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID, MERCATINO_FORUM_ID
from utils.debug import Logger
from utils.mercatino_system import MercatinoSystem

logger = Logger(os.path.basename(__file__).replace(".py", ""))

IMAGE_EXTS = ('png', 'jpg', 'jpeg', 'gif', 'webp')


def naive(dt):
    """Datetime UTC 'naive' (come lo vuole MySQL DATETIME)."""
    return dt.replace(tzinfo=None) if dt else None


async def build_snapshot(thread: discord.Thread) -> tuple[dict, list[dict]]:
    """Legge il thread + il messaggio iniziale e prepara i dati per il database."""
    try:
        # Nei forum l'id del messaggio iniziale coincide con l'id del thread
        msg = await thread.fetch_message(thread.id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        msg = None

    attachments = []
    if msg:
        author = msg.author
        author_id, author_name, author_avatar = author.id, author.display_name[:100], author.display_avatar.url
        content = msg.content
        attachments = [
            dict(url=a.url, filename=a.filename, content_type=a.content_type)
            for a in msg.attachments
        ]
    else:
        author_id, author_name, author_avatar = thread.owner_id, None, None
        content = None

    image_url = next((a["url"] for a in attachments
                      if (a["filename"] or "").lower().endswith(IMAGE_EXTS)), None)

    last_activity = (discord.utils.snowflake_time(thread.last_message_id)
                     if thread.last_message_id else thread.created_at)

    post = dict(
        thread_id=thread.id,
        guild_id=thread.guild.id,
        forum_id=thread.parent_id,
        author_id=author_id,
        author_name=author_name,
        author_avatar=author_avatar,
        title=thread.name[:100],
        content=content,
        tags=", ".join(t.name for t in thread.applied_tags)[:255] or None,
        image_url=image_url,
        attachments=len(attachments),
        jump_url=thread.jump_url,
        message_count=thread.message_count or 0,
        archived=int(thread.archived),
        locked=int(thread.locked),
        created_at=naive(thread.created_at),
        last_activity_at=naive(last_activity),
    )
    return post, attachments


class MercatinoCog(commands.Cog):
    def __init__(self, bot, mercatino_system: MercatinoSystem):
        self.bot = bot
        self.db = mercatino_system
        self.bot.tree.add_command(self.Mercatino(self))

    async def save_thread(self, thread: discord.Thread):
        post, attachments = await build_snapshot(thread)
        self.db.upsert_post(post)
        self.db.replace_attachments(thread.id, attachments)

    # ------------------------------------------------------------------
    # LISTENER: tiene il database aggiornato in tempo reale
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        if thread.parent_id != MERCATINO_FORUM_ID:
            return
        await asyncio.sleep(2)  # lascia il tempo al messaggio iniziale di essere disponibile
        try:
            await self.save_thread(thread)
        except Exception as e:
            logger.info(f"ERRORE salvataggio nuovo annuncio {thread.id}: {e}")

    @commands.Cog.listener()
    async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
        if after.parent_id != MERCATINO_FORUM_ID:
            return
        try:
            await self.save_thread(after)  # titolo, tag, archiviato, bloccato...
        except Exception as e:
            logger.info(f"ERRORE aggiornamento annuncio {after.id}: {e}")

    @commands.Cog.listener()
    async def on_raw_thread_delete(self, payload: discord.RawThreadDeleteEvent):
        if payload.parent_id == MERCATINO_FORUM_ID:
            self.db.deactivate_post(payload.thread_id)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        # Modifica del messaggio iniziale (es. prezzo cambiato)
        if payload.message_id != payload.channel_id:
            return
        thread = self.bot.get_channel(payload.channel_id)
        if isinstance(thread, discord.Thread) and thread.parent_id == MERCATINO_FORUM_ID:
            try:
                await self.save_thread(thread)
            except Exception as e:
                logger.info(f"ERRORE aggiornamento contenuto annuncio {thread.id}: {e}")

    # ------------------------------------------------------------------
    # COMANDI
    # ------------------------------------------------------------------
    @app_commands.guilds(*GUILD_ID)
    class Mercatino(app_commands.Group):
        def __init__(self, cog: "MercatinoCog"):
            super().__init__(name="mercatino", description="Gestione del database del mercatino.")
            self.cog = cog
            self._sync_lock = asyncio.Lock()

        @app_commands.command(name="sync",
                              description="[STAFF] Salva nel database tutti gli annunci del forum mercatino.")
        @app_commands.checks.has_permissions(administrator=True)
        async def sync(self, interaction: discord.Interaction):
            if self._sync_lock.locked():
                await interaction.response.send_message("⏳ Una sincronizzazione è già in corso.", ephemeral=True)
                return

            async with self._sync_lock:
                await interaction.response.defer(ephemeral=True)
                guild = interaction.guild

                forum = guild.get_channel(MERCATINO_FORUM_ID)
                if forum is None:
                    try:
                        forum = await guild.fetch_channel(MERCATINO_FORUM_ID)
                    except (discord.NotFound, discord.Forbidden):
                        forum = None
                if not isinstance(forum, discord.ForumChannel):
                    await interaction.followup.send(
                        "Forum mercatino non trovato (controlla `MERCATINO_FORUM_ID` in config.py).",
                        ephemeral=True)
                    return

                async def progress(text: str):
                    try:
                        await interaction.edit_original_response(content=text)
                    except discord.HTTPException:
                        pass  # token scaduto (15 min)

                await progress("🔄 Recupero la lista degli annunci...")

                # Thread attivi + archiviati
                threads = {t.id: t for t in await guild.active_threads() if t.parent_id == forum.id}
                async for t in forum.archived_threads(limit=None):
                    threads[t.id] = t

                total = len(threads)
                saved = failed = 0
                for thread_id in sorted(threads):
                    try:
                        await self.cog.save_thread(threads[thread_id])
                        saved += 1
                    except Exception as e:
                        failed += 1
                        logger.info(f"ERRORE sync annuncio {thread_id}: {e}")

                    if (saved + failed) % 20 == 0:
                        await progress(f"🔄 Elaborati {saved + failed}/{total} annunci...")

                # Annunci nel DB che non esistono più nel forum -> inattivi
                removed = 0
                for thread_id in self.cog.db.get_active_ids(guild.id) - set(threads):
                    self.cog.db.deactivate_post(thread_id)
                    removed += 1

                summary = (
                    f"✅ **Sync mercatino completato!**\n"
                    f"• Annunci trovati nel forum: **{total}**\n"
                    f"• Salvati: **{saved}**\n"
                    f"• Errori: **{failed}**\n"
                    f"• Segnati come rimossi (non più nel forum): **{removed}**"
                )
                logger.info(f"Mercatino sync done: total={total}, saved={saved}, failed={failed}, removed={removed}")
                try:
                    await interaction.edit_original_response(content=summary)
                except discord.HTTPException:
                    await interaction.channel.send(f"{interaction.user.mention}\n{summary}")