import asyncio
from dataclasses import dataclass
import discord
from discord.ext import commands
from cogs.level import LevelCog
import config
from config import GUILD_ID
from utils.debug import Logger
import os
from utils.level_system import LevelSystem
from utils.embed_factory import EmbedFactory

# Initilize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

intents = discord.Intents.all()
intents.message_content = True

level_system = LevelSystem(
    host="localhost",
    user="root",
    password="",
    database="discordbot"
)

initial_extensions = [
    "cogs.basic",
    "cogs.embed",
    "cogs.group_commands",
    "cogs.test"
]
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
        except Exception as e:
            logger.error(f"Failed to load extension cogs.level", exc_info=e)

        try:
            await self.tree.sync(guild=GUILD_ID)
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
        
        level = level_system.add_xp(message.author.id, message.guild.id, amount=10)
        xp, user_level = level_system.get_user(message.author.id, message.guild.id)

        if xp == 0:
            embed = EmbedFactory.create_embed(
                title="Level up!",
                description=f"🎉 {message.author.mention} just leveled up!",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=message.author.avatar.url
            )

            embed.add_field(name="New level", value=user_level, inline=True)

            await message.channel.send(embed=embed)

    async def on_member_join(self, member: discord.Member):
        logger.info(f"New member joined: {member.name}")
        embed = discord.Embed(
            colour=discord.Color.brand_green(),
            title=f"{member.name} si è unito a test 🎉",
            description=f"Benvenuto {member.mention}!\nTi diamo il benvenuto nel nostro magnifico server.\nSpero tu ti possa trovare a tuo agio."
        )

        embed.add_field(name="Leggi le regole", value="Canale1", inline=False)
        embed.add_field(name="Presentati alla community", value="Canale2", inline=False)
        embed.add_field(name="Personalizza il tuo profilo", value="Canale3", inline=False)
        embed.add_field(name="Per saperne di più sui bot del server", value="Canale4", inline=False)

        embed.set_thumbnail(url=member.avatar.url)
        
        embed.set_image(url="https://cdn-longterm.mee6.xyz/plugins/embeds/images/1086830286580494408/900984c478465dfea712df07398fb80a8b86fd47c1de24798c678a9fe403f835.gif")
        
        await self.announce_channel.send(embed=embed, content="||@everyone||") 

    
    async def on_member_leave(self, member: discord.Member):
        logger.info(f"Member left: {member.name}")
        embed = discord.Embed(
            colour=discord.Color.brand_red(),
            title=f"{member.name} ci ha abandonati 😢",
            description=f"Prima o poi si pentirà della sua scelta."
        )

        embed.set_thumbnail(url=member.avatar.url)
        
        embed.set_image(url="https://media1.tenor.com/m/JQZPRf0YTicAAAAd/emoji-in-distress-emoji-sad.gif")
        
        await self.announce_channel.send(embed=embed, content="||@everyone||")


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
