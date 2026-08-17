import uuid
import discord
from discord import app_commands
from utils.debug import Logger
import os

logger = Logger(os.path.basename(__file__).replace(".py", ""))

import json
import io
# (Make sure your other imports like os, Logger, uuid, etc. are still at the top)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Chiudi Ticket", style=discord.ButtonStyle.danger,
                       custom_id="persistent_close_ticket_button", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Acknowledge the button press
        await interaction.response.send_message("Sto salvando il transcript e chiudendo il ticket...", ephemeral=True)

        try:
            # 1. Fetch all messages in the channel (from oldest to newest)
            messages_data = []
            async for msg in interaction.channel.history(limit=None, oldest_first=True):
                messages_data.append({
                    "author": str(msg.author),
                    "author_id": msg.author.id,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                })

            # 2. Convert dictionary to a formatted JSON string and load it into a BytesIO object
            json_data = json.dumps(messages_data, indent=4, ensure_ascii=False)
            file_bytes = io.BytesIO(json_data.encode('utf-8'))

            # 3. Get the log channel
            log_channel_id = 1538771506618695750
            log_channel = interaction.guild.get_channel(log_channel_id)

            # 4. Send the JSON file to the log channel
            if log_channel:
                transcript_file = discord.File(fp=file_bytes, filename=f"{interaction.channel.name}_transcript.json")
                await log_channel.send(
                    content=f"📑 Transcript del ticket `{interaction.channel.name}` (Chiuso da {interaction.user.mention})",
                    file=transcript_file
                )
            else:
                logger.warning(f"Log channel {log_channel_id} non trovato.")

            # 5. Delete the ticket channel
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
            logger.info(f"Ticket {interaction.channel.name} closed by {interaction.user.name}.")

        except discord.HTTPException as e:
            logger.error(f"Failed to process or delete ticket channel: {e}")
            # In case it fails to delete, notify the user in the channel
            try:
                await interaction.followup.send("Errore durante la chiusura del ticket. Controlla i log.", ephemeral=True)
            except:
                pass


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apri un ticket", style=discord.ButtonStyle.primary,
                       custom_id="persistent_create_ticket_button", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Acknowledge the interaction first so it doesn't time out
        await interaction.response.send_message("Setting up your ticket...", ephemeral=True)

        server = interaction.guild

        # 1. Get the category (Ensure the ID is an integer)
        category_id = 1538768468868857927
        category = server.get_channel(category_id)

        # Check if the category exists to prevent errors
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send("Error: Ticket category not found or is invalid.", ephemeral=True)
            return

        # 2. Create a unique ID for the ticket
        short_uuid = uuid.uuid4().hex[:6]
        channel_name = f"ticket-{short_uuid}"

        # Get the Support Role
        support_role_id = 1530983265467498636
        support_role = server.get_role(support_role_id)

        # 3. Set permissions
        overwrites = {
            server.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            server.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Add support role to overwrites if it exists
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        else:
            logger.warning(f"Support role with ID {support_role_id} not found.")

        try:
            # 4. Create the ticket and put it in the category
            ticket_channel = await server.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites
            )

            # 5. Create the Welcome Embed for the new channel
            welcome_embed = discord.Embed(
                title="Ticket Creato",
                description=f"Ciao {interaction.user.mention},\nGrazie per aver aperto un ticket. Puoi iniziare a scrivere qui il tuo problema o la tua richiesta. Un membro dello staff ti risponderà il prima possibile.",
                color=discord.Color.green()
            )

            # Send the embed, ping the user, and attach the close button
            await ticket_channel.send(
                content=f"{interaction.user.mention} <@&1530983265467498636> <@&1517263269348507668> <@&1530982295752937512>",
                embed=welcome_embed,
                view=TicketControlView()
            )

            # Notify the user that the ticket is ready in the original channel
            await interaction.followup.send(f"Ticket successfully created: {ticket_channel.mention}", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("Error: I do not have permissions to create channels.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred while creating the ticket: {e}", ephemeral=True)