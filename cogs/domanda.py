import datetime as dt
import os
import random
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import GUILD_ID
from utils.debug import Logger
from utils.domanda_system import DomandaSystem, utcnow

logger = Logger(os.path.basename(__file__).replace(".py", ""))

# ---------------------------------------------------------------------------
# Impostazioni
# ---------------------------------------------------------------------------
TZ = ZoneInfo("Europe/Rome")

STAFF_ROLE_ID = 1539463835931377765  # lo stesso ruolo usato nei comandi /channel

# La domanda esce il lunedì alle 09:00 e si chiude la domenica alle 20:00 (ora italiana)
START_WEEKDAY, START_HOUR = 5, 20
END_WEEKDAY, END_HOUR = 4, 20

MAX_PENDING_PER_USER = 3     # proposte in attesa contemporaneamente per utente
ALLOW_SELF_VOTE = False      # True = ci si può votare da soli

CHANNEL_KIND = "domande"             # chiave nella tabella `channels`
STAFF_CHANNEL_KIND = "domande_staff"

# Usate quando non ci sono domande approvate in coda
DEFAULT_QUESTIONS = [
    "Chi è più propenso a presentarsi in ritardo al proprio matrimonio?",
    "Chi è la mamma del gruppo?",
    "Chi è più propenso a sopravvivere a un'apocalisse zombie?",
    "Chi è più propenso a diventare famoso?",
    "Chi è più propenso a perdere il telefono ogni settimana?",
    "Chi è più propenso a restare sveglio fino alle 5 di mattina giocando?",
    "Chi è più propenso a sbagliare chat e scrivere alla persona sbagliata?",
    "Chi è più propenso a piangere guardando un film d'animazione?",
    "Chi è più propenso a litigare con l'arbitro in una partita tra amici?",
    "Chi è il più testardo del server?",
    "Chi è più propenso a trasferirsi all'estero da un giorno all'altro?",
    "Chi è più propenso a vincere alla lotteria e sperperare tutto in una settimana?",
    "Chi è il più simpatico del gruppo?",
    "Chi è più propenso a rispondere ai messaggi dopo tre giorni?",
    "Chi è più propenso a farsi un tatuaggio impulsivo?",
]


# ---------------------------------------------------------------------------
# Utilità di tempo
# ---------------------------------------------------------------------------
def to_naive_utc(local: dt.datetime) -> dt.datetime:
    return local.astimezone(dt.timezone.utc).replace(tzinfo=None)


def from_naive_utc(naive: dt.datetime) -> dt.datetime:
    return naive.replace(tzinfo=dt.timezone.utc)


def week_key(now_local: dt.datetime) -> str:
    iso = now_local.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def next_end(now_local: dt.datetime) -> dt.datetime:
    """Prossima scadenza (domenica 20:00) a partire da adesso."""
    days = (END_WEEKDAY - now_local.weekday()) % 7
    end = (now_local + dt.timedelta(days=days)).replace(
        hour=END_HOUR, minute=0, second=0, microsecond=0)
    if end <= now_local:
        end += dt.timedelta(days=7)
    return end


def start_is_due(now_local: dt.datetime) -> bool:
    """True se siamo nella finestra tra lunedì 09:00 e domenica 20:00."""
    cur = (now_local.weekday(), now_local.hour)
    return (START_WEEKDAY, START_HOUR) <= cur < (END_WEEKDAY, END_HOUR)


def is_staff(member) -> bool:
    return isinstance(member, discord.Member) and (
        member.guild_permissions.administrator
        or any(r.id == STAFF_ROLE_ID for r in member.roles)
    )


