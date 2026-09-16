import os
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import GUILD_ID
from utils.debug import Logger
from utils.embed_factory import EmbedFactory
from utils.roles_system import RoleSystem

logger = Logger(os.path.basename(__file__).replace(".py", ""))


class Roles(commands.Cog):
    def __init__(self, bot: commands.Bot, role_system: RoleSystem):
        self.bot = bot
        self.role_system = role_system
        self.bot.tree.add_command(self.MessageCommands(self.bot, self.role_system))

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(*GUILD_ID)
    class MessageCommands(app_commands.Group):
        def __init__(self, bot: commands.Bot, role_system: RoleSystem):
            super().__init__(name="message", description="Manage role messages")
            self.bot = bot
            self.role_system = role_system
            self.add_command(self.RoleSpecific(self.bot, self.role_system))

        @app_commands.command(
            name="multiselect",
            description="Enable or disable multiple role selection on a message."
        )
        @app_commands.describe(
            message_id="ID of the message",
            enabled="True for multiselect, False for single-choice only"
        )
        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        async def multiselect(self, interaction: discord.Interaction, message_id: str, enabled: bool):
            try:
                msg_id = int(message_id.strip())
            except ValueError:
                return await interaction.response.send_message("Invalid Message ID format.", ephemeral=True)

            self.role_system.set_multiselect(msg_id, enabled)
            mode_text = "Multiple roles allowed" if enabled else "Single role only (exclusive)"

            embed = EmbedFactory.create_embed(
                title="Multiselect Updated",
                description=f"Message `{msg_id}` selection mode set to: **{mode_text}**.",
                colour=discord.Color.green(),
                author="Role System"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        @app_commands.checks.has_permissions(administrator=True)
        @app_commands.guilds(*GUILD_ID)
        class RoleSpecific(app_commands.Group):
            def __init__(self, bot: commands.Bot, role_system: RoleSystem):
                super().__init__(name="role", description="Manage roles for messages.")
                self.bot = bot
                self.role_system = role_system

            @app_commands.command(
                name="add",
                description="Add a reaction role to an existing message."
            )
            @app_commands.describe(
                message_id="ID of the target message",
                emoji="Emoji to identify the role (Unicode or custom)",
                role="Role to give/remove",
                channel="Channel of the message (defaults to the current channel)"
            )
            @app_commands.checks.has_permissions(administrator=True)
            @app_commands.guilds(*GUILD_ID)
            async def add(
                self,
                interaction: discord.Interaction,
                message_id: str,
                emoji: str,
                role: discord.Role,
                channel: Optional[discord.TextChannel] = None
            ):
                await interaction.response.defer(ephemeral=True)

                try:
                    msg_id = int(message_id.strip())
                except ValueError:
                    return await interaction.followup.send("Message ID must be numeric.", ephemeral=True)

                target_channel = channel or interaction.channel
                try:
                    target_message = await target_channel.fetch_message(msg_id)
                except discord.NotFound:
                    return await interaction.followup.send(
                        f"Message `{msg_id}` was not found in {target_channel.mention}.", ephemeral=True
                    )
                except discord.Forbidden:
                    return await interaction.followup.send(
                        f"I lack permissions to read messages in {target_channel.mention}.", ephemeral=True
                    )

                # Parse emoji to determine identifier
                emoji_clean = emoji.strip()
                match = re.match(r'<a?:\w+:(\d+)>', emoji_clean)
                if match:
                    emoji_identifier = match.group(1)  # Custom emoji ID
                else:
                    try:
                        partial = discord.PartialEmoji.from_str(emoji_clean)
                        emoji_identifier = str(partial.id) if partial.id else partial.name
                    except Exception:
                        emoji_identifier = emoji_clean

                try:
                    # Save mapping in database
                    self.role_system.add_role(msg_id, role.id, emoji_identifier)

                    # Add reaction to message
                    await target_message.add_reaction(emoji_clean)

                    embed = EmbedFactory.create_embed(
                        title="Success!",
                        description=f"Reaction {emoji_clean} linked to {role.mention} on message `{msg_id}`.",
                        colour=discord.Color.green(),
                        author="Role System"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

                except discord.HTTPException as e:
                    embed = EmbedFactory.create_embed(
                        title="Discord Error",
                        description=f"Could not react with emoji: {e}",
                        colour=discord.Color.red(),
                        author="Role System"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except Exception as e:
                    logger.error("Error adding reaction role: ", exc_info=e)
                    embed = EmbedFactory.create_embed(
                        title="Error",
                        description=str(e),
                        colour=discord.Color.red(),
                        author="Role System"
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)

            @app_commands.command(name="remove", description="Remove a role from a message.")
            @app_commands.describe(
                message_id="ID of the message",
                role="Role you want to remove",
                channel="Channel of the message (defaults to the current channel)"
            )
            @app_commands.checks.has_permissions(administrator=True)
            @app_commands.guilds(*GUILD_ID)
            async def remove(
                self,
                interaction: discord.Interaction,
                message_id: str,
                role: discord.Role,
                channel: Optional[discord.TextChannel] = None
            ):
                await interaction.response.defer(ephemeral=True)
                try:
                    msg_id = int(message_id.strip())
                except ValueError:
                    return await interaction.followup.send("Message ID must be numeric.", ephemeral=True)

                target_channel = channel or interaction.channel
                emoji = self.role_system.get_emoji(msg_id, role.id)

                if emoji:
                    try:
                        msg = await target_channel.fetch_message(msg_id)
                        # Remove bot reaction
                        if emoji.isdigit():
                            custom_emoji = self.bot.get_emoji(int(emoji))
                            if custom_emoji:
                                await msg.clear_reaction(custom_emoji)
                        else:
                            await msg.clear_reaction(emoji)
                    except Exception:
                        pass

                self.role_system.remove_role(msg_id, role.id)
                embed = EmbedFactory.create_embed(
                    title="Removed Role",
                    description=f"Successfully removed {role.mention} from message `{msg_id}`.",
                    colour=discord.Color.green(),
                    author="Role System"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    pass