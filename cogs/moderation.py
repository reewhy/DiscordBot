from datetime import timedelta
import re
import discord
from discord.ext import commands
import random
from discord import app_commands
from discord.utils import utcnow

from config import GUILD_ID
from utils import embed_factory
from utils.debug import Logger
from utils.embed_factory import EmbedFactory
import os
import asyncio
from datetime import datetime

from utils.moderation_system import ModerationSystem

logger = Logger(os.path.basename(__file__).replace(".py",""))

def parse_duration(duration_str):
    num = int(duration_str[:-1])
    unit = duration_str[-1]
    return timedelta(**{
        's': { 'seconds': num },
        'm': { 'minutes': num},
        'h': { 'hours': num},
        'd': { 'days': num}
    }.get(unit, {}))

# All cogs need to inherit the class commands.Cog
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ModerationSystem(
            host="localhost",
            user="root",
            password="",
            database="discordbot"
        )
        self.next_unban_time = None
        self.unban_task = self.bot.loop.create_task(self._update_next_unban_time())

    
    # This line sets a name for a command and its description
    @app_commands.command(name="tempban", description="Tempban an user.")
    # Describes parameters
    @app_commands.describe(
        member="Member to ban.",
        reason="Reason why they're being banned.",
        duration="Duration in format <number><unit> (s=seconds, m=minutes, h=hours, d=days)."
    )
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def tempban(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            duration: str,
            reason: str = "No reason"):
        try:
            delta = parse_duration(duration)
        except Exception:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"❌ Invalid duration format.",
                title="Error!",
                colour=discord.Color.red(),
                author="Moderation"
            )

            await interaction.response.send_message(embed=embed)
            return

        unban_time= datetime.utcnow() + delta
        await member.ban(reason=reason)

        await asyncio.to_thread(
            self.db.tempban,
            member.id,
            interaction.guild_id,
            reason,
            unban_time
        )

        await self._update_next_unban_time()

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"🔨 {member.mention} has been temporarily banned for `{duration}`",
            title="Banned!",
            thumbnail=member.avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )

        embed.add_field(name="📝 Reason", value=reason)

        await interaction.response.send_message(embed=embed)

    async def _update_next_unban_time(self):
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban
            delay = (unban_time - datetime.utcnow()).total_seconds()

            if delay > 0 and (self.next_unban_time is None or unban_time < self.next_unban_time):
                self.next_unban_time = unban_time

                if self.unban_task:
                    self.unban_task.cancel()

                self.unban_task = self.bot.loop.create_task(self._unban_after_delay(delay))

    async def _unban_after_delay(self, delay: float):
        await asyncio.sleep(delay)
        await self._unban_user()

    async def _unban_user(self):
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban

            guild = self.bot.get_guild(guild_id)

            if guild:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await guild.unban(user, reason="Temporary ban expired.")
                except discord.NotFound:
                    pass

        await asyncio.to_thread(self.db.delete_expired_bans)
        await self._update_next_unban_time()

    
    # This line sets a name for a command and its description
    @app_commands.command(name="pardon", description="Pardon an user.")
    # Describes parameters
    @app_commands.describe(user="Member to pardon.", reason="Reason why they're being unbanned.")
    # Specify permissions
    @app_commands.checks.has_permissions(administrator=True)
    # Specify in which server you want to activate your bot
    @app_commands.guilds(GUILD_ID)
    async def pardon(self, interaction: discord.Interaction, user: discord.User, reason: str = ""):
        removed = await asyncio.to_thread(self.db.pardon, user.id, interaction.guild.id)

        if not removed:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description=f"⚠️ No active tempban found for {user.mention}.",
                title="Error",
                thumbnail=user.avatar.url,
                colour=discord.Color.yellow(),
                author="Moderation"
            )

            await interaction.response.send_message(embed=embed)
            return

        guild = interaction.guild
        
        try:
            await guild.unban(user, reason=reason)
        except discord.NotError:
            pass

        await self._update_next_unban_time()
         
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
