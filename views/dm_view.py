import asyncio

import discord
from discord.ext import commands
import re
import datetime

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