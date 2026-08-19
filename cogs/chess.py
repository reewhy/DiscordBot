import discord
from discord.ext import commands
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger
import os
import random

from utils.embed_factory import EmbedFactory
from utils.chess_db import ChessSystem
from views.chess_view import MatchAcceptView

logger = Logger(os.path.basename(__file__).replace(".py", ""))


class ChessEvent(commands.Cog):
    def __init__(self, bot, chess_system: ChessSystem):
        self.bot = bot
        self.chess_system = chess_system
        self.bot.tree.add_command(self.Chess(chess_system, bot))

    @app_commands.guilds(*GUILD_ID)
    class Chess(app_commands.Group):
        def __init__(self, chess_system: ChessSystem, bot: commands.Bot):
            super().__init__(name="chess", description="Comandi relativi al campionato di scacchi.")
            self.chess_system = chess_system
            self.bot = bot

        @app_commands.command(name="signup", description="Iscriviti all'evento di scacchi!")
        async def signup(self, interaction: discord.Interaction):
            self.chess_system.sign_up(interaction.user.id)
            embed = EmbedFactory.create_embed(
                title="Buona fortuna!",
                description="Ti sei ufficialmente iscritto a scacchilarp!",
                colour=discord.Colour.random(),
                interaction=interaction
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="profile", description="Mostra il profilo del giocatore.")
        async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
            score = self.chess_system.get_score(interaction.user.id if member == None else member.id)

            if score is not None:
                embed = EmbedFactory.create_embed(
                    title=interaction.user.name if member == None else member.name,
                    description=f"Score: **{score}** punti",
                    colour=discord.Colour.random(),
                    thumbnail=interaction.user.avatar.url if member == None else member.avatar.url,
                    interaction=interaction
                )
                await interaction.response.send_message(embed=embed)
            else:
                embed = EmbedFactory.create_embed(
                    title="Errore!",
                    description="Non sei ancora iscritto all'evento.\n\n___\n\n**Come iscriverti:**\nUsa `/chess signup`" if member == None else "L'utente non è iscritto all'evento",
                    colour=discord.Color.red(),
                    interaction=interaction,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        # --- STAFF COMMANDS ---

        @app_commands.command(name="generate_round",
                              description="Crea e pubblica i match in un canale specifico (Solo Staff).")
        @app_commands.describe(channel="Il canale dove pubblicare i match")
        @app_commands.checks.has_permissions(manage_messages=True)
        async def generate_round(self, interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)

            players = self.chess_system.get_all_players()

            if len(players) < 2:
                await interaction.followup.send("Non ci sono abbastanza giocatori iscritti per generare dei match.")
                return

            random.shuffle(players)

            bye_player = None
            if len(players) % 2 != 0:
                bye_player = players.pop()

            await interaction.followup.send(f"Generazione match in corso nel canale {channel.mention}...")

            # Pair and post matches directly to the channel
            for i in range(0, len(players), 2):
                p1_id = players[i]
                p2_id = players[i + 1]

                match_id = self.chess_system.new_match(p1_id, p2_id)

                # Fetch members to pass to the view
                p1 = interaction.guild.get_member(p1_id)
                p2 = interaction.guild.get_member(p2_id)

                if p1 and p2:
                    embed = EmbedFactory.create_embed(
                        title=f"Match #{match_id}",
                        description=f"{p1.mention} vs {p2.mention}\n\n*Avete tempo fino a stasera per cliccare 'Accetta Partita' e accordarvi. Chi non accetta subirà -1 punto di penalità.*",
                        colour=discord.Color.dark_theme(),
                        interaction=interaction
                    )

                    view = MatchAcceptView(self.chess_system, match_id, p1, p2)
                    await channel.send(content=f"{p1.mention} {p2.mention}", embed=embed, view=view)

            if bye_player:
                await channel.send(f"⏸️ <@{bye_player}> riposa in questo turno (numero dispari di giocatori).")

        @app_commands.command(name="close_day",
                              description="Chiude la giornata, penalizza chi non ha giocato e annulla i match (Solo Staff).")
        @app_commands.checks.has_permissions(manage_messages=True)
        async def close_day(self, interaction: discord.Interaction):
            penalized = self.chess_system.process_end_of_day_penalties()

            if penalized:
                mentions = " ".join([f"<@{pid}>" for pid in penalized])
                await interaction.response.send_message(f"✅ Giornata chiusa. Penalità applicate a: {mentions}")
            else:
                await interaction.response.send_message(
                    "✅ Giornata chiusa. Tutti i giocatori hanno confermato i loro match oggi!")

        @app_commands.command(name="force_signup",
                              description="Iscrive forzatamente un utente all'evento (Solo Staff).")
        @app_commands.describe(user="L'utente da iscrivere")
        @app_commands.checks.has_permissions(manage_messages=True)
        async def force_signup(self, interaction: discord.Interaction, user: discord.Member):
            # Calls the existing sign_up method using the target user's ID
            self.chess_system.sign_up(user.id)

            embed = EmbedFactory.create_embed(
                title="Iscrizione Forzata Completata",
                description=f"Hai iscritto con successo {user.mention} al campionato di scacchi!",
                colour=discord.Color.green(),
                interaction=interaction
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    pass