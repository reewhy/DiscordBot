import asyncio
from dataclasses import dataclass

from cogs.basic import Basic
from cogs.channel import Channel
from cogs.roles import Roles
import discord
from discord.ext import commands
from cogs.level import LevelCog
import config
from config import GUILD_ID
from utils import roles_system
from utils.debug import Logger
import os
from utils.level_system import LevelSystem
from utils.embed_factory import EmbedFactory
import json
import re
from utils.roles_system import RoleSystem
from utils.server_system import ServerSystem
from utils.board_system import BoardSystem

# Initilize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

intents = discord.Intents.all()
intents.message_content = True

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

class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.PREFIX, intents=intents)

    async def setup_hook(self):
        # List here all your cogs, they will be automatically loaded
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}", exc_info=e)
        
        try:
            await self.add_cog(LevelCog(self, level_system))
            logger.info(f"Loaded extension: cogs.level")
            await self.add_cog(Roles(self, roles_system))
            logger.info("Loaded extension: cogs.roles")
            await self.add_cog(Channel(self, server_system, board_system))
            logger.info("Loaded extension: cogs.channel")
        except Exception as e:
            logger.error(f"Failed to load extension", exc_info=e)

        try:
            for g_id in GUILD_ID:
                await self.tree.sync(guild=discord.Object(id=g_id))
            logger.info("Slash commands synced successfully")
        except Exception as e:
            logger.error("Failed to sync slash commands", exc_info=e)

    async def on_ready(self):
        logger.info(f"We have logged in as {bot.user.name} (ID: {bot.user.id}")
        logger.info(f"Connected to {len(bot.guilds)} guild(s)")

        try:
            # Setup here your custom presence on ready
            await bot.change_presence(
                status = discord.Status.online,
                activity=discord.Game(name="witchcraft")
            )
            logger.info("Presence updated successfully")


            # self.announce_channel = self.get_channel(1528433049828589731)
            # self.level_channel = self.get_channel(1528433049828589733)

            self.meme = self.get_channel(1516814162846810234)


            embed = EmbedFactory.create_embed(
                title="Ready!",
                description="🟩 The bot is ready to use!",
                colour=discord.Color.green(),
                author=False
            )
            # await self.announce_channel.send(embed=embed)
            # await self.meme.send(content='')
        except Exception as e:
            logger.error("Failed to update presence", exc_info=e)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        
        res = any(elem in message.content for elem in blacklist)
        if res:
            await message.delete()
            return

        _, level = level_system.add_xp(message.author.id, message.guild.id, amount=10)
        xp, user_level = level_system.get_user(message.author.id, message.guild.id)

        try:
            roles = server_system.get_all_roles(message.guild.id, user_level)
            logger.info(roles)
            to_add = []
            if len(roles) > 0:
                for role_id in roles:
                    role = await message.guild.fetch_role(role_id[0])
                    to_add.append(role)
                logger.info(to_add)
                await message.author.add_roles(*to_add)
        except Exception as e:
            logger.error("Error in role level:", exc_info=e)

        if xp == 0:
            embed = EmbedFactory.create_embed(
                title="Level up!",
                description=f"🎉 {message.author.mention} just leveled up!",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=message.author.avatar.url
            )

            embed.add_field(name="New level", value=user_level, inline=True)
            
            guild_id = message.guild.id
            
            channel_id = server_system.get_level_channel(guild_id)[0]
            
            logger.info(f"Found channel: {channel_id}")

            level_channel = self.get_channel(channel_id)
            
            if level_channel:
                await level_channel.send(embed=embed)
            else:
                await self.announce_channel.send(content="Channel not found")

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
            colour=discord.Color.brand_green(),
            title=f"{member.name} si è unito a {member.guild.name} 🎉",
            description=description.replace("%u", f"{member.mention}")
        )

        print("canali: ")
        channels = server_system.get_channels(guild_id)
        print(channels)

        if channels:
            for channel_id, desc in channels:
                channel = self.get_channel(channel_id)
                if channel:
                    embed.add_field(name=desc, value=channel.mention, inline=False)

        # FIX AVATAR: Se l'utente non ha un avatar personalizzato, usa quello di default di Discord
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        embed.set_thumbnail(url=avatar_url)

        embed.set_image(
            url="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmF2MTc2YjBxamZ3aXdvMnF6cGdrc2s1dDR1YnR3aGVqb2c2Yjd3bSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ExMGjbktr4phe/giphy.gif")

        # FIX ANNOUNCE: Rimuoviamo il [0] superfluo perché il metodo restituisce già l'ID pulito
        channel_id = server_system.get_announce_channel(guild_id)

        if channel_id:
            channel = self.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed, content="||@everyone||")
            else:
                logger.error(f"Announce channel con ID {channel_id} non trovato in cache.")
        else:
            logger.warning(f"Nessun canale announce configurato per la gilda {guild_id}")

    
    async def on_member_leave(self, member: discord.Member):
        logger.info(f"Member left: {member.name}")

        guild_id = member.guild.id

        embed = discord.Embed(
            colour=discord.Color.brand_red(),
            title=f"{member.name} ci ha abandonati 😢",
            description=f"Prima o poi si pentirà della sua scelta."
        )

        embed.set_thumbnail(url=member.avatar.url)
        
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZnd3aDJwYzdoZWhkbGV6b2Joc3c3MjJvZzUwMG8zMjljOGo5eXN1aSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/nyDuytA5bRdbW/giphy.gif")
        
        channel_id = server_system.get_announce_channel(guild_id)[0]
        channel = self.get_channel(channel_id)

        if channel:
            await channel.send(embed=embed, content="||everyone||")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        logger.info("--- Reaction Add Event Triggered ---")

        if payload.member and payload.member.bot:
            logger.info("Ignored: Reaction is from a bot.")
            return

        emoji_id = payload.emoji.id or payload.emoji.name
        logger.info(f"Reaction added: {emoji_id} on message ID: {payload.message_id}")



        # emoji filter
        # todo: use emoji from board_config
        target_emoji_id = 1517325122363592867

        if payload.emoji.id == target_emoji_id:
            # 1. Update and check reaction count
            board_system.add_reaction(payload.message_id)
            n_reactions = board_system.get_reactions(payload.message_id)[0]

            # Hardcoded to 1 for testing — ensure this matches your desired threshold!
            min_react = board_system.get_min_reactions(payload.guild_id)
            logger.info(f"Current reactions: {n_reactions} / Target: {min_react}")

            # 2. Check if we hit the exact threshold
            if n_reactions == min_react:
                logger.info("Threshold reached! Fetching original message...")

                source_channel = self.get_channel(payload.channel_id)
                if not source_channel:
                    logger.error(f"Could not find source channel {payload.channel_id} in cache.")
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

                # 3. Build Embed
                description = f"{message.content}\n\n**[Jump to message!]({message.jump_url})**"
                embed = EmbedFactory.create_embed(
                    description=description,
                    colour=discord.Color.gold(),
                    timestamp=True
                )

                avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
                embed.set_author(name=message.author.display_name, icon_url=avatar_url)

                # Extract first image attachment if it exists
                if message.attachments:
                    for attachment in message.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in
                               ['png', 'jpg', 'jpeg', 'gif', 'webp']):
                            embed.set_image(url=attachment.url)
                            logger.info("Image attachment found and added to embed.")
                            break

                # 4. Fetch Announce Channel and Send
                # 4. Fetch Board Channel from BoardSystem
                channel_id = board_system.get_board_channel(payload.guild_id)
                logger.info(f"Board Channel ID found: {channel_id}")

                if channel_id:
                    channel = self.get_channel(channel_id)

                    if channel:
                        sent_msg = await channel.send(
                            content=f"get a load of this chud...", embed=embed)
                        logger.info("Successfully sent featured message to board channel!")

                        board_system.add_boarded(payload.message_id, sent_msg.id)
                        logger.info(f"Saved to DB: Original {payload.message_id} -> Board {sent_msg.id}")
                    else:
                        logger.error(f"Board channel {channel_id} not found in bot's cache.")
                else:
                    logger.warning("No board channel set for this guild. Use /setboard to set it.")
            else:
                logger.info("Threshold not met (or already surpassed), skipping embed creation.")

        # --- Role Logic ---
        role_data = roles_system.get_role(payload.message_id, emoji_id)
        if role_data:
            role_id = role_data[0] if isinstance(role_data, tuple) else role_data
            try:
                server: discord.Guild = self.get_guild(payload.guild_id) or await self.fetch_guild(payload.guild_id)
                role: discord.Role = server.get_role(role_id) or await server.fetch_role(role_id)

                if role:
                    await payload.member.add_roles(role)
                    logger.info(f"Successfully added role: {role.name}")
            except Exception as e:
                logger.error(f"Failed to add role. Error: {e}")

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        logger.info(f"Payload: {payload}")
        if payload.user_id == self.user.id:
            return

        emoji_id = payload.emoji.id or payload.emoji.name

        guild: discord.Guild = await self.fetch_guild(payload.guild_id)

        try:
            member: discord.Member = await guild.fetch_member(payload.user_id)
        except discord.NotFound:
            logger.warning(f"Member not found in guild {guild.id} for user ID {payload.user_id}")
            return

        logger.info(f"Received reaction: {emoji_id} by {member.name}")


        # emoji filter
        # todo: use emoji from board_config
        target_emoji_id = 1517325122363592867

        if payload.emoji.id == target_emoji_id:
            # 1. Recupera l'ID del messaggio della board PRIMA di rimuovere la riga dal DB
            board_message_id = board_system.get_boarded(payload.message_id)
            if isinstance(board_message_id, tuple):
                board_message_id = board_message_id[0]

            # 2. Rimuovi la reazione dal database (potrebbe eliminare la riga se arriva a 0)
            board_system.remove_reaction(payload.message_id)

            # 3. Controlla le reazioni rimaste
            reactions = board_system.get_reactions(payload.message_id)
            min_react = board_system.get_min_reactions(payload.guild_id)

            # 4. Calcola il numero effettivo di reazioni
            current_reactions = 0
            if reactions is not None:
                current_reactions = reactions[0] if isinstance(reactions, tuple) else reactions

            # Se le reazioni scendono sotto il minimo, elimina il messaggio dalla board
            # Se le reazioni scendono sotto il minimo, elimina il messaggio dalla board
            if current_reactions < min_react:
                if board_message_id:
                    # FETCH BOARD CHANNEL
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


        
        role_data = roles_system.get_role(payload.message_id, emoji_id)
        if not role_data:
            logger.warning(f"No role mapping found for message ID {payload.message_id} and emoji {emoji_id}")
            return
        
        role_id = role_data[0]

        try:
            role: discord.Role = await guild.fetch_role(role_id)
        except discord.NotFound:
            logger.warning(f"Role with ID {role_id} not found in guild {guild.id}")
            return

        await member.remove_roles(role)

        logger.info(f"Removed role: {role.name} from {member.name}")

bot = DiscordBot()
channel = None


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
        embed = EmbedFactory.create_embed(
            title="Stopped.",
            description="🟥 The bot has been stopped!",
            colour=discord.Color.red(),
            author=False
        )

        await bot.announce_channel.send(embed=embed)
        logger.info("Bot has shut down!")



if __name__ == "__main__":
    asyncio.run(main())
