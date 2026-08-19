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

        @app_commands.command(name="matches", description="Mostra lo storico delle partite di un giocatore.")
        @app_commands.describe(member="Il giocatore di cui vedere le partite (lascia vuoto per le tue)")
        async def matches(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user

            # Controlla prima se è iscritto
            score = self.chess_system.get_score(target.id)
            if score is None:
                await interaction.response.send_message(f"⚠️ {target.mention} non è iscritto al torneo.",
                                                        ephemeral=True)
                return

            player_matches = self.chess_system.get_player_matches(target.id)

            if not player_matches["active"] and not player_matches["past"]:
                await interaction.response.send_message(
                    f"{target.mention} non ha ancora giocato o ricevuto nessuna partita.", ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title=f"Storico Partite di {target.display_name}",
                description=f"Punteggio attuale: **{score}** punti",
                colour=discord.Color.blue(),
                thumbnail=target.avatar.url,
                interaction=interaction
            )

            # --- PARTITE ATTIVE ---
            if player_matches["active"]:
                active_text = ""
                for m in player_matches["active"]:
                    state = "⏳ In attesa di conferma" if m['status'] == 'PENDING' else "⚔️ In corso"
                    active_text += f"**Match #{m['match_id']}** contro <@{m['opponent_id']}> ({state})\n"

                embed.add_field(name="Prossime Partite", value=active_text, inline=False)

            # --- PARTITE PASSATE ---
            if player_matches["past"]:
                past_text = ""
                # Mostriamo solo le ultime 10 per non sforare i limiti di testo di Discord
                for m in player_matches["past"][:10]:
                    if m['status'] == 'CANCELLED':
                        res = "❌ Annullata"
                    elif m['status'] == 'FINISHED':
                        if m['winner_id'] == target.id:
                            res = "🏆 Vinta"
                        elif m['winner_id'] is not None:
                            res = "💀 Persa"
                        else:
                            res = "🤝 Pareggio"  # Se è FINISHED ma non c'è winner, è un pareggio

                    past_text += f"**Match #{m['match_id']}** contro <@{m['opponent_id']}>: {res}\n"

                if len(player_matches["past"]) > 10:
                    past_text += f"\n*...e altre {len(player_matches['past']) - 10} partite meno recenti.*"

                embed.add_field(name="Partite Concluse", value=past_text, inline=False)

            await interaction.response.send_message(embed=embed)

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

        @app_commands.command(name="drop_chess", description="Elimina le tables")
        @app_commands.checks.has_role(1539463835931377765)
        async def drop_chess(self, interaction: discord.Interaction):
            self.chess_system.drop_tables()

        @app_commands.command(name="create_match", description="Crea un match.")
        @app_commands.describe(player1="Primo player", player2="Secondo player")
        @app_commands.checks.has_role(1539471475885482065)
        async def create_match(self, interaction: discord.Interaction, player1: discord.Member, player2: discord.Member):
            await interaction.response.defer(ephemeral=True)

            self.chess_system.sign_up(player1.id)
            self.chess_system.sign_up(player2.id)

            await interaction.followup.send(f"Generazione match in corso...")

            match_id = self.chess_system.new_match(player1.id, player2.id)

            p1 = interaction.guild.get_member(player1.id)
            p2 = interaction.guild.get_member(player2.id)

            if p1 and p2:
                embed = EmbedFactory.create_embed(
                    title=f"Match #{match_id}",
                    description=f"{p1.mention} vs {p2.mention}\n\n*Avete tempo fino a stasera per cliccare 'Accetta Partita' e accordarvi. Chi non accetta subirà -1 punto di penalità.*",
                    colour=discord.Color.dark_theme(),
                    interaction=interaction
                )

                view = MatchAcceptView(self.chess_system, match_id, p1, p2)
                await interaction.channel.send(content=f"{p1.mention} {p2.mention}", embed=embed, view=view)

        @app_commands.command(name="generate_round",
                              description="Crea e pubblica i match in un canale specifico (Solo Staff).")
        @app_commands.describe(channel="Il canale dove pubblicare i match")
        @app_commands.checks.has_role(1539471475885482065)
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
        @app_commands.checks.has_role(1539471475885482065)
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
        @app_commands.checks.has_role(1539471475885482065)
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

        @app_commands.command(name="resolve_match",
                              description="Risolve forzatamente una disputa in un match (Solo Staff).")
        @app_commands.describe(match_id="L'ID del match", winner="Il giocatore che ha vinto (lascia vuoto se pareggio)",
                               is_draw="Imposta a True se è un pareggio")
        @app_commands.checks.has_role(1539471475885482065)
        async def resolve_match(self, interaction: discord.Interaction, match_id: int, winner: discord.Member = None,
                                is_draw: bool = False):
            # Valida l'input: non puoi avere sia un vincitore che un pareggio, ma devi avere almeno uno dei due
            if not winner and not is_draw:
                await interaction.response.send_message(
                    "Devi specificare un vincitore oppure impostare `is_draw` a True.", ephemeral=True)
                return

            if winner and is_draw:
                await interaction.response.send_message(
                    "Non puoi specificare sia un vincitore che un pareggio allo stesso tempo.", ephemeral=True)
                return

            winner_id = winner.id if winner else None

            # Esegue l'azione nel database
            success, message = self.chess_system.force_resolve_match(match_id, winner_id, is_draw)

            if success:
                esito = "🤝 Pareggio" if is_draw else f"🏆 Vittoria per {winner.mention}"

                embed = EmbedFactory.create_embed(
                    title=f"Match #{match_id} Risolto",
                    description=f"Il match è stato risolto forzatamente dallo staff.\n\n**Esito:** {esito}\n*I punteggi sono stati aggiornati di conseguenza.*",
                    colour=discord.Color.green(),
                    interaction=interaction
                )
                await interaction.response.send_message(embed=embed)
            else:
                embed = EmbedFactory.create_embed(
                    title="Errore di Risoluzione",
                    description=message,
                    colour=discord.Color.red(),
                    interaction=interaction
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    pass