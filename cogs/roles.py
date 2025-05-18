import re
import discord
from discord.ext import commands
import random
from discord import app_commands
import __future__
from config import GUILD_ID
from utils import roles_system
from utils.debug import Logger
from utils.embed_factory import EmbedFactory

import os

from utils.roles_system import RoleSystem

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class Roles(commands.Cog):
    def __init__(self, bot, role_system: RoleSystem):
        self.bot = bot
        self.role_system = role_system
        self.bot.tree.add_command(self.MessageCommands(self.role_system))
    
    @app_commands.guilds(GUILD_ID)
    @app_commands.checks.has_permissions(administrator=True)
    class MessageCommands(app_commands.Group):
        """
        Group of commands related to self-roles integration
        """
        def __init__(self, role_system: RoleSystem):
            super().__init__(name="message", description="Manage role messages")
            self.role_system = role_system
            self.add_command(self.RoleSpecific(self.role_system))
            logger.info("Loaded command group: RoleCommands")
        

        @app_commands.command(name="create", description="Create a new role message.")
        @app_commands.guilds(GUILD_ID)
        @app_commands.describe(title="Title of the role message", description="Custom description")
        @app_commands.checks.has_permissions(administrator=True)
        async def create(self, interaction: discord.Interaction, title: str, description: str):
            logger.info("Create a new self-role message")
            
            embed = EmbedFactory.create_embed(
                title = title,
                description=description,
                colour=discord.Color.random(),
                author="Role System",
            )

            interaction_callback = await interaction.response.send_message(embed=embed)
    
            self.role_system.create_message(interaction_callback.message_id)
        
        @app_commands.guilds(GUILD_ID)
        @app_commands.checks.has_permissions(administrator=True)
        class RoleSpecific(app_commands.Group):
            def __init__(self, role_system: RoleSystem):
                super().__init__(name="role", description="Manage roles for messages.")
                self.role_system = role_system
                logger.info("Loaded command group: RoleSpecific")

            @app_commands.command(name="add", description="Add new role to a message.")
            @app_commands.guilds(GUILD_ID)
            @app_commands.checks.has_permissions(administrator=True)
            @app_commands.describe(
                message="Message you want to add role to.",
                role="Role you want to add.",
                emoji="Emoji to identify said role."
            )
            async def add(self, interaction: discord.Interaction, message: str, role: discord.Role, emoji: str):
                await interaction.response.defer()
                emoji_id = None
                match = re.match(r'<a?:\w+:(\d+)>', emoji)
                if match:
                    emoji_id = int(match.group(1))

                try:
                    partial = discord.PartialEmoji.from_str(emoji)
                    if partial.id != None:
                        emoji_id = partial.id
                    else:
                        emoji_id = partial.name
                except Exception as e:
                    logger.error("Error adding role: ", exc_info=e)
                    await interaction.response.send_message("Error")
                
                if emoji_id == None:
                    emoji_id = emoji

                try:
                    self.role_system.add_role(
                        message,
                        role.id,
                        emoji_id
                        )
                    

                    msg = await interaction.channel.fetch_message(message)

                    await msg.add_reaction(emoji)

                    embed = EmbedFactory.create_embed(
                        title="Successo!",
                        description=f"`{emoji}` {role.mention} has been added!",
                        colour=discord.Color.green(),
                        author="Role System"
                    )

                    await interaction.followup.send(embed=embed, ephemeral=True)
                except Exception as e:
                    embed = EmbedFactory.create_embed(
                        title="Error",
                        colour=discord.Color.red(),
                        description=e,
                        author="Role System"
                    )
                    await interaction.followup.send(embed=embed)
                    logger.error("Error in role syste: ", exc_info=e)

            @app_commands.command(name="reset", description="Reset all roles.")
            @app_commands.guilds(GUILD_ID)
            @app_commands.checks.has_permissions(administrator=True)
            async def reset(self, interaction: discord.Interaction):

                self.role_system.reset()

                embed = EmbedFactory.create_embed(
                    title="Reset roles!",
                    description="Reset all the roles.",
                    colour=discord.Color.red(),
                    author="Role System",
                    thumbnail=interaction.user.avatar.url
                )

                await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Roles(bot))
