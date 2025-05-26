import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils.debug import Logger

import os

from utils.embed_factory import EmbedFactory
from utils.server_system import ServerSystem

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class Channel(commands.Cog):
    def __init__(self, bot, server_system: ServerSystem):
        self.bot = bot
        self.server_system = server_system
        self.bot.tree.add_command(self.Set(server_system, bot))
        self.bot.tree.add_command(self.Role(server_system, bot))
    
    @app_commands.command(name="onjoin", description="Set a role on join.")
    @app_commands.guilds(*GUILD_ID)
    @app_commands.describe(role="Role to add on join")
    async def role(self, interaction: discord.Interaction, role: discord.Role):
        try:
            self.server_system.set_role(interaction.guild_id, role.id)
        except Exception as e:
            embed = EmbedFactory.create_embed(
                title="Errore",
                description=e,
                colour=discord.Color.red(),
                interaction=interaction,
                author="Server System"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedFactory.create_embed(
            title="Success!",
            description="You've successfully set the new on join role",
            colour=discord.Color.green(),
            interaction=interaction,
            author="Server System"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guilds(*GUILD_ID)
    class Role(app_commands.Group):
        def __init__(self, server_system: ServerSystem, bot: commands.Bot):
            super().__init__(name="role", description="Role levels settings.")
            self.server_system = server_system
            self.bot = bot

        @app_commands.command(name="set", description="Set a new role level.")
        @app_commands.guilds(*GUILD_ID)
        @app_commands.describe(role="Role you want to set",level="Level of the role")
        async def set(self, interaction: discord.Interaction, role: discord.Role, level: int):
            try:
                self.server_system.add_role(interaction.guild_id, role.id, level)
            except Exception as e:
                embed = EmbedFactory.create_embed(
                    title="Error",
                    description=e,
                    colour=discord.Color.red(),
                    interaction=interaction,
                    author="Server System"
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = EmbedFactory.create_embed(
                title="Level role succesfully created!",
                description=f"You've successfully set {role.mention} for level: {level}",
                colour=discord.Color.green(),
                interaction=interaction,
                author="Server System"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guilds(*GUILD_ID)
    class Set(app_commands.Group):
        def __init__(self, server_system: ServerSystem, bot: commands.Bot):
            super().__init__(name="channel", description="Set server channels.")
            self.server_system = server_system
            self.bot = bot
            logger.info("Loaded command group: Set")

        @app_commands.command(name="level", description="Set this channel as level channel.")
        @app_commands.guilds(*GUILD_ID)
        async def level(self, interaction: discord.Interaction):
            self.server_system.add_channel(interaction.guild_id, interaction.channel_id, "level")
            
            embed = EmbedFactory.create_embed(
                title="Level channel set",
                description=f"You've set {interaction.channel.mention} as level channel.",
                colour=discord.Color.green(),
                author="Server System",
                interaction=interaction
            )

            logger.info(f"{interaction.channel.name} set a level channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="announcements", description="Set this channel as announcements channel.")
        @app_commands.guilds(*GUILD_ID)
        async def announcements(self, interaction: discord.Interaction):
            self.server_system.add_channel(interaction.guild_id, interaction.channel_id, "announce")
            embed = EmbedFactory.create_embed(
                title="Announcements channel set",
                description=f"You've set {interaction.channel.mention} as announcements channel.",
                colour=discord.Color.green(),
                author="Server System",
                interaction=interaction
            )

            logger.info(f"{interaction.channel.name} set as announcements channel.")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="add", description="Add a new channel, the channel added will be shown in announcements.")
        @app_commands.describe(description="Description of added channel")
        @app_commands.guilds(*GUILD_ID)
        async def add(self, interaction: discord.Interaction, description: str, channel: discord.TextChannel = None):
            self.server_system.add_channel(interaction.guild_id, interaction.channel_id if channel == None else channel.id, description)
            embed = EmbedFactory.create_embed(
                title="New channel added!",
                description=f"You've added {interaction.channel.mention} to the channel list.",
                colour=discord.Color.green(),
                author="Server System",
                interaction=interaction
            )
            embed.add_field(name="Description", value=description)
            logger.info(f"{interaction.channel.name} has been added to server description.")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.command(name="announce", description="Announce something in announcement chat.")
        @app_commands.describe(value="Message to announce", title="Title of the announcement", author="Author of the announcemnt")
        @app_commands.guilds(*GUILD_ID)
        async def announce(self, interaction: discord.Interaction, title: str, value: str, author: str = "Server System"):
            channel_id = self.server_system.get_announce_channel(interaction.guild_id)

            embed = EmbedFactory.create_embed(
                title=title,
                description=value,
                colour=discord.Color.random(),
                author=author,
                interaction=interaction
            )

            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

        @app_commands.command(name="description", description="Set server description, %u = user mention")
        @app_commands.describe(value="Description for the join message")
        @app_commands.guilds(*GUILD_ID)
        async def desc(self, interaction: discord.Interaction, value: str):
            self.server_system.set_description(interaction.guild_id, value)

            embed = EmbedFactory.create_embed(
                title="New description set",
                description="You've changed the welcome message description",
                colour=discord.Color.green(),
                author="Server System",
                interaction=interaction
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Channel(bot))
