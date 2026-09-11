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

        async def get_top_messages(self, interaction: discord.Interaction, limit: int = 10):
            """Helper per ottenere i messaggi più stellati."""
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
                    logger.warning(f"Boarded message {boarded_id} non trovato. Probabilmente eliminato.")
                    continue

            return top_messages, None

        @app_commands.command(name="leaderboard",
                              description="Mostra la top 10 dei messaggi più chud del server.")
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
                title="🏆 Hall of Shame",
                description="I 10 messaggi più chud del server!",
                colour=discord.Color.gold(),
                interaction=interaction
            )

            for idx, (b_msg, reactions) in enumerate(top_messages, 1):
                original_embed = b_msg.embeds[0] if b_msg.embeds else None
                author_name = original_embed.author.name if original_embed and original_embed.author else "Utente Sconosciuto"

                desc = original_embed.description if original_embed else "Nessun testo..."

                match = re.search(r'\((https://discord\.com/channels/[^\)]+)\)', desc)
                jump_url = match.group(1) if match else b_msg.jump_url

                clean_desc = desc.split("\n\n**[Jump")[0]
                text_snippet = (clean_desc[:60] + "...") if len(clean_desc) > 60 else clean_desc
                if not text_snippet.strip():
                    text_snippet = "*[Immagine/Allegato]*"

                embed.add_field(
                    name=f"#{idx} - {author_name} (⭐ {reactions})",
                    value=f"\"{text_snippet}\"\n**[Vai al messaggio]({jump_url})**",
                    inline=False
                )

            await interaction.followup.send(embed=embed)

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

            # 1. Grab all active boarded messages and their reactions from the database
            cursor = self.board_system.get_cursor(buffered=True)
            cursor.execute("SELECT boarded, reactions FROM board WHERE boarded != 0")
            rows = cursor.fetchall()
            cursor.close()

            boarded_reactions = {row[0]: row[1] for row in rows}

            user_totals = {}  # Map to calculate leaderboard positions
            target_stars = 0
            target_boarded_count = 0
            target_best_msg = None
            target_max_stars = 0

            # 2. Iterate through the board channel's history to link embeds to users
            async for b_msg in board_channel.history(limit=None):
                if b_msg.id in boarded_reactions and b_msg.embeds:
                    reactions = boarded_reactions[b_msg.id]
                    embed = b_msg.embeds[0]

                    if embed.author and embed.author.name:
                        author_name = embed.author.name
                        # Tally total stars for global ranking
                        user_totals[author_name] = user_totals.get(author_name, 0) + reactions

                        # If this message belongs to our target user
                        if author_name == target.display_name:
                            target_boarded_count += 1
                            target_stars += reactions
                            if reactions > target_max_stars:
                                target_max_stars = reactions
                                target_best_msg = b_msg

            if target_boarded_count == 0:
                await interaction.followup.send(
                    f"Al momento {target.mention} non ha nessun messaggio nella Hall of Shame. Troppo poco divertente?",
                    ephemeral=True)
                return

            # 3. Calculate their position on the leaderboard
            sorted_users = sorted(user_totals.items(), key=lambda x: x[1], reverse=True)
            position = 0
            for idx, (name, total) in enumerate(sorted_users, 1):
                if name == target.display_name:
                    position = idx
                    break

            avg_stars = round(target_stars / target_boarded_count, 1)
            avatar_url = target.avatar.url if target.avatar else target.default_avatar.url

            embed_stats = EmbedFactory.create_embed(
                title=f"🎭 Statistiche Hall of Shame: {target.display_name}",
                description=f"Il contributo di {target.mention} al disagio del server.",
                colour=discord.Color.purple(),
                thumbnail=avatar_url,
                interaction=interaction
            )

            embed_stats.add_field(name="Posizione Server", value=f"**#{position}** su {len(user_totals)} utenti",
                                  inline=False)
            embed_stats.add_field(name="Post nella Board", value=f"**{target_boarded_count}**", inline=True)
            embed_stats.add_field(name="Stelle Totali", value=f"**{target_stars}** ⭐", inline=True)
            embed_stats.add_field(name="Media Stelle", value=f"**{avg_stars}** ⭐", inline=True)

            if target_best_msg:
                # Extract original jump link and text snippet
                desc = target_best_msg.embeds[0].description if target_best_msg.embeds else ""
                match = re.search(r'\((https://discord\.com/channels/[^\)]+)\)', desc)
                jump_url = match.group(1) if match else target_best_msg.jump_url

                clean_desc = desc.split("\n\n**[Jump")[0]
                text_snippet = (clean_desc[:50] + "...") if len(clean_desc) > 50 else clean_desc
                if not text_snippet.strip():
                    text_snippet = "*[Immagine/Allegato]*"

                embed_stats.add_field(
                    name=f"🌟 Miglior Messaggio (⭐ {target_max_stars})",
                    value=f"\"{text_snippet}\"\n**[Vai al messaggio]({jump_url})**",
                    inline=False
                )

            await interaction.followup.send(embed=embed_stats)