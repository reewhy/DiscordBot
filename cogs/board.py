import discord
from discord.ext import commands
from discord import app_commands
import os
import re

from config import GUILD_ID
from utils.debug import Logger
from utils.embed_factory import EmbedFactory
from utils.board_system import BoardSystem

logger = Logger(os.path.basename(__file__).replace(".py", ""))


class UserShamePagination(discord.ui.View):
    def __init__(self, target: discord.Member, messages: list, per_page: int = 5):
        super().__init__(timeout=180)
        self.target = target
        self.messages = messages
        self.per_page = per_page
        self.current_page = 0
        self.max_pages = max(1, (len(messages) + per_page - 1) // per_page)
        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1

    def create_embed(self):
        embed = EmbedFactory.create_embed(
            title=f"📜 I messaggi di {self.target.display_name}",
            description=f"Pagina {self.current_page + 1} di {self.max_pages} (Totale: {len(self.messages)})",
            colour=discord.Color.purple()
        )

        avatar_url = self.target.avatar.url if self.target.avatar else self.target.default_avatar.url
        embed.set_thumbnail(url=avatar_url)

        start = self.current_page * self.per_page
        end = start + self.per_page
        page_messages = self.messages[start:end]

        for idx, (b_msg, reactions) in enumerate(page_messages, start + 1):
            desc = b_msg.embeds[0].description if b_msg.embeds else ""

            match = re.search(r'\((https://discord\.com/channels/[^\)]+)\)', desc)
            jump_url = match.group(1) if match else b_msg.jump_url

            clean_desc = desc.split("**[Jump to message!]")[0].strip()
            if not clean_desc:
                text_snippet = "*[Solo Immagine/Allegato]*"
            else:
                text_snippet = (clean_desc[:60] + "...") if len(clean_desc) > 60 else clean_desc

            embed.add_field(
                name=f"#{idx} - (⭐ {reactions})",
                value=f"{text_snippet}\n**[Vai al messaggio]({jump_url})**",
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

        # --- COMMAND TO FIX OLD MESSAGES (STAFF ONLY) ---
        @app_commands.command(name="fix_database",
                              description="[STAFF] Associa gli ID utente ai vecchi messaggi della board.")
        @app_commands.checks.has_permissions(administrator=True)
        async def fix_database(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            board_channel_id = self.board_system.get_board_channel(interaction.guild_id)
            board_channel = interaction.guild.get_channel(board_channel_id) or await interaction.guild.fetch_channel(
                board_channel_id)

            cursor = self.board_system.get_cursor(buffered=True)

            # Make sure column exists before migrating
            try:
                cursor.execute("ALTER TABLE board ADD COLUMN author_id BIGINT")
                self.board_system.conn.commit()
            except:
                pass

            updated = 0
            await interaction.followup.send("Inizio migrazione del database... Potrebbe volerci qualche secondo.",
                                            ephemeral=True)

            async for b_msg in board_channel.history(limit=None):
                if b_msg.embeds:
                    desc = b_msg.embeds[0].description if b_msg.embeds[0].description else ""

                    match = re.search(r'channels/\d+/(\d+)/(\d+)', desc)
                    if match:
                        channel_id = int(match.group(1))
                        msg_id = int(match.group(2))

                        try:
                            orig_channel = interaction.guild.get_channel(
                                channel_id) or await interaction.guild.fetch_channel(channel_id)
                            orig_msg = await orig_channel.fetch_message(msg_id)
                            author_id = orig_msg.author.id

                            cursor.execute("UPDATE board SET author_id = %s WHERE boarded = %s", (author_id, b_msg.id))
                            updated += 1
                        except Exception:
                            pass  # Message deleted or inaccessible

            self.board_system.conn.commit()
            cursor.close()

            await interaction.edit_original_response(
                content=f"✅ Migrazione completata! Ho aggiornato **{updated}** vecchi messaggi con i corretti ID utente.")

        async def get_top_messages(self, interaction: discord.Interaction, limit: int = 10):
            board_channel_id = self.board_system.get_board_channel(interaction.guild_id)
            if not board_channel_id:
                return None, "Canale board non configurato. Usa /setboard."

            board_channel = interaction.guild.get_channel(board_channel_id) or await interaction.guild.fetch_channel(
                board_channel_id)
            if not board_channel:
                return None, "Impossibile trovare il canale board."

            cursor = self.board_system.get_cursor(buffered=True)
            cursor.execute("""
                           SELECT message_id, reactions, boarded
                           FROM board
                           WHERE boarded != 0
                           ORDER BY reactions DESC
                               LIMIT %s
                           """, (limit,))
            rows = cursor.fetchall()
            cursor.close()

            top_messages = []
            for row in rows:
                orig_msg_id, reactions, boarded_id = row
                try:
                    b_msg = await board_channel.fetch_message(boarded_id)
                    top_messages.append((b_msg, reactions))
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    logger.warning(f"Boarded message {boarded_id} non trovato.")
                    continue

            return top_messages, None

        @app_commands.command(name="leaderboard",
                              description="Mostra la top 10 dei messaggi con più reazioni nel server.")
        async def leaderboard(self, interaction: discord.Interaction):
            await interaction.response.defer()

            top_messages, error = await self.get_top_messages(interaction, limit=10)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            if not top_messages:
                await interaction.followup.send("Nessun messaggio trovato nella board!", ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title="🏆 Hall of Shame - Leaderboard",
                description="I 10 messaggi più leggendari (o imbarazzanti) del server!",
                colour=discord.Color.gold(),
                interaction=interaction
            )

            for idx, (b_msg, reactions) in enumerate(top_messages, 1):
                original_embed = b_msg.embeds[0] if b_msg.embeds else None
                author_name = original_embed.author.name if original_embed and original_embed.author else "Utente Sconosciuto"
                desc = original_embed.description if original_embed else ""

                match = re.search(r'\((https://discord\.com/channels/[^\)]+)\)', desc)
                jump_url = match.group(1) if match else b_msg.jump_url

                clean_desc = desc.split("**[Jump to message!]")[0].strip()

                if not clean_desc:
                    text_snippet = "*[Solo Immagine/Allegato]*"
                else:
                    text_snippet = (clean_desc[:60] + "...") if len(clean_desc) > 60 else clean_desc

                embed.add_field(
                    name=f"#{idx} - {author_name} (⭐ {reactions})",
                    value=f"{text_snippet}\n[Vai al messaggio]({jump_url})",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        @app_commands.command(name="user_posts",
                              description="Mostra tutti i messaggi di un utente nella Hall of Shame.")
        @app_commands.describe(member="L'utente di cui vedere i messaggi (lascia vuoto per te)")
        async def user_posts(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            await interaction.response.defer()

            board_channel_id = self.board_system.get_board_channel(interaction.guild_id)
            if not board_channel_id:
                await interaction.followup.send("Canale board non configurato.", ephemeral=True)
                return

            board_channel = interaction.guild.get_channel(board_channel_id) or await interaction.guild.fetch_channel(
                board_channel_id)

            # Query SQL diretta usando author_id
            cursor = self.board_system.get_cursor(buffered=True)
            cursor.execute(
                "SELECT boarded, reactions FROM board WHERE author_id = %s AND boarded != 0 ORDER BY reactions DESC",
                (target.id,))
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                await interaction.followup.send(
                    f"Al momento {target.mention} non ha nessun messaggio nella Hall of Shame. (Se hai aggiornato ora il bot, usa prima `/shame fix_database`)",
                    ephemeral=True)
                return

            user_messages_list = []
            for row in rows:
                boarded_id, reactions = row
                try:
                    b_msg = await board_channel.fetch_message(boarded_id)
                    user_messages_list.append((b_msg, reactions))
                except:
                    continue

            view = UserShamePagination(target, user_messages_list, per_page=5)
            embed = view.create_embed()

            await interaction.followup.send(embed=embed, view=view)

        @app_commands.command(name="top", description="Mostra il messaggio in assoluto più da moid/foid del server.")
        async def top_message(self, interaction: discord.Interaction):
            await interaction.response.defer()

            top_messages, error = await self.get_top_messages(interaction, limit=1)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return

            if not top_messages:
                await interaction.followup.send("Nessun messaggio trovato nella board!", ephemeral=True)
                return

            best_msg, reactions = top_messages[0]
            original_embed = best_msg.embeds[0] if best_msg.embeds else None

            embed = EmbedFactory.create_embed(
                title=f"👑 Il Chud finale (⭐ {reactions})",
                description=original_embed.description if original_embed else best_msg.content,
                colour=discord.Color.gold(),
                interaction=interaction
            )

            if original_embed:
                if original_embed.author:
                    embed.set_author(name=original_embed.author.name, icon_url=original_embed.author.icon_url)
                if original_embed.image:
                    embed.set_image(url=original_embed.image.url)

            await interaction.followup.send(content="Moid e foid, il livello più basso in assoluto di questo server:",
                                            embed=embed)

        @app_commands.command(name="stats", description="Mostra statistiche sulla Hall of Shame.")
        async def stats(self, interaction: discord.Interaction):
            cursor = self.board_system.get_cursor(buffered=True)

            cursor.execute("SELECT COUNT(*), SUM(reactions), MAX(reactions) FROM board WHERE boarded != 0")
            row = cursor.fetchone()
            cursor.close()

            total_boarded = row[0] or 0
            total_stars = int(row[1]) if row[1] else 0
            max_stars = row[2] or 0

            avg_stars = round(total_stars / total_boarded, 1) if total_boarded > 0 else 0

            embed = EmbedFactory.create_embed(
                title="📊 Statistiche Hall of Shame",
                description="Ecco i numeri generati dai vostri messaggi.",
                colour=discord.Color.blurple(),
                interaction=interaction
            )

            embed.add_field(name="Messaggi nella hall of shame", value=f"**{total_boarded}**", inline=True)
            embed.add_field(name="Stelle Totali Assegnate", value=f"**{total_stars}** ⭐", inline=True)
            embed.add_field(name="Media Stelle per Post", value=f"**{avg_stars}** ⭐", inline=True)
            embed.add_field(name="Record Assoluto", value=f"**{max_stars}** ⭐ su un singolo post", inline=False)

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="user_leaderboard",
                              description="Mostra la top 10 degli utenti con più stelle totali.")
        async def user_leaderboard(self, interaction: discord.Interaction):
            await interaction.response.defer()

            # Completamente gestito da SQL ora!
            cursor = self.board_system.get_cursor(buffered=True)
            cursor.execute("""
                           SELECT author_id, SUM(reactions), COUNT(message_id)
                           FROM board
                           WHERE boarded != 0 AND author_id IS NOT NULL
                           GROUP BY author_id
                           ORDER BY SUM (reactions) DESC
                               LIMIT 10
                           """)
            rows = cursor.fetchall()
            cursor.close()

            if not rows:
                await interaction.followup.send("Nessun utente trovato! (Usa `/shame fix_database` prima)",
                                                ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title="🏅 Hall of Shame - Classifica Utenti",
                description="I 10 membri del server che hanno accumulato più disagio in assoluto!",
                colour=discord.Color.brand_red(),
                interaction=interaction
            )

            for idx, row in enumerate(rows, 1):
                author_id, total_stars, posts = row
                total_stars = int(total_stars)
                member = interaction.guild.get_member(author_id)
                name = member.display_name if member else f"Sconosciuto ({author_id})"

                media = round(total_stars / posts, 1)
                embed.add_field(
                    name=f"#{idx} - {name}",
                    value=f"**{total_stars}** ⭐ totali su **{posts}** messaggi (Media: {media} ⭐)",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

        @app_commands.command(name="user",
                              description="Mostra le statistiche della Hall of Shame per te o per un altro utente.")
        @app_commands.describe(member="Il giocatore di cui vedere le statistiche (lascia vuoto per le tue)")
        async def user_stats(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            await interaction.response.defer()

            board_channel_id = self.board_system.get_board_channel(interaction.guild_id)
            if not board_channel_id:
                await interaction.followup.send("Canale board non configurato.", ephemeral=True)
                return

            board_channel = interaction.guild.get_channel(board_channel_id) or await interaction.guild.fetch_channel(
                board_channel_id)

            cursor = self.board_system.get_cursor(buffered=True)

            # Calcola la posizione
            cursor.execute("""
                           SELECT author_id, SUM(reactions) as total
                           FROM board
                           WHERE boarded != 0 AND author_id IS NOT NULL
                           GROUP BY author_id
                           ORDER BY total DESC
                           """)
            leaderboard = cursor.fetchall()

            position = 0
            for idx, row in enumerate(leaderboard, 1):
                if row[0] == target.id:
                    position = idx
                    break

            # Prendi i post dell'utente
            cursor.execute("SELECT reactions, boarded FROM board WHERE author_id = %s AND boarded != 0", (target.id,))
            user_posts = cursor.fetchall()
            cursor.close()

            target_boarded_count = len(user_posts)
            if target_boarded_count == 0:
                await interaction.followup.send(
                    f"Al momento {target.mention} non ha nessun messaggio nella Hall of Shame.", ephemeral=True)
                return

            target_stars = sum(row[0] for row in user_posts)
            avg_stars = round(target_stars / target_boarded_count, 1)

            # Trova il messaggio top
            best_post = max(user_posts, key=lambda x: x[0])
            target_max_stars = best_post[0]
            best_boarded_id = best_post[1]

            target_best_msg = None
            try:
                target_best_msg = await board_channel.fetch_message(best_boarded_id)
            except:
                pass

            avatar_url = target.avatar.url if target.avatar else target.default_avatar.url

            embed_stats = EmbedFactory.create_embed(
                title=f"🎭 Statistiche Hall of Shame: {target.display_name}",
                description=f"Il contributo di {target.mention} al disagio del server.",
                colour=discord.Color.purple(),
                thumbnail=avatar_url,
                interaction=interaction
            )

            embed_stats.add_field(name="Posizione Server", value=f"**#{position}** su {len(leaderboard)} utenti",
                                  inline=False)
            embed_stats.add_field(name="Post nella Board", value=f"**{target_boarded_count}**", inline=True)
            embed_stats.add_field(name="Stelle Totali", value=f"**{target_stars}** ⭐", inline=True)
            embed_stats.add_field(name="Media Stelle", value=f"**{avg_stars}** ⭐", inline=True)

            if target_best_msg and target_best_msg.embeds:
                desc = target_best_msg.embeds[0].description if target_best_msg.embeds[0].description else ""
                match = re.search(r'\((https://discord\.com/channels/[^\)]+)\)', desc)
                jump_url = match.group(1) if match else target_best_msg.jump_url

                clean_desc = desc.split("**[Jump to message!]")[0].strip()
                if not clean_desc:
                    text_snippet = "*[Solo Immagine/Allegato]*"
                else:
                    text_snippet = (clean_desc[:50] + "...") if len(clean_desc) > 50 else clean_desc

                embed_stats.add_field(
                    name=f"🌟 Miglior Messaggio (⭐ {target_max_stars})",
                    value=f"{text_snippet}\n**[Vai al messaggio]({jump_url})**",
                    inline=False
                )

            await interaction.followup.send(embed=embed_stats)