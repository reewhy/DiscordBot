import asyncio
import discord
from discord.ext import commands
import config
from config import GUILD_ID
from utils.debug import Logger
import os

<<<<<<< HEAD
from utils.embed_factory import EmbedFactory

=======
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211
# Initilize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

intents = discord.Intents.default()
intents.message_content = True

<<<<<<< HEAD
initial_extensions = [
    "cogs.basic",
    "cogs.embed",
    "cogs.group_commands"
]

=======
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211
class DiscordBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.PREFIX, intents=intents)

    async def setup_hook(self):
        # List here all your cogs, they will be automatically loaded
<<<<<<< HEAD
=======
        initial_extensions = ['cogs.basic', 'cogs.group_commands']
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211
        for ext in initial_extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}", exc_info=e)

        try:
            await self.tree.sync(guild=GUILD_ID)
            logger.info("Slash commands synced successfully")
        except Exception as e:
            logger.error("Failed to sync slash commands", exc_info=e)

bot = DiscordBot()
<<<<<<< HEAD
channel = None
=======
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211

@bot.event
async def on_ready():
    logger.info(f"We have logged in as {bot.user.name} (ID: {bot.user.id}")
    logger.info(f"Connected to {len(bot.guilds)} guild(s)")

    try:
        # Setup here your custom presence on ready
        await bot.change_presence(
            status = discord.Status.online,
            activity=discord.Game(name="witchcraft")
        )
        logger.info("Presence updated successfully")
<<<<<<< HEAD

        bot.announce_channel = bot.get_channel(1247283014480691272)

        embed = EmbedFactory.create_embed(
            title="Ready!",
            description="🟩 The bot is ready to use!",
            colour=discord.Color.green(),
            author=False
        )

        await bot.announce_channel.send(embed=embed)
=======
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211
    except Exception as e:
        logger.error("Failed to update presence", exc_info=e)


async def main():
    try:
        logger.info("Starting bot...")
        async with bot:
            await bot.start(config.TOKEN)
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
<<<<<<< HEAD

        
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
        
=======
    except Exception as e:
        logger.critical("Bot crashed!", exc_info=e)
    finally:
        logger.info("Bot has shut down!")
>>>>>>> e82461cfcd6e0033cce26ce7be5751c1c42ec211


if __name__ == "__main__":
    asyncio.run(main())
