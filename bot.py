import asyncio
from dataclasses import dataclass

from cogs.basic import Basic
from cogs.birthday import BirthdayCog
from cogs.board import HallOfShameCog
from cogs.channel import Channel
from cogs.chess import ChessEvent
from cogs.roles import Roles
from cogs.mod_logs import ModLogs
import discord
from discord.ext import commands, tasks
from cogs.level import LevelCog
import config
from config import GUILD_ID
from utils import roles_system
from utils.bd_system import BirthdaySystem
from utils.chess_db import ChessSystem
from utils.debug import Logger
import os
from utils.level_system import LevelSystem
from utils.embed_factory import EmbedFactory
import json
import re
from utils.roles_system import RoleSystem
from utils.server_system import ServerSystem
from utils.board_system import BoardSystem
from views.ticket_view import TicketView, TicketControlView

import discord.ext.tasks
import datetime as dt
from datetime import datetime, timezone

# Initialize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True
intents.members = True

DM_CATEGORY_ID = 1549228463133818930

host = "localhost"
user = "root"
password = "luca"
database = "discordbot"

server_system = ServerSystem(
    host=host,
    user=user,
    password=password,
    database=database
)

level_system = LevelSystem(
    host=host,
    user=user,
    password=password,
    database=database
)

roles_system = RoleSystem(
    host=host,
    user=user,
    password=password,
    database=database
)

board_system = BoardSystem(
    host=host,
    user=user,
    password=password,
    database=database
)

chess_system = ChessSystem(
    host=host,
    user=user,
    password=password,
    database=database
)

bd_system = BirthdaySystem(
    host=host,
    user=user,
    password=password,
    database=database
)

initial_extensions = [
    "cogs.basic",
    "cogs.embed",
    "cogs.group_commands",
    "cogs.test",
    "cogs.moderation"
]

blacklist = []

with open('configs/blacklist.json') as f:
    d = json.load(f)
    for word in d["words"]:
        blacklist.append(word)




