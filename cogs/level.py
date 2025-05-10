from dis import disco
import dis
from enum import member
import discord
from discord import app_commands, permissions
from discord.ext import commands
from config import GUILD_ID
from utils.level_system import LevelSystem
from utils.embed_factory import EmbedFactory
import __future__
from utils.debug import Logger
import os

# Initilize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

class LevelCog(commands.Cog):
    """
        Cogs for commands used to manage the level system in the server.
    """
    def __init__(self, bot, level_system: LevelSystem):
        """
        Constructor for the cog

        Args:
            bot (discord.Bot): The bot object.
            level_system (LevelSystem): The level system instance.
        """
        self.bot = bot
        self.level_system = level_system
        self.bot.tree.add_command(self.LevelSet(level_system))
        self.bot.tree.add_command(self.LevelAdd(level_system))

    @app_commands.command(name="level", description="Check your level or someone else's.")
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(member="Member to check.")
    async def level(self, interaction: discord.Interaction, member: discord.Member = None):
        """
        Command to retrieve member level.

        Args:
            interaction (discord.interaction): Discord interaction with user.
            member (Optional[discord.Member]): Discord member you want to see the level of. 
        """
        # Either take the member given as parameter or the message author
        member = member or interaction.user
        data = self.level_system.get_user(member.id, interaction.guild_id)
        if data:
            xp, level = data

            embed = EmbedFactory.create_embed(
                title = "Level check",
                description=f"{member.mention} is level {level} ({xp} XP).",
                author="Level",
                thumbnail=member.avatar.url,
                interaction=interaction
            )

            await interaction.response.send_message(embed=embed)
        else:
            embed = EmbedFactory.create_embed(
                title="Error",
                description=f"{member.mention} has no level data yet.",
                author="Level",
                thumbnail=member.avatar.url, 
                colour=discord.Color.red(),
                interaction=interaction
            )

            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset", description="Reset user level.")
    @app_commands.guilds(GUILD_ID)
    @app_commands.describe(member="Member to reset.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, member: discord.Member):
        """
        Command to reset an user level. Need to have admin permission.

        Args:
            interaction (discord.interaction): Discord interaction with user.
            member (discord.Member): Member to reset.
        """
        result = self.level_system.reset_level(member.id, interaction.guild.id)

        if result:
            embed = EmbedFactory.create_embed(
                title="Level reset",
                description=f"You successfully reset {member.mention} level.",
                author="Level",
                thumbnail=member.avatar.url,
                colour=discord.Color.red(),
                interaction=interaction
            )

            await interaction.response.send_message(embed=embed)
        else:
            embed = EmbedFactory.create_embed(
                title="Error",
                description=f"{member.mention} has no level data yet.",
                author="Level",
                thumbnail=member.avatar.url,
                colour=discord.Color.red(),
                interaction=interaction
            )

            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(GUILD_ID)
    @app_commands.checks.has_permissions(administrator=True)
    class LevelSet(app_commands.Group):
        """
        Command group with level system setter wrappers. Need to have admin permission.

        Attributes:
            level_system (LevelSystem): Instance of the level system.
        """
        def __init__(self, level_system: LevelSystem):
            super().__init__(name="set", description="Set user level or xp.")
            self.level_system = level_system
            logger.info("Loaded command group in cogs.level: LevelSet")
        
        @app_commands.command(name="xp", description="Set user xp.")
        @app_commands.guilds(GUILD_ID)
        @app_commands.describe(member="Member to change.", value="New XP value.")
        @app_commands.checks.has_permissions(administrator=True)
        async def xp(
                self,
                interaction: discord.Interaction,
                member: discord.Member,
                value: int
        ):
            """
            Command to set user XP. Need to have admin permission.

            Args:
                interaction (discord.Interaction): Discord interaction with user.
                member (discord.Member): Member to modify.
                value (int): New value for the XP.
            """
            level = self.level_system.set_xp(member.id, interaction.guild.id, value)
            xp, user_level = self.level_system.get_user(member.id, interaction.guild.id)

            embed = EmbedFactory.create_embed(
                title="XP changed!",
                description=f"You changed {member.mention}'s XP.",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=member.avatar.url,
                interaction=interaction
            )

            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="level", description="Set user level.")
        @app_commands.guilds(GUILD_ID)
        @app_commands.describe(member="Member to change.", value="New level value.")
        @app_commands.checks.has_permissions(administrator=True)
        async def level(
                self,
                interaction: discord.Interaction,
                member: discord.Member,
                value: int
        ):
            """
            Command to set user Level. Need to have admin permission.

            Args:
                interaction (discord.Interaction): Discord interaction with user.
                member (discord.Member): Member to modify.
                value (int): New value for the Level.
            """
            level = self.level_system.set_level(member.id, interaction.guild.id, value)
            xp, user_level = self.level_system.get_user(member.id, interaction.guild.id)

            embed = EmbedFactory.create_embed(
                title="Level changed!",
                description=f"You changed {member.mention}'s Level.",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=member.avatar.url,
                interaction=interaction
            )

            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(GUILD_ID)
    @app_commands.checks.has_permissions(administrator=True)
    class LevelAdd(app_commands.Group):
        """
        Command group with level system add function wrappers. Need to have admin permission.

        Attributes:
            level_system (LevelSystem): Instance of the level system.
        """
        def __init__(self, level_system: LevelSystem):
            super().__init__(name="add", description="Add an amount to user level or xp.")
            self.level_system = level_system
            logger.info("Loaded command group in cogs.level: LevelAdd")
        
        @app_commands.command(name="xp", description="Add user xp.")
        @app_commands.guilds(GUILD_ID)
        @app_commands.describe(member="Member to change.", value="Amount of XP to add.")
        @app_commands.checks.has_permissions(administrator=True)
        async def xp(
                self,
                interaction: discord.Interaction,
                member: discord.Member,
                value: int
        ):
            """
            Command to add an amount to user XP. Need to have admin permission.

            Args:
                interaction (discord.Interaction): Discord interaction with user.
                member (discord.Member): Member to modify.
                value (int): Amoun to add to XP.
            """
            level = self.level_system.add_xp(member.id, interaction.guild.id, value)
            xp, user_level = self.level_system.get_user(member.id, interaction.guild.id)

            embed = EmbedFactory.create_embed(
                title="XP added!",
                description=f"You added {value} to {member.mention}'s XP.",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=member.avatar.url,
                interaction=interaction
            )

            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            await interaction.response.send_message(embed=embed)

        @app_commands.command(name="level", description="Add level to user.")
        @app_commands.guilds(GUILD_ID)
        @app_commands.describe(member="Member to change.", value="Amount of levels to add.")
        @app_commands.checks.has_permissions(administrator=True)
        async def level(
                self,
                interaction: discord.Interaction,
                member: discord.Member,
                value: int
        ):
            """
            Command to add levels to user. Need to have admin permission.

            Args:
                interaction (discord.Interaction): Discord interaction with user.
                member (discord.Member): Member to modify.
                value (int): Amount of levels to add.
            """
            level = self.level_system.add_levels(member.id, interaction.guild.id, value)
            xp, user_level = self.level_system.get_user(member.id, interaction.guild.id)

            embed = EmbedFactory.create_embed(
                title="Levels added!",
                description=f"You added {value} to {member.mention}'s Level.",
                colour=discord.Color.yellow(),
                author="Level",
                thumbnail=member.avatar.url,
                interaction=interaction
            )

            embed.add_field(name="Level", value=user_level, inline=True)
            embed.add_field(name="XP", value=xp, inline=True)

            await interaction.response.send_message(embed=embed)

            
async def setup(bot):
    await bot.add_cog(LevelCog(bot))
