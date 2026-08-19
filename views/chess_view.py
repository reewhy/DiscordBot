import discord
from utils.chess_db import ChessSystem


class MatchResultView(discord.ui.View):
    """Fase 2: I giocatori inseriscono il risultato."""

    def __init__(self, chess_system: ChessSystem, match_id: int, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=None)
        self.chess_system = chess_system
        self.match_id = match_id
        self.p1 = p1
        self.p2 = p2

    async def handle_result(self, interaction: discord.Interaction, result: str):
        if interaction.user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("Non fai parte di questo match!", ephemeral=True)
            return

        status_data = self.chess_system.report_result(self.match_id, interaction.user.id, result)
        status = status_data[0]

        if status == "RESOLVED":
            winner = status_data[1]
            if winner == "DRAW":
                msg = f"🤝 **Partita #{self.match_id} Conclusa!**\nI giocatori hanno concordato un pareggio."
            else:
                msg = f"✅ **Partita #{self.match_id} Conclusa!**\nVincitore confermato: <@{winner}>. Punteggio aggiornato."

            # Disable buttons and edit message
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content=msg, view=self)

        elif status == "DISPUTE":
            msg = f"⚠️ **Disputa nel Match #{self.match_id}!**\nI risultati inseriti non coincidono. Contattate uno staffer."
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(content=msg, view=self)
        else:
            await interaction.response.send_message(f"Hai segnalato: **{result}**. In attesa dell'avversario...",
                                                    ephemeral=True)

    @discord.ui.button(label="Ho Vinto", style=discord.ButtonStyle.success, emoji="🏆")
    async def btn_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_result(interaction, "WIN")

    @discord.ui.button(label="Ho Perso", style=discord.ButtonStyle.danger, emoji="💀")
    async def btn_loss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_result(interaction, "LOSS")

    @discord.ui.button(label="Pareggio", style=discord.ButtonStyle.secondary, emoji="🤝")
    async def btn_draw(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_result(interaction, "DRAW")


class MatchAcceptView(discord.ui.View):
    """Fase 1: I giocatori accettano la partita."""

    def __init__(self, chess_system: ChessSystem, match_id: int, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=None)
        self.chess_system = chess_system
        self.match_id = match_id
        self.p1 = p1
        self.p2 = p2
        self.accepted_users = set()

    @discord.ui.button(label="Accetta Partita", style=discord.ButtonStyle.primary, emoji="✅")
    async def btn_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("Non sei uno dei giocatori di questa partita!", ephemeral=True)
            return

        if interaction.user.id in self.accepted_users:
            await interaction.response.send_message("Hai già accettato questa partita.", ephemeral=True)
            return

        # Register in DB
        both_ready = self.chess_system.confirm_availability(self.match_id, interaction.user.id)
        self.accepted_users.add(interaction.user.id)

        if both_ready:
            # Switch to Phase 2 (Result Reporting)
            new_view = MatchResultView(self.chess_system, self.match_id, self.p1, self.p2)
            await interaction.response.edit_message(
                content=f"⚔️ **Match #{self.match_id} INIZIATO!**\n{self.p1.mention} vs {self.p2.mention}\n\n*Entrambi i giocatori hanno accettato. Giocate la partita e dichiarate il risultato qui sotto.*",
                embed=None,
                view=new_view
            )
        else:
            await interaction.response.send_message(f"Hai accettato il match! In attesa del tuo avversario...",
                                                    ephemeral=True)