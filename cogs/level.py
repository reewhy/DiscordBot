import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID
from utils.level_system import LevelSystem
from utils.embed_factory import EmbedFactory
from utils.debug import Logger
import os

# Initialize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

class LevelCog(commands.Cog):
    """
    Cog for managing the level system of users in the server.

    This cog contains commands that allow users to check their level, 
    reset user levels, and modify user levels and XP. Only admins can 
    use the commands for setting or modifying levels and XP.
    """

    def __init__(self, bot, level_system: LevelSystem):
        """
        Initializes the LevelCog.

        Args:
            bot (discord.Bot): The bot object.
            level_system (LevelSystem): Instance of the level system to manage user levels and XP.
        """
        self.bot = bot
        self.level_system = level_system
        self.bot.tree.add_command(self.LevelSet(level_system))
        self.bot.tree.add_command(self.LevelAdd(level_system))

    @app_commands.command(name="level", description="Check your level or someone else's.")
    @app_commands.describe(member="Member to check.")
    @app_commands.guilds(*GUILD_ID)
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        """
        Command to retrieve a user's level and XP.

        If no member is specified, it will check the level of the user 
        who issued the command.

        Args:
            interaction (discord.Interaction): Discord interaction with the user.
            member (discord.Member, optional): The member whose level to check. Defaults to None, which checks the invoking user's level.
        """
        # Either take the member given as a parameter or the message author
        member = member or interaction.user
        data = self.level_system.get_user(member.id, interaction.guild_id)
        
        if data:
            xp, level = data
            embed = EmbedFactory.create_embed(
                title="Level Check",
                description=f"{member.mention} is level {level} ({xp} XP).",
                author="Level System",
                thumbnail=member.avatar.url,
                interaction=interaction,
                colour=discord.Color.green()
            )
            logger.info(f"Level check for {member}: {level} (XP: {xp})")
            await interaction.response.send_message(embed=embed)
        else:
            embed = EmbedFactory.create_embed(
                title="Error",
                description=f"{member.mention} has no level data yet.",
                author="Level System",
                thumbnail=member.avatar.url, 
                colour=discord.Color.red(),
                interaction=interaction
            )
            logger.warning(f"No level data for {member}.")
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset", description="Reset a user's level.")
    @app_commands.describe(member="Member to reset.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    async def reset(self, interaction: discord.Interaction, member: discord.Member):
        """
        Command to reset a user's level and XP. This requires admin permissions.

        Args:
            interaction (discord.Interaction): Discord interaction with the user.
            member (discord.Member): The member whose level to reset.
        """
        result = self.level_system.reset_level(member.id, interaction.guild.id)

        if result:
            embed = EmbedFactory.create_embed(
                title="Level Reset",
                description=f"You successfully reset {member.mention}'s level.",
                author="Level System",
                thumbnail=member.avatar.url,
                colour=discord.Color.orange(),
                interaction=interaction
            )
            logger.info(f"Level reset for {member}.")
            await interaction.response.send_message(embed=embed)
        else:
            embed = EmbedFactory.create_embed(
                title="Error",
                description=f"{member.mention} has no level data yet.",
                author="Level System",
                thumbnail=member.avatar.url,
                colour=discord.Color.red(),
                interaction=interaction
            )
            logger.warning(f"Failed to reset level for {member}. No data found.")
            await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    class LevelSet(app_commands.Group):
        """
        Group of commands for setting user levels and XP. Requires admin permissions.

        Attributes:
            level_system (LevelSystem): Instance of the level system to modify user levels and XP.
        """
        def __init__(self, level_system: LevelSystem):
            super().__init__(name="set", description="Set user level or XP.")
            self.level_system = level_system
            logger.info("Loaded command group: LevelSet")

        @app_commands.command(name="xp", description="Set a user's XP.")
        @app_commands.describe(member="Member to change.", value="New XP value.")
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        async def xp(self, interaction: discord.Interaction, member: discord.Member, value: int):
            """
            Command to set a user's XP. Requires admin permissions.

            Args:
                interaction (discord.Interaction): Discord interaction with the user.
                member (discord.Member): The member whose XP to set.
                value (int): The new XP value to set.
            """
            xp, user_level = self.level_system.set_xp(member.id, interaction.guild.id, value)
    
            embed = EmbedFactory.create_embed(
                title="XP Changed",
                description=f"You have set {member.mention}'s XP to {value}.",
                colour=discord.Color.blue(),
                author="Level System",
                thumbnail=member.avatar.url,
                interaction=interaction
            )
            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            logger.info(f"XP set for {member} to {value}.")
            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="level", description="Set a user's level.")
        @app_commands.describe(member="Member to change.", value="New level value.")
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        async def level(self, interaction: discord.Interaction, member: discord.Member, value: int):
            """
            Command to set a user's level. Requires admin permissions.

            Args:
                interaction (discord.Interaction): Discord interaction with the user.
                member (discord.Member): The member whose level to set.
                value (int): The new level value to set.
            """
            xp, user_level = self.level_system.set_level(member.id, interaction.guild.id, value)

            embed = EmbedFactory.create_embed(
                title="Level Changed",
                description=f"You have set {member.mention}'s level to {value}.",
                colour=discord.Color.blue(),
                author="Level System",
                thumbnail=member.avatar.url,
                interaction=interaction
            )
            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            logger.info(f"Level set for {member} to {value}.")
            await interaction.response.send_message(embed=embed)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    class LevelAdd(app_commands.Group):
        """
        Group of commands for adding XP or levels to users. Requires admin permissions.

        Attributes:
            level_system (LevelSystem): Instance of the level system to modify user levels and XP.
        """
        def __init__(self, level_system: LevelSystem):
            super().__init__(name="add", description="Add XP or levels to users.")
            self.level_system = level_system
            logger.info("Loaded command group: LevelAdd")

        @app_commands.command(name="xp", description="Add XP to a user.")
        @app_commands.describe(member="Member to change.", value="Amount of XP to add.")
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        async def xp(self, interaction: discord.Interaction, member: discord.Member, value: int):
            """
            Command to add XP to a user. Requires admin permissions.

            Args:
                interaction (discord.Interaction): Discord interaction with the user.
                member (discord.Member): The member to add XP to.
                value (int): The amount of XP to add.
            """
            xp, user_level = self.level_system.add_xp(member.id, interaction.guild.id, value)

            embed = EmbedFactory.create_embed(
                title="XP Added",
                description=f"You added {value} XP to {member.mention}.",
                colour=discord.Color.green(),
                author="Level System",
                thumbnail=member.avatar.url,
                interaction=interaction
            )
            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            logger.info(f"Added {value} XP to {member}.")
            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="level", description="Add levels to a user.")
        @app_commands.describe(member="Member to change.", value="Amount of levels to add.")
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        async def level(self, interaction: discord.Interaction, member: discord.Member, value: int):
            """
            Command to add levels to a user. Requires admin permissions.

            Args:
                interaction (discord.Interaction): Discord interaction with the user.
                member (discord.Member): The member to add levels to.
                value (int): The amount of levels to add.
            """
            xp, user_level = self.level_system.add_levels(member.id, interaction.guild.id, value)

            embed = EmbedFactory.create_embed(
                title="Levels Added",
                description=f"You added {value} levels to {member.mention}.",
                colour=discord.Color.green(),
                author="Level System",
                thumbnail=member.avatar.url,
                interaction=interaction
            )
            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            logger.info(f"Added {value} levels to {member}.")
            await interaction.response.send_message(embed=embed)


async def setup(bot):
    """
    Setup function to add the LevelCog to the bot.

    Args:
        bot (discord.Bot): The bot object.
    """
    await bot.add_cog(LevelCog(bot))
    logger.info("LevelCog successfully loaded.")
