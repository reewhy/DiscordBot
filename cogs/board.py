import asyncio
import os
import re

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from utils.board_system import BoardSystem
from utils.debug import Logger
from utils.embed_factory import EmbedFactory

logger = Logger(os.path.basename(__file__).replace(".py", ""))

JUMP_RE = re.compile(r'channels/(\d+)/(\d+)/(\d+)')
IMAGE_EXTS = ('png', 'jpg', 'jpeg', 'gif', 'webp')


def snippet(text: str | None, limit: int = 60) -> str:
    text = (text or "").strip()
    if not text:
        return "*[Solo Immagine/Allegato]*"
    return text[:limit] + "..." if len(text) > limit else text


def jump(post: dict) -> str:
    return post.get("jump_url") or "https://discord.com"


class UserShamePagination(discord.ui.View):
    def __init__(self, target: discord.Member, posts: list[dict], per_page: int = 5):
        super().__init__(timeout=180)
        self.target = target
        self.posts = posts
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = max(1, (len(posts) + per_page - 1) // per_page)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1

    def create_embed(self):
        embed = EmbedFactory.create_embed(
            title=f"📜 I messaggi di {self.target.display_name}",
            description=f"Pagina {self.current_page + 1} di {self.max_pages} (Totale: {len(self.posts)})",
            colour=discord.Color.purple()
        )
        embed.set_thumbnail(url=self.target.display_avatar.url)

        start = self.current_page * self.per_page
        for idx, post in enumerate(self.posts[start:start + self.per_page], start + 1):
            embed.add_field(
                name=f"#{idx} - (⭐ {post['stars']})",
                value=f"{snippet(post['content'])}\n**[Vai al messaggio]({jump(post)})**",
                inline=False
            )
        return embed

    @discord.ui.button(label="◀️ Precedente", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Successivo ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class HallOfShameCog(commands.Cog):
    def __init__(self, bot, board_system: BoardSystem):
        self.bot = bot
        self.board_system = board_system
        self.bot.tree.add_command(self.Shame(board_system, bot))

    @app_commands.guilds(*GUILD_ID)
    class Shame(app_commands.Group):
        def __init__(self, board_system: BoardSystem, bot: commands.Bot):
            super().__init__(name="shame", description="Statistiche e classifiche della Hall of Shame.")
            self.board_system = board_system
            self.bot = bot
            self._sync_lock = asyncio.Lock()

        # ------------------------------------------------------------------
        # SYNC (STAFF): ricostruisce tutto il database dalla board
        # ------------------------------------------------------------------
        @app_commands.command(name="sync",
                              description="[STAFF] Sincronizza il database con la Hall of Shame.")
        @app_commands.describe(voters="Ricalcola anche chi ha messo le stelle (più lento)")
        @app_commands.checks.has_permissions(administrator=True)
        async def sync(self, interaction: discord.Interaction, voters: bool = True):
            if self._sync_lock.locked():
                await interaction.response.send_message("⏳ Una sincronizzazione è già in corso.", ephemeral=True)
                return

            async with self._sync_lock:
                await interaction.response.defer(ephemeral=True)
                bs = self.board_system
                guild = interaction.guild

                board_channel_id = bs.get_board_channel(guild.id)
                if not board_channel_id:
                    await interaction.followup.send("Canale board non configurato. Usa /setboard.", ephemeral=True)
                    return
                board_channel = guild.get_channel(board_channel_id) or await guild.fetch_channel(board_channel_id)

                counters = {"scanned": 0, "synced": 0, "orig_deleted": 0, "skipped": 0}
                seen_board_ids = set()

                async def progress(text: str):
                    try:
                        await interaction.edit_original_response(content=text)
                    except discord.HTTPException:
                        pass  # token scaduto (15 min) o messaggio non modificabile

                await progress("🔄 Sincronizzazione avviata...")

                async for b_msg in board_channel.history(limit=None, oldest_first=True):
                    if b_msg.author.id != self.bot.user.id or not b_msg.embeds:
                        continue
                    counters["scanned"] += 1

                    embed = b_msg.embeds[0]
                    desc = embed.description or ""
                    match = JUMP_RE.search(desc)
                    if not match:
                        counters["skipped"] += 1
                        continue

                    orig_guild_id, orig_channel_id, orig_msg_id = map(int, match.groups())
                    seen_board_ids.add(b_msg.id)
                    legacy = bs.get_legacy_row(orig_msg_id)

                    # Provo a recuperare il messaggio originale
                    orig = None
                    try:
                        channel = guild.get_channel_or_thread(orig_channel_id) or await guild.fetch_channel(
                            orig_channel_id)
                        orig = await channel.fetch_message(orig_msg_id)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass

                    voter_ids = None
                    if orig:
                        author = orig.author
                        reaction = discord.utils.get(orig.reactions, emoji='⭐')
                        stars = reaction.count if reaction else 0
                        if voters and reaction:
                            voter_ids = [u.id async for u in reaction.users() if not u.bot]
                            stars = len(voter_ids)
                        elif voters:
                            voter_ids = []

                        image_url = next((a.url for a in orig.attachments
                                          if a.filename.lower().endswith(IMAGE_EXTS)), None)
                        author_id = author.id
                        post = dict(
                            author_id=author_id,
                            author_name=author.display_name[:100],
                            author_avatar=author.display_avatar.url,
                            content=orig.content,
                            image_url=image_url,
                            attachments=len(orig.attachments),
                            message_created_at=orig.created_at.replace(tzinfo=None),
                        )
                    else:
                        # Originale cancellato: salvo quello che resta nell'embed della board
                        counters["orig_deleted"] += 1
                        author_id = legacy["author_id"] if legacy else None
                        stars = legacy["reactions"] if legacy and legacy["reactions"] else 0
                        post = dict(
                            author_id=author_id,
                            author_name=(embed.author.name[:100] if embed.author and embed.author.name else None),
                            author_avatar=embed.author.icon_url if embed.author else None,
                            content=desc.split("**[Jump to message!]")[0].strip(),
                            image_url=embed.image.url if embed.image else None,
                            attachments=1 if embed.image else 0,
                            message_created_at=None,
                        )

                    bs.upsert_post(dict(
                        message_id=orig_msg_id,
                        guild_id=guild.id,
                        channel_id=orig_channel_id,
                        jump_url=f"https://discord.com/channels/{orig_guild_id}/{orig_channel_id}/{orig_msg_id}",
                        board_channel_id=board_channel.id,
                        board_message_id=b_msg.id,
                        stars=stars,
                        boarded_at=b_msg.created_at.replace(tzinfo=None),
                        **post
                    ))
                    bs.sync_legacy_board(orig_msg_id, stars, b_msg.id, author_id)
                    if voter_ids is not None:
                        bs.replace_stars(orig_msg_id, voter_ids)

                    counters["synced"] += 1
                    if counters["synced"] % 20 == 0:
                        await progress(f"🔄 Sincronizzati {counters['synced']} messaggi...")

                # Post nel DB che non esistono più nel canale board -> inattivi
                removed = 0
                for orig_id, board_id in bs.get_active_board_ids(guild.id):
                    if board_id not in seen_board_ids:
                        bs.deactivate_post(orig_id)
                        removed += 1

                summary = (
                    f"✅ **Sync completato!**\n"
                    f"• Messaggi letti nella board: **{counters['scanned']}**\n"
                    f"• Sincronizzati: **{counters['synced']}**\n"
                    f"• Originali cancellati (salvati dal backup dell'embed): **{counters['orig_deleted']}**\n"
                    f"• Segnati come rimossi dalla board: **{removed}**\n"
                    f"• Ignorati (senza link): **{counters['skipped']}**"
                )
                logger.info(f"Hall of Shame sync done: {counters}, removed={removed}")
                try:
                    await interaction.edit_original_response(content=summary)
                except discord.HTTPException:
                    await interaction.channel.send(f"{interaction.user.mention}\n{summary}")

        # ------------------------------------------------------------------
        # COMANDI (tutti letti dal DB, nessun fetch_message)
        # ------------------------------------------------------------------
        @app_commands.command(name="leaderboard",
                              description="Mostra la top 10 dei messaggi con più reazioni nel server.")
        async def leaderboard(self, interaction: discord.Interaction):
            posts = self.board_system.get_top_posts(interaction.guild_id, limit=10)
            if not posts:
                await interaction.response.send_message(
                    "Nessun messaggio trovato nella board! (Se è la prima volta, usa `/shame sync`)",
                    ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title="🏆 Hall of Shame - Leaderboard",
                description="I 10 messaggi più leggendari (o imbarazzanti) del server!",
                colour=discord.Color.gold(),
                interaction=interaction
            )
            for idx, post in enumerate(posts, 1):
                embed.add_field(
                    name=f"#{idx} - {post['author_name'] or 'Utente Sconosciuto'} (⭐ {post['stars']})",
                    value=f"{snippet(post['content'])}\n[Vai al messaggio]({jump(post)})",
                    inline=False
                )
            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="user_posts",
                              description="Mostra tutti i messaggi di un utente nella Hall of Shame.")
        @app_commands.describe(member="L'utente di cui vedere i messaggi (lascia vuoto per te)")
        async def user_posts(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            posts = self.board_system.get_user_posts(interaction.guild_id, target.id)
            if not posts:
                await interaction.response.send_message(
                    f"Al momento {target.mention} non ha nessun messaggio nella Hall of Shame.",
                    ephemeral=True)
                return

            view = UserShamePagination(target, posts, per_page=5)
            await interaction.response.send_message(embed=view.create_embed(), view=view)

        @app_commands.command(name="top", description="Mostra il messaggio in assoluto più da moid/foid del server.")
        async def top_message(self, interaction: discord.Interaction):
            posts = self.board_system.get_top_posts(interaction.guild_id, limit=1)
            if not posts:
                await interaction.response.send_message("Nessun messaggio trovato nella board!", ephemeral=True)
                return

            best = posts[0]
            embed = EmbedFactory.create_embed(
                title=f"👑 Il Chud finale (⭐ {best['stars']})",
                description=f"{best['content'] or ''}\n\n**[Vai al messaggio]({jump(best)})**",
                colour=discord.Color.gold(),
                interaction=interaction
            )
            if best["author_name"]:
                embed.set_author(name=best["author_name"], icon_url=best["author_avatar"])
            if best["image_url"]:
                embed.set_image(url=best["image_url"])

            await interaction.response.send_message(
                content="Moid e foid, il livello più basso in assoluto di questo server:", embed=embed)

        @app_commands.command(name="stats", description="Mostra statistiche sulla Hall of Shame.")
        async def stats(self, interaction: discord.Interaction):
            s = self.board_system.get_guild_stats(interaction.guild_id)
            total_posts = s["total_posts"]
            avg_stars = round(s["total_stars"] / total_posts, 1) if total_posts else 0

            embed = EmbedFactory.create_embed(
                title="📊 Statistiche Hall of Shame",
                description="Ecco i numeri generati dai vostri messaggi.",
                colour=discord.Color.blurple(),
                interaction=interaction
            )
            embed.add_field(name="Messaggi nella hall of shame", value=f"**{total_posts}**", inline=True)
            embed.add_field(name="Stelle Totali Assegnate", value=f"**{s['total_stars']}** ⭐", inline=True)
            embed.add_field(name="Media Stelle per Post", value=f"**{avg_stars}** ⭐", inline=True)
            embed.add_field(name="Autori diversi", value=f"**{s['unique_authors']}**", inline=True)
            embed.add_field(name="Post negli ultimi 7 giorni", value=f"**{s['posts_last_7d']}**", inline=True)
            embed.add_field(name="Record Assoluto", value=f"**{s['max_stars']}** ⭐ su un singolo post",
                            inline=False)

            givers = self.board_system.get_top_givers(interaction.guild_id, limit=1)
            if givers:
                embed.add_field(name="Il più generoso di stelle",
                                value=f"<@{givers[0]['user_id']}> ({givers[0]['stars_given']} ⭐ date)",
                                inline=False)

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="user_leaderboard",
                              description="Mostra la top 10 degli utenti con più stelle totali.")
        async def user_leaderboard(self, interaction: discord.Interaction):
            rows = self.board_system.get_author_ranking(interaction.guild_id, limit=10)
            if not rows:
                await interaction.response.send_message("Nessun utente trovato! (Usa `/shame sync` prima)",
                                                        ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title="🏅 Hall of Shame - Classifica Utenti",
                description="I 10 membri del server che hanno accumulato più disagio in assoluto!",
                colour=discord.Color.brand_red(),
                interaction=interaction
            )
            for idx, row in enumerate(rows, 1):
                member = interaction.guild.get_member(row["author_id"])
                name = member.display_name if member else (row["author_name"] or f"Sconosciuto ({row['author_id']})")
                media = round(row["total_stars"] / row["total_posts"], 1)
                embed.add_field(
                    name=f"#{idx} - {name}",
                    value=f"**{row['total_stars']}** ⭐ totali su **{row['total_posts']}** messaggi (Media: {media} ⭐)",
                    inline=False
                )
            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="user",
                              description="Mostra le statistiche della Hall of Shame per te o per un altro utente.")
        @app_commands.describe(member="Il giocatore di cui vedere le statistiche (lascia vuoto per le tue)")
        async def user_stats(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            posts = self.board_system.get_user_posts(interaction.guild_id, target.id)  # già ordinati per stelle
            if not posts:
                await interaction.response.send_message(
                    f"Al momento {target.mention} non ha nessun messaggio nella Hall of Shame.", ephemeral=True)
                return

            ranking = self.board_system.get_author_ranking(interaction.guild_id)
            position = next((i for i, r in enumerate(ranking, 1) if r["author_id"] == target.id), 0)

            total_stars = sum(p["stars"] for p in posts)
            avg_stars = round(total_stars / len(posts), 1)
            best = posts[0]

            embed = EmbedFactory.create_embed(
                title=f"🎭 Statistiche Hall of Shame: {target.display_name}",
                description=f"Il contributo di {target.mention} al disagio del server.",
                colour=discord.Color.purple(),
                thumbnail=target.display_avatar.url,
                interaction=interaction
            )
            embed.add_field(name="Posizione Server", value=f"**#{position}** su {len(ranking)} utenti", inline=False)
            embed.add_field(name="Post nella Board", value=f"**{len(posts)}**", inline=True)
            embed.add_field(name="Stelle Totali", value=f"**{total_stars}** ⭐", inline=True)
            embed.add_field(name="Media Stelle", value=f"**{avg_stars}** ⭐", inline=True)
            embed.add_field(
                name=f"🌟 Miglior Messaggio (⭐ {best['stars']})",
                value=f"{snippet(best['content'], 50)}\n**[Vai al messaggio]({jump(best)})**",
                inline=False
            )
            await interaction.response.send_message(embed=embed)