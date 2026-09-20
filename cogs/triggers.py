import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
from config import GUILD_ID
from utils.embed_factory import EmbedFactory
from utils.debug import Logger

logger = Logger(os.path.basename(__file__).replace(".py", ""))

def format_response(template: str, message: discord.Message) -> str:
    """Replaces Carl-bot style variables with actual Discord data."""
    replacements = {
        "{user}": message.author.display_name,
        "{user.name}": message.author.name,
        "{user.mention}": message.author.mention,
        "{user.id}": str(message.author.id),
        "{user.avatar}": message.author.display_avatar.url,
        "{server}": message.guild.name if message.guild else "",
        "{server.id}": str(message.guild.id) if message.guild else "",
        "{server.member_count}": str(message.guild.member_count) if message.guild else "",
        "{channel}": message.channel.name if hasattr(message.channel, "name") else "",
        "{channel.mention}": message.channel.mention if hasattr(message.channel, "mention") else "",
        "{channel.id}": str(message.channel.id),
    }
    output = template
    for placeholder, val in replacements.items():
        output = output.replace(placeholder, val)
    return output


class Triggers(commands.Cog):
    """Cog that manages Carl-bot style custom triggers and automated responses."""

    def __init__(self, bot: commands.Bot, trigger_db):
        self.bot = bot
        self.db = trigger_db

    # Define guild_ids here on the parent group instead of on each child command
    trigger_group = app_commands.Group(
        name="trigger",
        description="Gestisci i trigger automatici in stile Carl-bot",
        guild_ids=GUILD_ID
    )

    @trigger_group.command(name="add", description="Crea un nuovo trigger.")
    @app_commands.describe(
        trigger="La parola o frase chiave che attiva la risposta.",
        response="La risposta del bot (supporta {user}, {server}, {channel}, ecc.).",
        mode="Tipo di matching: 'contains' (default), 'exact', o 'startswith'."
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="Contiene la parola (contains)", value="contains"),
        app_commands.Choice(name="Frase esatta (exact)", value="exact"),
        app_commands.Choice(name="Inizia con (startswith)", value="startswith")
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_trigger(
        self,
        interaction: discord.Interaction,
        trigger: str,
        response: str,
        mode: app_commands.Choice[str] = None
    ):
        match_mode = mode.value if mode else "contains"

        trigger_id = await asyncio.to_thread(
            self.db.add_trigger,
            interaction.guild_id,
            trigger,
            response,
            match_mode
        )

        logger.info(f"Trigger #{trigger_id} added by {interaction.user.name} in guild {interaction.guild_id}")

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            title="Trigger Aggiunto! ✅",
            description=f"Il trigger **#{trigger_id}** è stato creato con successo.",
            colour=discord.Color.green(),
            author="Triggers"
        )
        embed.add_field(name="Keyword", value=f"`{trigger}`", inline=True)
        embed.add_field(name="Modalità", value=f"`{match_mode}`", inline=True)
        embed.add_field(name="Risposta", value=response, inline=False)

        await interaction.response.send_message(embed=embed)

    @trigger_group.command(name="remove", description="Rimuovi un trigger tramite il suo ID.")
    @app_commands.describe(trigger_id="L'ID del trigger da eliminare.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_trigger(self, interaction: discord.Interaction, trigger_id: int):
        deleted = await asyncio.to_thread(self.db.remove_trigger, interaction.guild_id, trigger_id)

        if not deleted:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                title="Errore",
                description=f"❌ Nessun trigger trovato con ID `#{trigger_id}` in questo server.",
                colour=discord.Color.red(),
                author="Triggers"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            title="Trigger Rimosso",
            description=f"🗑️ Trigger `#{trigger_id}` eliminato con successo.",
            colour=discord.Color.green(),
            author="Triggers"
        )
        await interaction.response.send_message(embed=embed)

    @trigger_group.command(name="list", description="Mostra tutti i trigger configurati nel server.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_triggers(self, interaction: discord.Interaction):
        rows = await asyncio.to_thread(self.db.get_triggers, interaction.guild_id)

        if not rows:
            embed = EmbedFactory.create_embed(
                interaction=interaction,
                title="Nessun Trigger",
                description="ℹ️ Non ci sono trigger configurati per questo server.",
                colour=discord.Color.yellow(),
                author="Triggers"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            title=f"Trigger di {interaction.guild.name}",
            description=f"Lista dei trigger registrati (**{len(rows)}** totali):",
            colour=discord.Color.blue(),
            author="Triggers"
        )

        for row in rows[:25]:
            t_id, trigger_text, resp, mode = row
            truncated_resp = resp if len(resp) <= 50 else resp[:47] + "..."
            embed.add_field(
                name=f"ID #{t_id} | `{trigger_text}` ({mode})",
                value=f"➜ {truncated_resp}",
                inline=False
            )

        if len(rows) > 25:
            embed.set_footer(text=f"Mostrati 25 di {len(rows)} trigger.")

        await interaction.response.send_message(embed=embed)

    @trigger_group.command(name="clear", description="Cancella tutti i trigger di questo server.")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_triggers(self, interaction: discord.Interaction):
        count = await asyncio.to_thread(self.db.clear_triggers, interaction.guild_id)

        embed = EmbedFactory.create_embed(
            interaction=interaction,
            title="Trigger Azzerati",
            description=f"🧹 Sono stati eliminati tutti i **{count}** trigger di questo server.",
            colour=discord.Color.green(),
            author="Triggers"
        )
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        triggers = await asyncio.to_thread(self.db.get_triggers, message.guild.id)
        if not triggers:
            return

        content = message.content.lower().strip()

        for _, trigger_text, response, mode in triggers:
            trigger_lower = trigger_text.lower()
            matched = False

            if mode == "exact" and content == trigger_lower:
                matched = True
            elif mode == "startswith" and content.startswith(trigger_lower):
                matched = True
            elif mode == "contains" and trigger_lower in content:
                matched = True

            if matched:
                formatted_response = format_response(response, message)
                try:
                    await message.channel.send(formatted_response)
                except discord.HTTPException as e:
                    logger.error(f"Failed to send trigger response: {e}")
                break