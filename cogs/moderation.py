import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
from utils.embed_factory import EmbedFactory
from utils.debug import Logger
from utils.moderation_system import ModerationSystem
import os
from config import GUILD_ID

# Initialize logger
logger = Logger(os.path.basename(__file__).replace(".py", ""))

def parse_duration(duration_str: str) -> timedelta:
    """
    Parses a duration string and returns a corresponding timedelta.

    Args:
        duration_str (str): The duration string (e.g., '10m', '2h').

    Returns:
        timedelta: A timedelta object representing the parsed duration.
    
    Raises:
        ValueError: If the duration string format is invalid.
    """
    try:
        num = int(duration_str[:-1])  # Extract the number
        unit = duration_str[-1]  # Extract the unit
        return timedelta(**{
            's': {'seconds': num},
            'm': {'minutes': num},
            'h': {'hours': num},
            'd': {'days': num}
        }.get(unit, {}))
    except Exception as e:
        logger.error(f"Error parsing duration '{duration_str}': {e}")
        raise ValueError(f"Invalid duration format: {duration_str}") from e

class Moderation(commands.Cog):
    """
    Cog to handle moderation commands such as temp banning, unbanning, and kicking users.
    """

    def __init__(self, bot):
        """
        Initializes the Moderation cog.

        Args:
            bot (discord.Bot): The bot instance.
        """
        self.bot = bot
        self.db = ModerationSystem(
            host="localhost",
            user="root",
            password="luca",
            database="discordbot"
        )
        self.next_unban_time = None
        self.unban_task = self.bot.loop.create_task(self._update_next_unban_time())

    @app_commands.command(name="tempban", description="Temporarily ban a user.")
    @app_commands.describe(
        member="Member to ban.",
        reason="Reason for the ban.",
        duration="Duration in format <number><unit> (s=seconds, m=minutes, h=hours, d=days)."
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def tempban(
            self,
            interaction: discord.Interaction,
            member: discord.Member,
            duration: str,
            reason: str = "No reason"):
        """
        Temporarily bans a user for a specified duration.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            member (discord.Member): The member to ban.
            duration (str): The duration for which the user is banned (e.g., '1h').
            reason (str, optional): The reason for the ban.
        """
        logger.info(f"Temp banning user {member.id} ({member.name}) for {duration} due to {reason}")
        
        try:
            delta = parse_duration(duration)
        except Exception as e:
            logger.error(f"Failed to parse duration '{duration}': {e}")
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                description="❌ Invalid duration format.",
                title="Error!",
                colour=discord.Color.red(),
                author="Moderation"
            )
            await interaction.response.send_message(embed=embed)
            return

        unban_time = datetime.utcnow() + delta
        await member.ban(reason=reason)
        logger.info(f"Banned user {member.id} ({member.name}) for {duration}. Unban scheduled at {unban_time}")
        
        await asyncio.to_thread(self.db.tempban, member.id, interaction.guild_id, reason, unban_time)
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
        """
        Updates the next unban time from the database and schedules the unban task.
        """
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban
            delay = (unban_time - datetime.utcnow()).total_seconds()

            logger.info(f"Next unban scheduled for user {user_id} in guild {guild_id} at {unban_time}. Delay: {delay}s")
            
            if delay > 0 and (self.next_unban_time is None or unban_time < self.next_unban_time):
                self.next_unban_time = unban_time

                if self.unban_task:
                    self.unban_task.cancel()

                self.unban_task = self.bot.loop.create_task(self._unban_after_delay(delay))
                logger.info(f"Unban task scheduled to run after {delay}s")

    async def _unban_after_delay(self, delay: float):
        """
        Unbans a user after a specified delay.

        Args:
            delay (float): The delay in seconds before the unban.
        """
        logger.info(f"Sleeping for {delay} seconds before unbanning the user.")
        await asyncio.sleep(delay)
        await self._unban_user()

    async def _unban_user(self):
        """
        Unbans the user whose temporary ban has expired.
        """
        next_ban = await asyncio.to_thread(self.db.fetch_next_unban)

        if next_ban:
            user_id, guild_id, unban_time = next_ban
            guild = self.bot.get_guild(guild_id)

            if guild:
                try:
                    user = await self.bot.fetch_user(user_id)
                    await guild.unban(user, reason="Temporary ban expired.")
                    logger.info(f"User {user_id} has been unbanned in guild {guild_id}")
                except discord.NotFound:
                    logger.warning(f"User with ID {user_id} not found for unban in guild {guild_id}.")
                    pass

        await asyncio.to_thread(self.db.delete_expired_bans)
        await self._update_next_unban_time()

    @app_commands.command(name="pardon", description="Pardon a temporarily banned user.")
    @app_commands.describe(user="User to pardon.", reason="Reason for the pardon.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def pardon(self, interaction: discord.Interaction, user: discord.User, reason: str = ""):
        """
        Pardons a user by removing their temporary ban.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            user (discord.User): The user to pardon.
            reason (str, optional): The reason for the pardon.
        """
        logger.info(f"Pardoning user {user.id} ({user.name}) in guild {interaction.guild.id} for reason: {reason}")
        
        removed = await asyncio.to_thread(self.db.pardon, user.id, interaction.guild.id)

        if not removed:
            logger.warning(f"No active tempban found for user {user.id} ({user.name}) in guild {interaction.guild.id}")
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
            logger.info(f"User {user.id} ({user.name}) has been unbanned in guild {guild.id}.")
        except discord.NotFound:
            logger.warning(f"User {user.id} not found for unban in guild {guild.id}.")
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

    @app_commands.command(name="kick", description="Kick a user.")
    @app_commands.describe(member="Member to kick.", reason="Reason for the kick.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = ""):
        """
        Kicks a user from the server.

        Args:
            interaction (discord.Interaction): The interaction that triggered the command.
            member (discord.Member): The member to kick.
            reason (str, optional): The reason for the kick.
        """
        logger.info(f"Kicking user {member.id} ({member.name}) from guild {interaction.guild.id} for reason: {reason}")
        
        await member.kick(reason=reason)

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"⛔ You've kicked {member.name}",
            title="Kicked!",
            thumbnail=member.avatar.url,
            colour=discord.Color.red(),
            author="Moderation"
        )
        embed.add_field(name="Reason", value=reason)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delete", description="Delete messages.")
    @app_commands.describe(number="Number of messages to be deleted", member="User")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(GUILD_ID)
    async def delete(self, interaction: discord.Interaction, number: int = None, member: discord.Member = None):
        """
        Delete n messages from an user.
        When number is "None", delete all messages
        When user isn't specified, remove every message no matter who the user is
        """
        logger.info(f"Delete {number} messages")
        
        messages = [message async for message in interaction.channel.history(limit = number)]
        
        n = 0

        for message in messages:
            if message.author == member or member == None:
                await message.delete()
                n += 1

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            description=f"You've deleted {n} message(s) {f"from {member.mention}" if member != None else ""}",
            title="Deleted messages!",
            thumbnail= member.avatar.url if member != None else interaction.user.avatar.url,
            colour=discord.Colour.red(),
            author="Moderation"
        )
        
        await interaction.response.send_message(embed=embed)



async def setup(bot):
    await bot.add_cog(Moderation(bot))