class CloseDMChannelView(discord.ui.View):
    """View persistente con pulsante per consentire allo staff di chiudere il canale."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Chiudi Canale",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="persistent_close_dm_channel_btn"
    )
    async def close_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        # Notifica opzionale all'utente nei DM che la sessione è conclusa
        if interaction.channel.topic:
            user_id_match = re.search(r'ID:\s*(\d+)', interaction.channel.topic)
            if user_id_match:
                user_id = int(user_id_match.group(1))
                try:
                    user = interaction.client.get_user(user_id) or await interaction.client.fetch_user(user_id)
                    close_embed = discord.Embed(
                        title="Ticket Chiuso",
                        description="Il canale di supporto con lo staff è stato chiuso. Se hai ulteriore bisogno, invia un nuovo messaggio!",
                        color=discord.Color.red(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    await user.send(embed=close_embed)
                except Exception:
                    pass

        embed = discord.Embed(
            description=f"🔒 Canale in chiusura da parte di {interaction.user.mention}...",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed)
        await asyncio.sleep(2)
        await interaction.channel.delete(reason=f"Ticket DM chiuso da {interaction.user.name}")


class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.PREFIX, intents=intents)

    async def setup_hook(self):
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}", exc_info=e)

        try:
            await self.add_cog(LevelCog(self, level_system))
            logger.info("Loaded extension: cogs.level")
            await self.add_cog(Roles(self, roles_system))
            logger.info("Loaded extension: cogs.roles")
            await self.add_cog(Channel(self, server_system, board_system))
            logger.info("Loaded extension: cogs.channel")
            await self.add_cog(ChessEvent(self, chess_system))
            logger.info("Loaded extension: cogs.chess")
            await self.add_cog(HallOfShameCog(self, board_system))
            logger.info("Loaded extension: cogs.hall_of_shame")
            await self.add_cog(BirthdayCog(self, bd_system))
            logger.info("Loaded extension: cogs.birthday")
            await self.add_cog(ModLogs(self, server_system))
            logger.info("Loaded extension: cogs.mod_logs")
        except Exception as e:
            logger.error("Failed to load extension", exc_info=e)

        try:
            for g_id in GUILD_ID:
                await self.tree.sync(guild=discord.Object(id=g_id))
            logger.info("Slash commands synced successfully")
        except Exception as e:
            logger.error("Failed to sync slash commands", exc_info=e)

        logger.info("Setting up ticket view")
        self.add_view(TicketView())
        self.add_view(TicketControlView())
        self.add_view(CloseDMChannelView())  # Registra la view per renderla persistente

    async def notify_role_change(self, member: discord.Member, role: discord.Role, action: str):
        """
        Sends a direct message to the user informing them of role addition or removal.
        Silently fails if the user has DMs disabled or bot is blocked.
        """
        embed = EmbedFactory.create_embed(
            title="Ruolo cambiato",
            description=f"Hai **{action}** il ruolo: **{role.name}** in **{member.guild.name}**.",
            colour=discord.Color.green() if action == "selezionato" else discord.Color.red(),
            author="Role System"
        )
        try:
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            logger.warning(f"Could not send role notification DM to {member.name} ({member.id}).")

    @tasks.loop(hours=24)
    async def check_birthday(self):
        today = dt.date.today()
        logger.info(f"Running debug birthday check for {today}")

        bd_role_id = 1549205110826082355

        try:
            rows = bd_system.get_birthdays(today)
            if not rows:
                logger.info("No birthdays found for today.")
                return

            for guild in self.guilds:
                guild_id = guild.id
                channel_id = server_system.get_birthday_channel(guild_id)
                if not channel_id:
                    continue

                birthday_channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)
                if not birthday_channel:
                    continue

                for row in rows:
                    user_id = row[0]
                    try:
                        member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                        if not member:
                            continue

                        embed = EmbedFactory.create_embed(
                            title="🎂 Buon Compleanno! 🎉",
                            description=(
                                f"Tanti auguri di buon compleanno a {member.mention}! 🥳\n"
                                " Ti auguriamo una giornata fantastica piena di gioia e"
                                " di tante cose belle! 💖"
                            ),
                            colour=discord.Color.from_rgb(255, 182, 193),
                            author="Birthday System",
                            thumbnail=(
                                member.avatar.url
                                if member.avatar
                                else member.default_avatar.url
                            ),
                        )

                        await birthday_channel.send(
                            content=f"<@&{bd_role_id}> {member.mention}! 🎈",
                            embed=embed,
                        )
                        logger.info(f"Sent debug birthday message for user {member.name} in guild {guild.name}")

                    except discord.HTTPException as e:
                        logger.error(f"Failed to send birthday message for user {user_id}: {e}")

        except Exception as e:
            logger.error("Error occurred during check_birthday loop execution", exc_info=e)

    async def on_ready(self):
        logger.info(f"We have logged in as {self.user.name} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        try:
            # Presenza aggiornata per informare gli utenti della funzione DM/Supporto
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="Scrivimi in DM per parlare con lo staff!"
                )
            )
            logger.info("Presence updated successfully")

            self.meme = self.get_channel(1516814162846810234)
            self.check_birthday.start()
        except Exception as e:
            logger.error("Failed to update presence", exc_info=e)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # =========================================================================
        # 1. GESTIONE DM: Da Utente Privato -> Canale Staff
        # =========================================================================
        if isinstance(message.channel, discord.DMChannel):
            logger.info(f"Received DM from {message.author.name} (ID: {message.author.id})")

            category = None
            guild = None
            for g_id in GUILD_ID:
                target_guild = self.get_guild(g_id)
                if target_guild:
                    category = discord.utils.get(target_guild.categories, id=DM_CATEGORY_ID)
                    if category:
                        guild = target_guild
                        break

            if not category or not guild:
                logger.error(f"Categoria DM con ID {DM_CATEGORY_ID} non trovata.")
                return

            # Cerca se esiste già un canale aperto per questo utente
            target_channel = None
            for ch in category.text_channels:
                if ch.topic and str(message.author.id) in ch.topic:
                    target_channel = ch
                    break

            # Se non esiste, crea il canale e invia sia l'header allo staff sia l'embed di conferma all'utente
            if not target_channel:
                clean_name = re.sub(r'[^a-zA-Z0-9_-]', '', message.author.name.lower().replace(" ", "-"))
                channel_name = f"dm-{clean_name}"[:100]

                target_channel = await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    topic=f"Canale di supporto DM per: {message.author.name} (ID: {message.author.id})"
                )
                logger.info(f"Created DM channel {target_channel.name} ({target_channel.id}) for {message.author.name}")

                # 1. Embed intestazione nel canale staff
                header_embed = discord.Embed(
                    title="Nuova Conversazione DM",
                    description=(
                        f"Questo canale è stato aperto automaticamente per comunicare con {message.author.mention}.\n"
                        f"• Tutti i messaggi inviati qui dallo staff saranno recapitati in DM all'utente.\n"
                        f"• Quando la conversazione è conclusa, clicca sul pulsante sottostante per eliminare il canale."
                    ),
                    color=discord.Color.gold(),
                    timestamp=datetime.now(timezone.utc)
                )
                header_embed.set_author(name=f"{message.author.name} ({message.author.id})",
                                        icon_url=message.author.display_avatar.url)
                header_embed.set_footer(text="Staff Support Panel")

                await target_channel.send(embed=header_embed, view=CloseDMChannelView(), content="@everyone")

                # 2. Embed inviato in risposta all'utente nei DM (solo al primo messaggio)
                ack_embed = discord.Embed(
                    title="Richiesta Ricevuta! 📬",
                    description=(
                        "Ciao! Abbiamo recapitato il tuo messaggio al nostro team di moderazione.\n\n"
                        "Uno staffer prenderà in carico la tua richiesta e **ti risponderà direttamente qui a breve**."
                    ),
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                if guild.icon:
                    ack_embed.set_thumbnail(url=guild.icon.url)
                ack_embed.set_footer(text=guild.name, icon_url=guild.icon.url if guild.icon else None)

                try:
                    await message.author.send(embed=ack_embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send DM confirmation to {message.author.id}")

            # Inoltro del messaggio dell'utente nel canale dello staff
            embed = discord.Embed(
                description=message.content if message.content else "*Nessun contenuto testuale*",
                colour=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(
                name=f"{message.author.display_name} (DM Utente)",
                icon_url=message.author.display_avatar.url
            )
            embed.set_footer(text=f"User ID: {message.author.id}")

            if message.attachments:
                embed.set_image(url=message.attachments[0].url)

            await target_channel.send(embed=embed)
            await message.add_reaction("📨")
            return

        # =========================================================================
        # 2. GESTIONE RISPOSTA STAFF: Da Canale Staff -> DM Utente
        # =========================================================================
        if message.channel.category_id == DM_CATEGORY_ID and message.channel.topic:
            user_id_match = re.search(r'ID:\s*(\d+)', message.channel.topic)
            if user_id_match:
                recipient_id = int(user_id_match.group(1))
                try:
                    recipient = await self.fetch_user(recipient_id)

                    staff_embed = discord.Embed(
                        description=message.content if message.content else "*Nessun testo*",
                        colour=discord.Color.green(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    staff_embed.set_author(
                        name=f"{message.author.display_name} (Staff)",
                        icon_url=message.author.display_avatar.url
                    )

                    if message.attachments:
                        staff_embed.set_image(url=message.attachments[0].url)

                    await recipient.send(embed=staff_embed)
                    await message.add_reaction("✅")
                    logger.info(f"Staff member {message.author.name} replied to user {recipient.id}")
                except discord.Forbidden:
                    await message.channel.send(
                        "⚠️ Impossibile recapitare il messaggio: l'utente ha i DM disabilitati o ha bloccato il bot.")
                except Exception as e:
                    logger.error(f"Errore nell'inoltro della risposta staff via DM: {e}")
                return

        # =========================================================================
        # 3. FILTRO BLACKLIST
        # =========================================================================
        if any(elem in message.content for elem in blacklist):
            await message.delete()
            return

        await self.process_commands(message)

    async def on_member_join(self, member: discord.Member):
        logger.info(f"New member joined: {member.name}")

        guild_id = member.guild.id
        description = server_system.get_description(guild_id)

        try:
            role_id_data = server_system.get_role(guild_id)
            if role_id_data:
                role_id = role_id_data[0]
                role = await member.guild.fetch_role(role_id)
                await member.add_roles(role)
        except Exception as e:
            logger.warning(f"No role found or impossible to add: {e}")

        embed = discord.Embed(
            colour=discord.Color.dark_gray(),
            title=f"{member.name} si è unito a {member.guild.name} 🎉",
            description=description.replace("%u", f"{member.mention}")
        )

        channels = server_system.get_channels(guild_id)
        if channels:
            for item in channels:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    channel_id, desc = item
                    channel = self.get_channel(channel_id)
                else:
                    logger.warning(f"Unexpected data format in channels list: {item}")

        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        embed.set_thumbnail(url=avatar_url)

        channel_id = server_system.get_announce_channel(guild_id)
        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed, content=f"Welcome {member.mention}!")
            else:
                logger.error(f"Announce channel con ID {channel_id} non trovato in cache.")
        else:
            logger.warning(f"Nessun canale announce configurato per la gilda {guild_id}")

    async def on_member_leave(self, member: discord.Member):
        logger.info(f"Member left: {member.name}")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        logger.info("--- Reaction Add Event Triggered ---")

        if payload.member and payload.member.bot:
            logger.info("Ignored: Reaction is from a bot.")
            return

        emoji_identifier = payload.emoji.id or payload.emoji.name
        logger.info(f"Reaction added: {emoji_identifier} on message ID: {payload.message_id}")

        target_emoji = '⭐'

        if payload.emoji.name == target_emoji:
            board_system.add_reaction(payload.message_id)
            n_reactions = board_system.get_reactions(payload.message_id)[0]

            min_react = board_system.get_min_reactions(payload.guild_id)
            logger.info(f"Current reactions: {n_reactions} / Target: {min_react}")

            if n_reactions == min_react:
                logger.info("Threshold reached! Fetching original message...")

                source_channel = self.get_channel(payload.channel_id) or await self.fetch_channel(payload.channel_id)
                if not source_channel:
                    logger.error(f"Could not find source channel {payload.channel_id}.")
                    return

                try:
                    message = await source_channel.fetch_message(payload.message_id)
                    logger.info(f"Successfully fetched message from {message.author.name}")
                except discord.NotFound:
                    logger.error(f"Message {payload.message_id} not found. It may have been deleted.")
                    return
                except discord.Forbidden:
                    logger.error("Bot lacks 'Read Message History' permissions in the source channel.")
                    return

                description = f"{message.content}\n\n**[Jump to message!]({message.jump_url})**"
                embed = EmbedFactory.create_embed(
                    description=description,
                    colour=discord.Color.gold(),
                    timestamp=True
                )

                avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
                embed.set_author(name=message.author.display_name, icon_url=avatar_url)

                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in
                               ['png', 'jpg', 'jpeg', 'gif', 'webp']):
                            embed.set_image(url=attachment.url)
                            logger.info("Image attachment found and added to embed.")
                            break

                channel_id = board_system.get_board_channel(payload.guild_id)
                logger.info(f"Board Channel ID found: {channel_id}")

                if channel_id:
                    channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)

                    if channel:
                        sent_msg = await channel.send(
                            content="get a load of this chud...", embed=embed)
                        logger.info("Successfully sent featured message to board channel!")

                        board_system.add_boarded(payload.message_id, sent_msg.id, message.author.id)
                        logger.info(f"Saved to DB: Original {payload.message_id} -> Board {sent_msg.id}")
                    else:
                        logger.error(f"Board channel {channel_id} not found.")
                else:
                    logger.warning("No board channel set for this guild. Use /setboard to set it.")

            elif n_reactions == min_react + 2:
                logger.info("Threshold + 2 reached! Checking for image to set as bot pfp...")

                source_channel = self.get_channel(payload.channel_id) or await self.fetch_channel(payload.channel_id)
                if not source_channel:
                    return

                try:
                    message = await source_channel.fetch_message(payload.message_id)
                except (discord.NotFound, discord.Forbidden):
                    return

                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'gif']):
                            try:
                                image_bytes = await attachment.read()
                                await self.user.edit(avatar=image_bytes)
                                logger.info(f"Successfully updated bot profile picture to {attachment.filename}!")
                                break
                            except discord.HTTPException as e:
                                logger.error(f"Failed to update avatar (may be rate-limited): {e}")
            else:
                logger.info("Threshold not met (or already surpassed), skipping embed creation.")

        # --- Self-Roles System ---
        role_id = roles_system.get_role(payload.message_id, str(emoji_identifier))
        if role_id:
            try:
                server: discord.Guild = self.get_guild(payload.guild_id) or await self.fetch_guild(
                    payload.guild_id)
                member = payload.member or await server.fetch_member(payload.user_id)
                target_role: discord.Role = server.get_role(role_id) or await server.fetch_role(role_id)

                # Check if multiselect is disabled
                if not roles_system.is_multiselect(payload.message_id):
                    all_message_roles = roles_system.get_all_roles_for_message(payload.message_id)
                    roles_to_remove = []

                    source_channel = self.get_channel(payload.channel_id) or await self.fetch_channel(
                        payload.channel_id)
                    target_message = None
                    try:
                        target_message = await source_channel.fetch_message(payload.message_id)
                    except Exception:
                        pass

                    for r in all_message_roles:
                        other_role_id = r["role_id"]
                        other_emoji = r["emoji"]

                        if other_role_id != role_id:
                            other_role = server.get_role(other_role_id)
                            if other_role and other_role in member.roles:
                                roles_to_remove.append(other_role)

                            # Remove the other reaction made by this user
                            if target_message:
                                try:
                                    if str(other_emoji).isdigit():
                                        reac_obj = self.get_emoji(int(other_emoji))
                                    else:
                                        reac_obj = other_emoji
                                    if reac_obj:
                                        await target_message.remove_reaction(reac_obj, member)
                                except Exception:
                                    pass

                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove,
                                                  reason="Reaction Role: Single-select enforced")
                        for old_role in roles_to_remove:
                            await self.notify_role_change(member, old_role, "rimosso")

                if target_role:
                    if target_role not in member.roles:
                        await member.add_roles(target_role, reason="Reaction Role added")
                        logger.info(f"Successfully added role: {target_role.name} to {member.name}")
                        await self.notify_role_change(member, target_role, "selezionato")
            except Exception as e:
                logger.error(f"Failed to add role. Error: {e}", exc_info=e)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        logger.info(f"Payload: {payload}")
        if payload.user_id == self.user.id:
            return

        emoji_identifier = payload.emoji.id or payload.emoji.name
        guild: discord.Guild = self.get_guild(payload.guild_id) or await self.fetch_guild(payload.guild_id)

        try:
            member: discord.Member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            logger.warning(f"Member not found in guild {guild.id} for user ID {payload.user_id}")
            return

        logger.info(f"Received reaction: {emoji_identifier} by {member.name}")

        target_emoji = '⭐'

        if payload.emoji.name == target_emoji:
            board_message_id = board_system.get_boarded(payload.message_id)
            if isinstance(board_message_id, tuple):
                board_message_id = board_message_id[0]

            board_system.remove_reaction(payload.message_id)

            reactions = board_system.get_reactions(payload.message_id)
            min_react = board_system.get_min_reactions(payload.guild_id)

            current_reactions = 0
            if reactions is not None:
                current_reactions = reactions[0] if isinstance(reactions, tuple) else reactions

            if current_reactions < min_react:
                if board_message_id:
                    channel_id = board_system.get_board_channel(payload.guild_id)
                    channel = self.get_channel(channel_id) if channel_id else None

                    if channel:
                        try:
                            message = await channel.fetch_message(board_message_id)
                            logger.info("Successfully fetched boarded message from board channel.")
                            await message.delete()
                            logger.info(
                                f"Deleted board message {board_message_id} because reactions fell below threshold.")
                        except discord.NotFound:
                            logger.error(
                                f"Board message {board_message_id} not found. It may have been manually deleted.")
                        except discord.Forbidden:
                            logger.error("Bot lacks permissions in the board channel.")

        # --- Self-Roles System ---
        role_id = roles_system.get_role(payload.message_id, str(emoji_identifier))
        if not role_id:
            return

        try:
            role: discord.Role = guild.get_role(role_id) or await guild.fetch_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Reaction Role removed")
                logger.info(f"Removed role: {role.name} from {member.name}")
                await self.notify_role_change(member, role, "rimosso")
        except discord.NotFound:
            logger.warning(f"Role with ID {role_id} not found in guild {guild.id}")
        except Exception as e:
            logger.error(f"Failed to remove role: {e}")


bot = DiscordBot()


async def main():
    try:
        logger.info("Starting bot...")
        async with bot:
            await bot.start(config.TOKEN)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
    except Exception as e:
        logger.critical("Bot crashed!", exc_info=e)
    finally:
        logger.info("Bot has shut down!")


if __name__ == "__main__":
    asyncio.run(main())