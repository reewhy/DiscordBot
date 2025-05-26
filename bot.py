import asyncio
from dataclasses import dataclass
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
            await self.add_cog(Channel(self, server_system))
            logger.info("Loaded extension: cogs.channel")
        except Exception as e:
            logger.error(f"Failed to load extension", exc_info=e)

        try:
            for id in GUILD_ID:
                await self.tree.sync(guild=id)
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


            self.announce_channel = self.get_channel(1247283014480691272)
            self.level_channel = self.get_channel(1376557487880142951)


            embed = EmbedFactory.create_embed(
                title="Ready!",
                description="🟩 The bot is ready to use!",
                colour=discord.Color.green(),
                author=False
            )
            await self.announce_channel.send(embed=embed)
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
            role_id = server_system.get_role(guild_id)
            role = await member.guild.fetch_role(role_id)
            await member.add_roles(role)
        except:
            logger.warning(f"No role found.")

        embed = discord.Embed(
            colour=discord.Color.brand_green(),
            title=f"{member.name} si è unito a {member.guild.name} 🎉",
            description=description.replace("%u", f"{member.mention}")
        )

        #        
        channels = server_system.get_channels(guild_id)
        print(channels)

        for channel_id, description in channels:
            channel = self.get_channel(channel_id)
            embed.add_field(name=description, value=channel.mention, inline=False)
        #embed.add_field(name="Leggi le regole", value=self.rules[guild_id].mention, inline=False)
        #embed.add_field(name="Presentati alla community", value=self.presentations[guild_id].mention, inline=False)

        embed.set_thumbnail(url=member.avatar.url)
        
        embed.set_image(url="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExdmF2MTc2YjBxamZ3aXdvMnF6cGdrc2s1dDR1YnR3aGVqb2c2Yjd3bSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/ExMGjbktr4phe/giphy.gif")
        
        channel_id = server_system.get_announce_channel(guild_id)[0]
        channel = self.get_channel(channel_id)
        
        if channel:
            await channel.send(embed=embed, content="||everyone||") 

    
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
        logger.info(f"Payload: {payload}")
        if payload.member.bot:
            return

        emoji_id = payload.emoji.id or payload.emoji.name

        logger.info(f"Received reaction: {emoji_id} by {payload.member.name}")
        
        
        role_id = roles_system.get_role(payload.message_id, emoji_id)[0]
        server : discord.Guild = await self.fetch_guild(payload.guild_id)
        role : discord.Role = await server.fetch_role(role_id)

        await payload.member.add_roles(role)

        logger.info(f"Fetched role: {role.name}")

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
