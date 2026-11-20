import asyncio
import io

import discord
from discord.ext import commands
import re
import datetime
from utils.debug import Logger
import os
import json

logger = Logger(os.path.basename(__file__).replace(".py", ""))

class CloseDMChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # timeout=None rende la view persistente

    @discord.ui.button(
        label="Chiudi Canale",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="persistent_close_dm_channel_btn"
    )
    async def close_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

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
        except discord.HTTPException as e:
            logger.error(f"Failed to process or delete ticket channel: {e}")
            # In case it fails to delete, notify the user in the channel
            try:
                await interaction.followup.send("Errore durante la chiusura del ticket. Controlla i log.", ephemeral=True)
            except:
                pass

        # Recupera l'ID dell'utente dal topic del canale
        if interaction.channel.topic:
            user_id_match = re.search(r'ID:\s*(\d+)', interaction.channel.topic)
            if user_id_match:
                user_id = int(user_id_match.group(1))
                try:
                    user = interaction.client.get_user(user_id) or await interaction.client.fetch_user(user_id)
                    close_embed = discord.Embed(
                        title="Ticket Chiuso",
                        description="Il tuo ticket di supporto con lo staff è stato chiuso.",
                        color=discord.Color.red(),
                        timestamp=datetime.now(datetime.timezone.utc)
                    )
                    await user.send(embed=close_embed)
                except Exception:
                    pass

        embed = discord.Embed(
            description=f"🔒 Canale in chiusura su richiesta di {interaction.user.mention}...",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed)
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket DM chiuso da {interaction.user.name}")