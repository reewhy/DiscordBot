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
            super().__init__(name="chess", description="Comandi relativi al campionato e torneo di scacchi.")
            self.chess_system = chess_system
            self.bot = bot

        # --- CHAMPIONSHIP USER COMMANDS ---
        @app_commands.command(name="signup", description="Iscriviti al CAMPIONATO (a punti) di scacchi!")
        async def signup(self, interaction: discord.Interaction):
            self.chess_system.sign_up(interaction.user.id)
            embed = EmbedFactory.create_embed(
                title="Buona fortuna!",
                description="Ti sei ufficialmente iscritto al Campionato di Scacchi Larp!",
                colour=discord.Colour.random(),
                interaction=interaction
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="matches", description="Mostra lo storico delle partite di un giocatore.")
        @app_commands.describe(member="Il giocatore di cui vedere le partite (lascia vuoto per le tue)")
        async def matches(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            score = self.chess_system.get_score(target.id)
            if score is None:
                await interaction.response.send_message(f"⚠️ {target.mention} non è registrato nel database scacchi.",
                                                        ephemeral=True)
                return

            player_matches = self.chess_system.get_player_matches(target.id)

            if not player_matches["active"] and not player_matches["past"]:
                await interaction.response.send_message(
                    f"{target.mention} non ha ancora giocato o ricevuto nessuna partita.", ephemeral=True)
                return

            embed = EmbedFactory.create_embed(
                title=f"Storico Partite di {target.display_name}",
                description=f"Punteggio Campionato: **{score}** punti",
                colour=discord.Color.blue(),
                thumbnail=target.avatar.url,
                interaction=interaction
            )

            if player_matches["active"]:
                active_text = ""
                for m in player_matches["active"]:
                    state = "⏳ In attesa" if m['status'] == 'PENDING' else "⚔️ In corso"
                    m_type = "🏆 Campionato" if m['type'] == 'CHAMPIONSHIP' else "⚔️ Torneo"
                    active_text += f"**Match #{m['match_id']}** ({m_type}) contro <@{m['opponent_id']}>: {state}\n"
                embed.add_field(name="Prossime Partite", value=active_text, inline=False)

            if player_matches["past"]:
                past_text = ""
                for m in player_matches["past"][:10]:
                    if m['status'] == 'CANCELLED':
                        res = "❌ Annullata"
                    elif m['status'] == 'FINISHED':
                        if m['winner_id'] == target.id:
                            res = "Vinta"
                        elif m['winner_id'] is not None:
                            res = "Persa"
                        else:
                            res = "Pareggio"
                    m_type = "🏆" if m['type'] == 'CHAMPIONSHIP' else "⚔️"
                    past_text += f"**#{m['match_id']}** {m_type} contro <@{m['opponent_id']}>: {res}\n"
                embed.add_field(name="Partite Concluse", value=past_text, inline=False)

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="profile", description="Mostra il profilo del giocatore.")
        async def profile(self, interaction: discord.Interaction, member: discord.Member = None):
            target = member or interaction.user
            score = self.chess_system.get_score(target.id)

            if score is not None:
                embed = EmbedFactory.create_embed(
                    title=target.name,
                    description=f"Score Campionato: **{score}** punti",
                    colour=discord.Colour.random(),
                    thumbnail=target.avatar.url,
                    interaction=interaction
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"L'utente non è iscritto all'evento. Usa `/chess signup`",
                                                        ephemeral=True)

        # --- TOURNAMENT USER COMMANDS ---
        @app_commands.command(name="tourney_signup", description="Iscriviti al TORNEO (eliminazione diretta)!")
        async def tourney_signup(self, interaction: discord.Interaction):
            self.chess_system.tourney_sign_up(interaction.user.id)
            embed = EmbedFactory.create_embed(
                title="Iscritto al Torneo!",
                description="Sei entrato ufficialmente nel bracket del torneo a eliminazione diretta. Prepara le tue strategie!",
                colour=discord.Color.gold(),
                interaction=interaction
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="tourney_status", description="Mostra i giocatori ancora attivi nel torneo.")
        async def tourney_status(self, interaction: discord.Interaction):
            active_players = self.chess_system.get_active_tourney_players()

            if not active_players:
                await interaction.response.send_message("Nessun giocatore è attualmente attivo nel torneo.",
                                                        ephemeral=True)
                return

            mentions = ", ".join([f"<@{pid}>" for pid in active_players])
            embed = EmbedFactory.create_embed(
                title="Giocatori Attivi nel Torneo",
                description=f"Ci sono **{len(active_players)}** giocatori ancora in gara:\n\n{mentions}",
                colour=discord.Color.orange(),
                interaction=interaction
            )
            await interaction.response.send_message(embed=embed)

        # --- STAFF COMMANDS ---
        @app_commands.command(name="drop_chess", description="Elimina le tables")
        @app_commands.checks.has_role(1539463835931377765)
        async def drop_chess(self, interaction: discord.Interaction):
            self.chess_system.drop_tables()
            await interaction.response.send_message("Database resettato.", ephemeral=True)

        @app_commands.command(name="create_match", description="Crea un match di CAMPIONATO manuale.")
        @app_commands.checks.has_role(1539471475885482065)
        async def create_match(self, interaction: discord.Interaction, player1: discord.Member,
                               player2: discord.Member):
            await interaction.response.defer(ephemeral=True)
            self.chess_system.sign_up(player1.id)
            self.chess_system.sign_up(player2.id)
            match_id = self.chess_system.new_match(player1.id, player2.id, match_type='CHAMPIONSHIP')

            embed = EmbedFactory.create_embed(
                title=f"Match Campionato #{match_id}",
                description=f"{player1.mention} vs {player2.mention}\n\n*Chi non accetta entro fine giornata riceverà -1 punto.*",
                colour=discord.Color.dark_theme(),
                interaction=interaction
            )
            view = MatchAcceptView(self.chess_system, match_id, player1, player2)
            await interaction.channel.send(content=f"{player1.mention} {player2.mention}", embed=embed, view=view)
            await interaction.followup.send("Match campionato creato con successo.")

        @app_commands.command(name="generate_round", description="Genera round CAMPIONATO (tutti i giocatori).")
        @app_commands.checks.has_role(1539471475885482065)
        async def generate_round(self, interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(ephemeral=True)
            players = self.chess_system.get_all_players()
            if len(players) < 2:
                await interaction.followup.send("Non ci sono abbastanza giocatori.")
                return

            random.shuffle(players)
            bye_player = players.pop() if len(players) % 2 != 0 else None

            for i in range(0, len(players), 2):
                p1, p2 = interaction.guild.get_member(players[i]), interaction.guild.get_member(players[i + 1])
                if p1 and p2:
                    match_id = self.chess_system.new_match(p1.id, p2.id, match_type='CHAMPIONSHIP')
                    embed = EmbedFactory.create_embed(
                        title=f"Match Campionato #{match_id}",
                        description=f"{p1.mention} vs {p2.mention}",
                        colour=discord.Color.dark_theme(),
                        interaction=interaction
                    )
                    view = MatchAcceptView(self.chess_system, match_id, p1, p2)
                    await channel.send(content=f"{p1.mention} {p2.mention}", embed=embed, view=view)

            if bye_player:
                await channel.send(f"⏸️ <@{bye_player}> riposa in questo turno di campionato.")
            await interaction.followup.send("Match generati.")

        @app_commands.command(name="tourney_generate", description="Genera match TORNEO (solo giocatori in gara).")
        @app_commands.checks.has_role(1539471475885482065)
        async def tourney_generate(self, interaction: discord.Interaction, channel: discord.TextChannel,
                                   round_name: str = "Eliminatorie"):
            await interaction.response.defer(ephemeral=True)
            active_players = self.chess_system.get_active_tourney_players()

            if len(active_players) < 2:
                await interaction.followup.send(
                    "Non ci sono abbastanza giocatori attivi per generare il torneo (serve un minimo di 2).")
                return

            random.shuffle(active_players)
            bye_player = active_players.pop() if len(active_players) % 2 != 0 else None

            await interaction.followup.send(f"Generazione bracket torneo in corso...")

            for i in range(0, len(active_players), 2):
                p1, p2 = interaction.guild.get_member(active_players[i]), interaction.guild.get_member(
                    active_players[i + 1])
                if p1 and p2:
                    match_id = self.chess_system.new_match(p1.id, p2.id, match_type='TOURNAMENT')
                    embed = EmbedFactory.create_embed(
                        title=f"⚔️ {round_name} | Match Torneo #{match_id}",
                        description=f"{p1.mention} vs {p2.mention}\n\n**ATTENZIONE:** Questo è un match a eliminazione diretta. Il perdente esce dal torneo. I pareggi devono essere risolti dallo staff.",
                        colour=discord.Color.brand_red(),
                        interaction=interaction
                    )
                    view = MatchAcceptView(self.chess_system, match_id, p1, p2)
                    await channel.send(content=f"{p1.mention} {p2.mention}", embed=embed, view=view)

            if bye_player:
                await channel.send(f"🍀 <@{bye_player}> avanza automaticamente al prossimo turno! (Bye)")

        @app_commands.command(name="close_day",
                              description="Chiude la giornata, annulla i match e applica le penalità.")
        @app_commands.checks.has_role(1539471475885482065)
        async def close_day(self, interaction: discord.Interaction):
            penalized = self.chess_system.process_end_of_day_penalties()
            if penalized:
                mentions = " ".join([f"<@{pid}>" for pid in penalized])
                await interaction.response.send_message(
                    f"✅ Giornata chiusa. Penalità o eliminazioni applicate a: {mentions}")
            else:
                await interaction.response.send_message("✅ Giornata chiusa senza ritardatari.")

        @app_commands.command(name="force_signup", description="Iscrive forzatamente un utente (Staff).")
        @app_commands.checks.has_role(1539471475885482065)
        async def force_signup(self, interaction: discord.Interaction, user: discord.Member, torneo: bool = False):
            if torneo:
                self.chess_system.tourney_sign_up(user.id)
                msg = f"Hai iscritto con successo {user.mention} al TORNEO!"
            else:
                self.chess_system.sign_up(user.id)
                msg = f"Hai iscritto con successo {user.mention} al CAMPIONATO!"

            embed = EmbedFactory.create_embed(
                title="Iscrizione Forzata", description=msg, colour=discord.Color.green(), interaction=interaction
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="resolve_match", description="Risolve forzatamente un match (Staff).")
        @app_commands.checks.has_role(1539471475885482065)
        async def resolve_match(self, interaction: discord.Interaction, match_id: int, winner: discord.Member = None,
                                is_draw: bool = False):
            if not winner and not is_draw:
                await interaction.response.send_message(
                    "Devi specificare un vincitore oppure impostare `is_draw` a True.", ephemeral=True)
                return
            if winner and is_draw:
                await interaction.response.send_message("Non puoi specificare sia un vincitore che un pareggio.",
                                                        ephemeral=True)
                return

            success, message = self.chess_system.force_resolve_match(match_id, winner.id if winner else None, is_draw)
            if success:
                esito = "🤝 Pareggio" if is_draw else f"🏆 Vittoria per {winner.mention}"
                embed = EmbedFactory.create_embed(
                    title=f"Match #{match_id} Risolto", description=f"Esito: {esito}", colour=discord.Color.green(),
                    interaction=interaction
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(message, ephemeral=True)


async def setup(bot):
    pass