# ---------------------------------------------------------------------------
# View persistente: votazione (menu di selezione utenti sotto la domanda)
# ---------------------------------------------------------------------------
class DomandaVoteView(discord.ui.View):
    def __init__(self, system: DomandaSystem):
        super().__init__(timeout=None)
        self.system = system

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        custom_id="domanda:vote",
        placeholder="Scegli un membro...",
        min_values=1,
        max_values=1,
    )
    async def vote(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        week = self.system.get_week_by_message(interaction.message.id)
        if not week or week["status"] != "open" or week["ends_at"] <= utcnow():
            await interaction.response.send_message("⏰ La votazione è chiusa.", ephemeral=True)
            return

        target = select.values[0]
        if target.bot:
            await interaction.response.send_message("🤖 Non puoi votare un bot!", ephemeral=True)
            return
        if target.id == interaction.user.id and not ALLOW_SELF_VOTE:
            await interaction.response.send_message("😏 Non puoi votare te stesso!", ephemeral=True)
            return

        self.system.upsert_vote(week["id"], interaction.user.id, target.id)
        await interaction.response.send_message(
            f"✅ Hai votato {target.mention}. Puoi cambiare voto fino alla chiusura.",
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# View persistente: moderazione (bottoni nel canale staff)
# ---------------------------------------------------------------------------
class DomandaModerationView(discord.ui.View):
    def __init__(self, system: DomandaSystem):
        super().__init__(timeout=None)
        self.system = system

    async def _handle(self, interaction: discord.Interaction, new_status: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("Non hai i permessi per farlo.", ephemeral=True)
            return

        question = self.system.get_question_by_staff_message(interaction.message.id)
        if not question:
            await interaction.response.send_message("Domanda non trovata nel database.", ephemeral=True)
            return

        if not self.system.resolve_pending_question(question["id"], new_status):
            await interaction.response.send_message("Questa domanda è già stata gestita.", ephemeral=True)
            return

        approved = new_status == "approved"
        embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed()
        embed.colour = discord.Color.green() if approved else discord.Color.red()
        embed.title = f"Domanda #{question['id']} — {'APPROVATA ✅' if approved else 'RIFIUTATA ❌'}"
        embed.set_footer(text=f"{'Approvata' if approved else 'Rifiutata'} da {interaction.user.display_name}")
        await interaction.response.edit_message(embed=embed, view=None)

        # Avvisa l'autore in DM (se ha i DM chiusi, pazienza)
        try:
            author = await interaction.client.fetch_user(question["author_id"])
            if approved:
                msg = (f"✅ La tua domanda **{question['text']}** è stata approvata! "
                       "Uscirà presto come domanda della settimana.")
            else:
                msg = f"❌ La tua domanda **{question['text']}** non è stata approvata dallo staff."
            await author.send(msg)
        except (discord.Forbidden, discord.HTTPException):
            pass

        logger.info(f"Question {question['id']} {new_status} by {interaction.user.name}")

    @discord.ui.button(label="Approva", style=discord.ButtonStyle.success,
                       emoji="✅", custom_id="domanda:approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "approved")

    @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.danger,
                       emoji="❌", custom_id="domanda:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle(interaction, "rejected")


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------
class DomandaCog(commands.Cog):
    def __init__(self, bot, domanda_system: DomandaSystem):
        self.bot = bot
        self.system = domanda_system
        self.vote_view = DomandaVoteView(domanda_system)
        self.mod_view = DomandaModerationView(domanda_system)

    async def cog_load(self):
        # Registra le view persistenti (funzionano anche dopo un riavvio del bot)
        self.bot.add_view(self.vote_view)
        self.bot.add_view(self.mod_view)
        self.reconcile.start()

    async def cog_unload(self):
        self.reconcile.cancel()

    # -------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------
    async def _get_channel(self, guild: discord.Guild, channel_id):
        if not channel_id:
            return None
        try:
            return guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    # -------------------------------------------------------------------
    # Loop: ogni 5 minuti allinea lo stato (robusto ai riavvii del bot)
    #  - se c'è una settimana aperta scaduta  -> la chiude e pubblica il risultato
    #  - se non c'è nulla e siamo oltre lunedì 09:00 -> pubblica la nuova domanda
    # Il vincolo UNIQUE (guild_id, week_key) impedisce doppioni.
    # -------------------------------------------------------------------
    @tasks.loop(minutes=5)
    async def reconcile(self):
        for guild in self.bot.guilds:
            try:
                week = self.system.get_open_week(guild.id)
                if week:
                    if week["ends_at"] <= utcnow():
                        await self.close_week(guild, week)
                    continue

                now_local = dt.datetime.now(TZ)
                if (start_is_due(now_local)
                        and not self.system.week_exists(guild.id, week_key(now_local))
                        and self.system.get_channel(guild.id, CHANNEL_KIND)):
                    error = await self.start_week(guild, now_local)
                    if error:
                        logger.warning(f"Domanda settimanale non avviata in {guild.name}: {error}")
            except Exception as e:
                logger.error(f"Errore nel ciclo domande per la guild {guild.id}", exc_info=e)

    @reconcile.before_loop
    async def before_reconcile(self):
        await self.bot.wait_until_ready()

    # -------------------------------------------------------------------
    # Avvio settimana: pubblica la domanda. Ritorna None se ok, altrimenti un messaggio d'errore.
    # -------------------------------------------------------------------
    async def start_week(self, guild: discord.Guild, now_local: dt.datetime, forced: bool = False):
        channel = await self._get_channel(guild, self.system.get_channel(guild.id, CHANNEL_KIND))
        if not channel:
            return "Canale delle domande non configurato (usa `/channel domande`)."

        question = self.system.next_approved_question(guild.id)
        if question:
            q_id, text, author_id = question["id"], question["text"], question["author_id"]
        else:
            q_id, text, author_id = None, random.choice(DEFAULT_QUESTIONS), None

        ends_local = next_end(now_local)
        key = week_key(now_local)
        if forced:
            key += now_local.strftime("-F%d%H%M")  # chiave unica: l'avvio manuale ignora il vincolo settimanale
        week_id = self.system.create_week(
            guild.id, key, q_id, text, author_id, channel.id,
            to_naive_utc(now_local), to_naive_utc(ends_local),
        )
        if week_id is None:
            return "Per questa settimana esiste già una domanda."

        end_ts = int(ends_local.timestamp())
        embed = discord.Embed(
            title="🗳️ Domanda della settimana",
            description=f"## {text}",
            colour=discord.Color.blurple(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        embed.add_field(name="⏳ Si chiude", value=f"<t:{end_ts}:F> (<t:{end_ts}:R>)", inline=False)
        embed.set_footer(text="Vota col menu qui sotto • puoi cambiare voto fino alla chiusura • i voti sono segreti")

        try:
            msg = await channel.send(
                embed=embed, view=self.vote_view,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as e:
            self.system.delete_week(week_id)  # così il ciclo riprova al giro dopo
            logger.error(f"Impossibile pubblicare la domanda in {channel.id}: {e}")
            return "Non riesco a scrivere nel canale delle domande (controlla i permessi del bot)."

        self.system.set_week_message(week_id, msg.id)
        if q_id:
            self.system.mark_question_used(q_id)
        logger.info(f"Domanda della settimana pubblicata in {guild.name}: {text}")
        return None

    # -------------------------------------------------------------------
    # Chiusura settimana: calcola il vincitore, assegna il ruolo, pubblica il risultato
    # -------------------------------------------------------------------
    async def close_week(self, guild: discord.Guild, week: dict):
        # Chiudiamo subito sul DB: se qualcosa va storto dopo, non si ripete due volte
        self.system.close_week(week["id"])
        results = self.system.get_results(week["id"])

        winners = []
        if results:
            top = results[0][1]
            winners = [(uid, votes) for uid, votes in results if votes == top]  # pareggio = più vincitori
            self.system.add_winners(week["id"], winners)

        role = await self._update_winner_role(guild, [uid for uid, _ in winners])
        channel = await self._get_channel(guild, week["channel_id"])
        if not channel:
            logger.error(f"Canale {week['channel_id']} non trovato per chiudere la settimana {week['id']}")
            return

        # Rimuove il menu dal messaggio originale
        if week["message_id"]:
            try:
                original = await channel.fetch_message(week["message_id"])
                embed = original.embeds[0] if original.embeds else None
                if embed:
                    embed.set_footer(text="Votazione chiusa")
                await original.edit(embed=embed, view=None)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass

        total_votes = sum(v for _, v in results)
        embed = discord.Embed(
            title="🏆 Risultato della settimana",
            description=f"**{week['question_text']}**",
            colour=discord.Color.gold(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )

        if winners:
            names = "\n".join(f"<@{uid}> — **{votes}** voti" for uid, votes in winners)
            embed.add_field(
                name="👑 Il vincitore" if len(winners) == 1 else "👑 I vincitori (pareggio!)",
                value=names, inline=False)
            medals = ["🥇", "🥈", "🥉"]
            lines = [f"{medals[i] if i < 3 else '▫️'} <@{uid}> — {votes}"
                     for i, (uid, votes) in enumerate(results[:5])]
            embed.add_field(name="📊 Classifica", value="\n".join(lines), inline=False)
            if role:
                embed.add_field(name="🎖️ Ruolo", value=f"{role.mention} assegnato!", inline=False)
            embed.set_footer(text=f"Voti totali: {total_votes}")
            content = " ".join(f"<@{uid}>" for uid, _ in winners)
        else:
            embed.add_field(name="😢 Nessun voto", value="Questa settimana non ha votato nessuno.", inline=False)
            content = None

        try:
            await channel.send(
                content=content, embed=embed,
                allowed_mentions=discord.AllowedMentions(users=True, roles=False),
            )
        except discord.HTTPException as e:
            logger.error(f"Impossibile pubblicare il risultato: {e}")

    async def _update_winner_role(self, guild: discord.Guild, winner_ids: list):
        """Toglie il ruolo ai vecchi vincitori e lo dà ai nuovi. Ritorna il Role se configurato."""
        role_id = self.system.get_winner_role(guild.id)
        role = guild.get_role(role_id) if role_id else None
        if not role:
            return None

        for member in list(role.members):
            if member.id not in winner_ids:
                try:
                    await member.remove_roles(role, reason="Domanda della settimana: nuova settimana")
                except discord.HTTPException as e:
                    logger.error(f"Impossibile togliere il ruolo a {member.id}: {e}")

        for uid in winner_ids:
            try:
                member = guild.get_member(uid) or await guild.fetch_member(uid)
                if role not in member.roles:
                    await member.add_roles(role, reason="Vincitore domanda della settimana")
            except discord.NotFound:
                continue  # è uscito dal server
            except discord.HTTPException as e:
                logger.error(f"Impossibile dare il ruolo a {uid}: {e}")
        return role

    # -------------------------------------------------------------------
    # Comandi slash: /domanda ...
    # -------------------------------------------------------------------
    domanda = app_commands.Group(
        name="domanda", description="Domanda della settimana.", guild_ids=GUILD_ID)

    @domanda.command(name="proponi", description="Proponi una domanda per la community.")
    @app_commands.describe(testo="La domanda (es. Chi è più propenso a ...?)")
    async def proponi(self, interaction: discord.Interaction, testo: app_commands.Range[str, 10, 150]):
        guild = interaction.guild
        text = " ".join(testo.split())

        staff_channel_id = self.system.get_channel(guild.id, STAFF_CHANNEL_KIND)
        if not staff_channel_id:
            await interaction.response.send_message(
                "Il sistema delle domande non è ancora configurato.", ephemeral=True)
            return

        if self.system.count_pending_by_author(guild.id, interaction.user.id) >= MAX_PENDING_PER_USER:
            await interaction.response.send_message(
                f"Hai già {MAX_PENDING_PER_USER} proposte in attesa di approvazione. "
                "Aspetta che lo staff le valuti!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        staff_channel = await self._get_channel(guild, staff_channel_id)
        if not staff_channel:
            await interaction.followup.send("Non riesco a raggiungere il canale staff.", ephemeral=True)
            return

        q_id = self.system.add_question(guild.id, interaction.user.id, text)
        embed = discord.Embed(
            title=f"Nuova domanda #{q_id}",
            description=text,
            colour=discord.Color.gold(),
            timestamp=dt.datetime.now(dt.timezone.utc),
        )
        embed.add_field(
            name="Proposta da",
            value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=False)
        embed.set_footer(text="In attesa di moderazione")

        try:
            msg = await staff_channel.send(
                embed=embed, view=self.mod_view,
                allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            self.system.delete_question(q_id)
            await interaction.followup.send(
                "Non sono riuscito a inviare la proposta allo staff. Riprova più tardi.", ephemeral=True)
            return

        self.system.set_question_staff_message(q_id, msg.id)
        await interaction.followup.send(
            "✅ Domanda inviata allo staff! Riceverai un DM quando verrà valutata.", ephemeral=True)

    @domanda.command(name="ruolo", description="Imposta il ruolo da dare al vincitore della settimana.")
    @app_commands.describe(ruolo="Ruolo del vincitore")
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def ruolo(self, interaction: discord.Interaction, ruolo: discord.Role):
        self.system.set_winner_role(interaction.guild_id, ruolo.id)
        await interaction.response.send_message(
            f"Ruolo vincitore impostato su {ruolo.mention}.", ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none())

    @domanda.command(name="coda", description="Mostra lo stato delle domande proposte.")
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def coda(self, interaction: discord.Interaction):
        counts = self.system.count_by_status(interaction.guild_id)
        week = self.system.get_open_week(interaction.guild_id)
        lines = [
            f"⏳ In attesa di moderazione: **{counts.get('pending', 0)}**",
            f"✅ Approvate (in coda): **{counts.get('approved', 0)}**",
            f"📤 Già usate: **{counts.get('used', 0)}**",
            f"❌ Rifiutate: **{counts.get('rejected', 0)}**",
        ]
        if week:
            ts = int(from_naive_utc(week["ends_at"]).timestamp())
            lines.append(f"\n🗳️ Settimana in corso, chiude <t:{ts}:R>.")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @domanda.command(name="importa-default",
                     description="Aggiunge le domande di default alla coda delle approvate.")
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def importa_default(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        texts = DEFAULT_QUESTIONS[:]
        random.shuffle(texts)  # ordine casuale, così non escono sempre nello stesso ordine
        added = 0
        for text in texts:
            if self.system.question_exists(interaction.guild_id, text):
                continue
            self.system.add_approved_question(interaction.guild_id, 0, text)
            added += 1
        await interaction.followup.send(
            f"✅ Aggiunte **{added}** domande alla coda "
            f"({len(texts) - added} già presenti). Usa `/domanda coda` per vedere lo stato.",
            ephemeral=True)

    @domanda.command(name="avvia", description="Pubblica subito la domanda della settimana.")
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def avvia(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.system.get_open_week(interaction.guild_id):
            await interaction.followup.send("C'è già una votazione in corso.", ephemeral=True)
            return
        error = await self.start_week(interaction.guild, dt.datetime.now(TZ), forced=True)
        await interaction.followup.send(error or "✅ Domanda pubblicata!", ephemeral=True)

    @domanda.command(name="chiudi", description="Chiudi subito la votazione in corso e proclama il vincitore.")
    @app_commands.checks.has_role(STAFF_ROLE_ID)
    async def chiudi(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        week = self.system.get_open_week(interaction.guild_id)
        if not week:
            await interaction.followup.send("Non c'è nessuna votazione in corso.", ephemeral=True)
            return
        await self.close_week(interaction.guild, week)
        await interaction.followup.send("✅ Votazione chiusa e risultato pubblicato.", ephemeral=True)