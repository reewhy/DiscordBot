import discord
from discord.ext import commands
import random
from discord import app_commands

from config import GUILD_ID
from utils import embed_factory
from utils.debug import Logger
from utils.embed_factory import EmbedFactory
import os

logger = Logger(os.path.basename(__file__).replace(".py",""))

# All cogs need to inherit the class commands.Cog
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # This line sets a name for a command and its description
    @app_commands.command(name="ban", description="Ban an user.")
    # Describes parameters
    @app_commands.describe(member="Member to ban.", reason="Reason why they're being banned.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = ""):
        await member.ban(reason=reason)
        
        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⛔ You've banned {member.name}",
            title="Banned!",
            thumbnail=member.avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )

        embed.add_field(name="Reason", value=reason)

        await interaction.response.send_message(embed=embed)

    
    # This line sets a name for a command and its description
    @app_commands.command(name="pardon", description="Pardon an user.")
    # Describes parameters
    @app_commands.describe(user="Member to pardon.", reason="Reason why they're being unbanned.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def unban(self, interaction: discord.Interaction, user: discord.User, reason: str = ""):
        await member.unban(reason=reason)
        
        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"☑️ You've pardoned {user.name}",
            title="Unbanned!",
            thumbnail=user.display_avatar.url,
            colour=discord.Color.green(),
            author="Moderation"
        )
            
        embed.add_field(name="Reason", value=reason)

        await interaction.response.send_message(embed=embed)

        
    
    # This line sets a name for a command and its description
    @app_commands.command(name="kick", description="Kick an user.")
    # Describes parameters
    @app_commands.describe(member="Member to kick.", reason="Reason why they're being kicked.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = ""):
        await member.kick(reason=reason)
        
        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⛔ You've kicked {member.name}",
            title="Banned!",
            thumbnail=member.avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )
        
        embed.add_field(name="Reason", value=reason)

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
