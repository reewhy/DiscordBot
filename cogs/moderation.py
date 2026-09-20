import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import asyncio
from utils.embed_factory import EmbedFactory
from utils.board_system import BoardSystem
from utils.debug import Logger
from utils.moderation_system import ModerationSystem
import os
from config import GUILD_ID

# Initialize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

def parse_duration(duration_str: str) -> timedelta:
    """
    Parses a duration string and returns a corresponding timedelta.
    """
    try:
        num = int(duration_str[:-1])
        unit = duration_str[-1].lower()
        mapping = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days'
        }
        if unit not in mapping:
            raise ValueError(f"Unrecognized time unit '{unit}'")
        return timedelta(**{mapping[unit]: num})
    except Exception as e:
        logger.error(f"Error parsing duration '{duration_str}': {e}")
        raise ValueError(f"Invalid duration format: {duration_str}") from e

class Moderation(commands.Cog):
    """
    Cog to handle moderation commands such as temp banning, unbanning, and kicking users.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = ModerationSystem(
            host="localhost",
            user="root",
            password="luca",
            database="discordbot"
        )
        self.board_db = BoardSystem(
            host="localhost",
            user="root",
            password="luca",
            database="discordbot"
        )
        self.next_unban_time = None
        self.unban_task = self.bot.loop.create_task(self._update_next_unban_time())

    async def _send_moderation_dm(self, member: discord.Member, action: str, guild_name: str, reason: str, duration: str = None):
        """
        Sends an informative DM to the user before they are kicked/banned.
        """
        try:
            desc = (
                f"Sei stato **{action}** da **{guild_name}**.\n\n"
                f"📝 **Motivo:** {reason}\n"
            )
            if duration:
                desc += f"⏳ **Durata:** `{duration}`\n"

            desc += (
                "\n📩 *Nota:* Scrivendo un messaggio diretto a questo bot entrerai in contatto "
                "con lo staff per supporto o chiarimenti."
            )

            embed = discord.Embed(
                title=f"Avviso di Moderazione: {action.capitalize()}",
                description=desc,
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            if member.guild.icon:
                embed.set_thumbnail(url=member.guild.icon.url)

            await member.send(embed=embed)
            logger.info(f"Notified {member.id} ({member.name}) via DM of action: {action}")
        except discord.Forbidden:
            logger.warning(f"Could not deliver DM to {member.id} ({member.name}): DMs disabled or bot blocked.")
        except Exception as e:
            logger.error(f"Error sending moderation DM to {member.id}: {e}")

    @app_commands.command(name="setminreactions", description="Imposta il numero minimo di reazioni per la board.")
    @app_commands.describe(amount="Numero minimo di reazioni richieste (es. 3).")
    @app_commands.checks.has_any_role(1530983265467498636, 1516814689110200381)
    @app_commands.guilds(*GUILD_ID)
    async def setminreactions(self, interaction: discord.Interaction, amount: int):
        logger.info(f"Admin {interaction.user.name} changing min reactions to {amount} for guild {interaction.guild_id}")

        if amount < 1:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Il numero minimo di reazioni deve essere almeno 1.",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await asyncio.to_thread(self.board_db.set_min_reactions, interaction.guild_id, amount)

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"✅ Il numero minimo di reazioni per la board è stato impostato a **{amount}**.",
            title="Board Aggiornata!",
            colour=discord.Color.green(),
            author="Moderation"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tempban", description="Temporarily ban a user.")
    @app_commands.describe(
        member="Member to ban.",
        reason="Reason for the ban.",
        duration="Duration in format <number><unit> (s=seconds, m=minutes, h=hours, d=days)."
    )
    @app_commands.checks.has_any_role(1539463835931377765, 1516814689110200381)
    @app_commands.guilds(*GUILD_ID)
    async def tempban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "Nessun motivo specificato"
    ):
        logger.info(f"Temp banning user {member.id} ({member.name}) for {duration} due to {reason}")

        try:
            delta = parse_duration(duration)
        except Exception as e:
            logger.error(f"Failed to parse duration '{duration}': {e}")
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Formato durata non valido. Usa es. `10m`, `2h`, `1d`.",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 1. Avvisa prima l'utente nei DM
        await self._send_moderation_dm(
            member=member,
            action="bannato temporaneamente",
            guild_name=interaction.guild.name,
            reason=reason,
            duration=duration
        )

        unban_time = datetime.now(timezone.utc).replace(tzinfo=None) + delta

        # 2. Esegui il ban
        await member.ban(reason=reason)
        logger.info(f"Banned user {member.id} ({member.name}) for {duration}. Unban scheduled at {unban_time}")

        # 3. Salva nel DB e programma sban
        await asyncio.to_thread(self.db.tempban, member.id, interaction.guild_id, reason, unban_time)
        await self._update_next_unban_time()

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"🔨 {member.mention} è stato temporaneamente bannato per `{duration}`",
            title="Utente Bannato!",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )
        embed.add_field(name="📝 Motivo", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    async def _update_next_unban_time(self):
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            delay = (unban_time - now).total_seconds()

            logger.info(f"Next unban scheduled for user {user_id} in guild {guild_id} at {unban_time}. Delay: {delay}s")

            if delay > 0 and (self.next_unban_time is None or unban_time < self.next_unban_time):
                self.next_unban_time = unban_time

                if self.unban_task and not self.unban_task.done():
                    self.unban_task.cancel()

                self.unban_task = self.bot.loop.create_task(self._unban_after_delay(delay))
                logger.info(f"Unban task scheduled to run after {delay}s")
            elif delay <= 0:
                await self._unban_user()

    async def _unban_after_delay(self, delay: float):
        logger.info(f"Sleeping for {delay} seconds before unbanning the user.")
        await asyncio.sleep(delay)
        await self._unban_user()

    async def _unban_user(self):
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban
            guild = self.bot.get_guild(guild_id)

            if guild:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await guild.unban(user, reason="Ban temporaneo scaduto.")
                    logger.info(f"User {user_id} has been unbanned in guild {guild_id}")
                except discord.NotFound:
                    logger.warning(f"User with ID {user_id} not found for unban in guild {guild_id}.")
                except Exception as e:
                    logger.error(f"Error unbanning user {user_id}: {e}")

        await asyncio.to_thread(self.db.delete_expired_bans)
        self.next_unban_time = None
        await self._update_next_unban_time()

    @app_commands.command(name="pardon", description="Pardon a temporarily banned user.")
    @app_commands.describe(user="User to pardon.", reason="Reason for the pardon.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def pardon(self, interaction: discord.Interaction, user: discord.User, reason: str = "Pardon"):
        logger.info(f"Pardoning user {user.id} ({user.name}) in guild {interaction.guild.id} for reason: {reason}")

        removed = await asyncio.to_thread(self.db.pardon, user.id, interaction.guild.id)

        if not removed:
            logger.warning(f"No active tempban found for user {user.id} ({user.name}) in guild {interaction.guild.id}")
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"⚠️ Nessun ban temporaneo attivo trovato per {user.mention}.",
                title="Errore",
                thumbnail=user.display_avatar.url,
                colour=discord.Color.yellow(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        guild = interaction.guild
        try:
            await guild.unban(user, reason=reason)
            logger.info(f"User {user.id} ({user.name}) has been unbanned in guild {guild.id}.")
        except discord.NotFound:
            logger.warning(f"User {user.id} not found on server ban list.")

        await self._update_next_unban_time()

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"☑️ Hai revocato il ban a {user.name}",
            title="Sbannato!",
            thumbnail=user.display_avatar.url,
            colour=discord.Color.green(),
            author="Moderation"
        )
        embed.add_field(name="Motivo", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kick", description="Kick a user.")
    @app_commands.describe(member="Member to kick.", reason="Reason for the kick.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Nessun motivo specificato"):
        logger.info(f"Kicking user {member.id} ({member.name}) from guild {interaction.guild.id} for reason: {reason}")

        # Invia prima il DM di notifica
        await self._send_moderation_dm(
            member=member,
            action="espulso (kicked)",
            guild_name=interaction.guild.name,
            reason=reason
        )

        await member.kick(reason=reason)

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⛔ Hai espulso {member.mention}",
            title="Espulso!",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )
        embed.add_field(name="Motivo", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ban", description="Ban a user.")
    @app_commands.describe(member="Member to ban.", reason="Reason for the ban.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def ban(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "Nessun motivo specificato"
    ):
        logger.info(f"Banning user {member.id} ({member.name}) from guild {interaction.guild.id} for reason: {reason}")

        # Invia prima il DM di notifica
        await self._send_moderation_dm(
            member=member,
            action="bannato",
            guild_name=interaction.guild.name,
            reason=reason
        )

        await member.ban(reason=reason)

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⛔ Hai bannato {member.mention}",
            title="Bannato!",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )
        embed.add_field(name="Motivo", value=reason)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete", description="Delete messages.")
    @app_commands.describe(number="Number of messages to delete (max 100)", member="User to filter messages by")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def delete(self, interaction: discord.Interaction, number: int = 10, member: discord.Member = None):
        await interaction.response.defer(ephemeral=True)
        logger.info(f"Purging up to {number} messages from channel {interaction.channel.id}")

        def check_filter(msg):
            return member is None or msg.author.id == member.id

        deleted = await interaction.channel.purge(limit=number, check=check_filter)
        count = len(deleted)

        target_text = f" da {member.mention}" if member else ""
        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"Eliminati **{count}** messaggi{target_text}.",
            title="Messaggi Eliminati!",
            thumbnail=member.display_avatar.url if member else interaction.user.display_avatar.url,
            colour=discord.Colour.red(),
            author="Moderation"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="mute", description="Mute / Timeout a member.")
    @app_commands.describe(
        member="Member to mute.",
        duration="Duration format: <number><unit> (e.g. 10m, 2h, 1d - max 28d).",
        reason="Reason for the timeout."
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guilds(*GUILD_ID)
    async def mute(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            duration: str,
            reason: str = "Nessun motivo specificato"
    ):
        logger.info(f"Muting user {member.id} ({member.name}) for {duration} due to: {reason}")

        # 1. Parse duration
        try:
            delta = parse_duration(duration)
        except Exception as e:
            logger.error(f"Failed to parse duration '{duration}': {e}")
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Formato durata non valido. Usa es. `10m`, `2h`, `1d`.",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Discord timeouts have a maximum limit of 28 days
        if delta > timedelta(days=28) or delta.total_seconds() <= 0:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ La durata del mute deve essere compresa tra 1 secondo e 28 giorni.",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Check role hierarchy
        if interaction.guild.me.top_role <= member.top_role:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Non posso mutare questo utente perché ha un ruolo uguale o superiore al mio.",
                title="Errore Permessi",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Inform the user in DMs before applying the timeout
        await self._send_moderation_dm(
            member=member,
            action="silenziato (in timeout)",
            guild_name=interaction.guild.name,
            reason=reason,
            duration=duration
        )

        # 3. Apply native timeout
        try:
            await member.timeout(delta, reason=reason)
            logger.info(f"Successfully timed out {member.name} ({member.id}) for {duration}.")
        except discord.Forbidden:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Permessi insufficienti per applicare il timeout a questo utente.",
                title="Errore Permessi",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        except Exception as e:
            logger.error(f"Error while muting {member.id}: {e}")
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"❌ Errore durante il mute: {e}",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 4. Confirmation embed
        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"🔇 {member.mention} è stato silenziato per `{duration}`",
            title="Utente Silenziato!",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.orange(),
            author="Moderation"
        )
        embed.add_field(name="📝 Motivo", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unmute", description="Unmute / Remove timeout from a member.")
    @app_commands.describe(
        member="Member to unmute.",
        reason="Reason for unmuting."
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guilds(*GUILD_ID)
    async def unmute(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "Timeout rimosso dallo staff"
    ):
        logger.info(f"Unmuting user {member.id} ({member.name})")

        if not member.is_timed_out():
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"⚠️ {member.mention} non è attualmente silenziato.",
                title="Attenzione",
                colour=discord.Color.yellow(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            # Setting timeout to None removes the timeout immediately
            await member.timeout(None, reason=reason)
            logger.info(f"Successfully removed timeout for {member.name} ({member.id}).")
        except discord.Forbidden:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Non ho i permessi per rimuovere il timeout a questo utente.",
                title="Errore Permessi",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"🔊 Il timeout a {member.mention} è stato revocato.",
            title="Utente Smutato!",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.green(),
            author="Moderation"
        )
        embed.add_field(name="📝 Motivo", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warn", description="Avvisa un utente.")
    @app_commands.describe(member="Utente da avvisare.", reason="Motivo dell'avviso.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guilds(*GUILD_ID)
    async def warn(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "Nessun motivo specificato"
    ):
        if member.bot:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Non puoi ammonire un bot.",
                title="Errore!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 1. Salva il warn nel DB
        warn_id = await asyncio.to_thread(
            self.db.add_warning, member.id, interaction.guild_id, interaction.user.id, reason
        )
        total_warns = await asyncio.to_thread(self.db.get_warning_count, member.id, interaction.guild_id)

        logger.info(f"User {member.id} warned by {interaction.user.id}. Total warnings: {total_warns}")

        # 2. Invia notifica DM all'utente
        await self._send_moderation_dm(
            member=member,
            action="ammonito (avvertimento)",
            guild_name=interaction.guild.name,
            reason=f"{reason} (Avviso #{total_warns})"
        )

        # 3. Auto-escalation (es. 3 warn = 1h timeout, 5 warn = 1d timeout)
        escalation_text = ""
        if total_warns == 3:
            try:
                await member.timeout(timedelta(hours=1), reason="Raggiunti 3 avvertimenti")
                escalation_text = "\n⚠️ **Auto-Escalation:** L'utente è stato silenziato per 1 ora (3° avviso)."
            except Exception as e:
                logger.error(f"Failed to auto-timeout user {member.id}: {e}")
        elif total_warns >= 5:
            try:
                await member.timeout(timedelta(days=1), reason="Raggiunti 5 o più avvertimenti")
                escalation_text = "\n⛔ **Auto-Escalation:** L'utente è stato silenziato per 1 giorno (5° avviso)."
            except Exception as e:
                logger.error(f"Failed to auto-timeout user {member.id}: {e}")

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⚠️ {member.mention} è stato ammonito.\n**Totale avvisi attivi:** `{total_warns}`{escalation_text}",
            title=f"Avviso #{warn_id} Registrato",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.yellow(),
            author="Moderation"
        )
        embed.add_field(name="📝 Motivo", value=reason, inline=False)
        embed.add_field(name="👮 Moderatore", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="warnings", description="Visualizza lo storico avvertimenti di un utente.")
    @app_commands.describe(member="Utente di cui consultare gli avvisi.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guilds(*GUILD_ID)
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        rows = await asyncio.to_thread(self.db.get_warnings, member.id, interaction.guild_id)

        if not rows:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"✅ {member.mention} non ha nessun avviso registrato.",
                title="Fedina Pulita",
                colour=discord.Color.green(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"Storico violazioni per {member.mention} (**{len(rows)}** totali):",
            title="Registro Avvertimenti",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.orange(),
            author="Moderation"
        )

        # Mostra fino agli ultimi 10 warn per non superare il limite dei campi embed
        for warn_id, mod_id, reason, timestamp in rows[:10]:
            formatted_date = timestamp.strftime("%d/%m/%Y %H:%M")
            embed.add_field(
                name=f"ID: #{warn_id} | Data: {formatted_date}",
                value=f"• **Motivo:** {reason}\n• **Mod:** <@{mod_id}>",
                inline=False
            )

        if len(rows) > 10:
            embed.set_footer(text=f"...e altri {len(rows) - 10} avvisi più vecchi.")

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="removewarn", description="Rimuovi un avvertimento specifico tramite il suo ID.")
    @app_commands.describe(warn_id="L'ID univoco del warn da eliminare.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.guilds(*GUILD_ID)
    async def removewarn(self, interaction: discord.Interaction, warn_id: int):
        removed = await asyncio.to_thread(self.db.remove_warning, warn_id, interaction.guild_id)

        if not removed:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"❌ Nessun avvertimento trovato con ID `#{warn_id}` in questo server.",
                title="Non trovato",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"✅ Avvertimento `#{warn_id}` rimosso con successo.",
            title="Avviso Rimosso",
            colour=discord.Color.green(),
            author="Moderation"
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="clearwarns", description="Cancella tutti gli avvertimenti di un utente.")
    @app_commands.describe(member="Utente a cui resettare la cronologia avvisi.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def clearwarns(self, interaction: discord.Interaction, member: discord.Member):
        count = await asyncio.to_thread(self.db.clear_warnings, member.id, interaction.guild_id)

        if count == 0:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"⚠️ {member.mention} non aveva avvisi da rimuovere.",
                title="Nessun Avviso",
                colour=discord.Color.yellow(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"🧹 Sono stati cancellati tutti i **{count}** avvertimenti di {member.mention}.",
            title="Avvisi Azzerati",
            thumbnail=member.display_avatar.url,
            colour=discord.Color.green(),
            author="Moderation"
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))