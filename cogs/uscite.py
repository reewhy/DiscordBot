import asyncio
import math
import os
import random
import time
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
import io
import re
import aiohttp

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    GUILD_ID,
    USCITE_ID,
    USCITE_ROLE_ID,
    USCITE_LISTA_CHANNEL_ID,
    USCITE_PROPOSTE_CHANNEL_ID,
    EVENTI_ONLINE_ID,
    EVENTI_ONLINE_ROLE_ID,
)
from utils.debug import Logger

logger = Logger(os.path.basename(__file__).replace(".py", ""))

TZ = ZoneInfo("Europe/Rome")
REMINDER_HOUR = 12          # ora (Italia) del giorno prima in cui parte il sondaggio finale
MAX_POLL_HOURS = 768        # limite di Discord per la durata di un sondaggio (32 giorni)

ANSWER_YES = "Sì"
ANSWER_MAYBE = "Forse..."
ANSWER_NO = "No"

KAOMOJI = [
    "(ᵔᴥᵔ)", "(◕‿◕)", "ヽ(•‿•)ノ", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "(≧◡≦)", "٩(◕‿◕)۶", "(•◡•)",
    "(๑˃ᴗ˂)ﻭ", "(＾▽＾)", "ʕ•ᴥ•ʔ",
    "(◕ᴗ◕✿)", "(≧▽≦)", "( ꈍᴗꈍ)", "(´ω｀)", "(｡•̀ᴗ-)✧", "✧◝(⁰▿⁰)◜✧", "(｡･ω･｡)ﾉ♡",
    "꒰⑅ᵕ༚ᵕ꒱˖♡", "ʕっ•ᴥ•ʔっ", "ᕦʕ •ᴥ•ʔᕤ", "ʕ·ᴥ·ʔ", "ฅ^•ﻌ•^ฅ", "૮ ˶ᵔ ᵕ ᵔ˶ ა",
    "꒰ᐢ. .ᐢ꒱₊˚⊹", "(*ᴗ͈ˬᴗ͈)", "ʚ(｡˃ ᵕ ˂ )ɞ", "૮₍˶ •. • ⑅₎ა", "⸜(｡˃ ᵕ ˂ )⸝",
    "(˶˃ ᵕ ˂˶)", "˶ˆ꒳ˆ˵", "( • ༝•)", "≽^•༚• ྀི≼", "૮ ˶ᵔ ᵕ ᵔ˶ ა", "𐔌՞. .՞𐦯"
]

PRENOTAZIONE_TEXT = (
    "## ⚠️ ATTENZIONE : **USCITA CON PRENOTAZIONE** ! LEGGI PRIMA DI VOTARE\n"
    "🔴 Questa uscita verrà effettuata con prenotazione al pub.\n\n"
    "• __Bidonare__ un'uscita con prenotazione risulterà in **uno strike**.\n"
    "• Portare __persone__ non presenti nel server **senza avvisare lo staff**, "
    "quindi non contate nella prenotazione, risulterà in uno strike.\n"
    "• Venire __senza aver messo la presenza__ **risulterà in uno strike.**\n\n"
    "‼️ **Dopo 2 strike non sarà più possibile venire alle uscite sotto prenotazione.**\n\n"
    "-# Un sondaggio di conferma per coloro che votano \"forse\" verrà effettuato 1-2 giorni "
    "prima dell'uscita. Le persone che hanno votato \"sì\" al primo sondaggio sono libere di "
    "cambiare voto senza ricevere uno strike."
)

EVENT_DURATION_HOURS = 3
CHANNEL_REF_RE = re.compile(r"discord(?:app)?\.com/channels/\d+/(\d+)|<#(\d+)>")


# =========================================================================
# Utility
# =========================================================================

def parse_event_dt(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return None


def build_uscita_embeds(p: dict, creator: Optional[discord.abc.User], image_ref: Optional[str]) -> list[discord.Embed]:
    """Gli embed del post: identici nella proposta e nella pubblicazione."""
    online = p.get("kind") == "ONLINE"

    parts = [f"# {discord.utils.escape_markdown(p['kaomoji'])} {p['title']}"]
    if p["description"]:
        parts.append(p["description"])
    parts.append(f"{'💻 **__dove__**' if online else '📍 **__punto di ritrovo__**'} : {p['place']}")
    parts.append(f"📅 **__data__** : <t:{p['event_ts']}:D>")
    parts.append(f"🕑 **__orario__** : <t:{p['event_ts']}:t>")

    embed = discord.Embed(description="\n\n".join(parts), color=discord.Color.blurple())
    if creator:
        embed.set_footer(text=f"Organizzata da {creator.display_name}", icon_url=creator.display_avatar.url)
    if image_ref:
        embed.set_image(url=image_ref)

    embeds = [embed]
    if p["reservation"] and not online:
        embeds.append(discord.Embed(description=PRENOTAZIONE_TEXT, color=discord.Color.red()))
    if p["warning"]:
        embeds.append(discord.Embed(description=f"# ⚠️ {p['warning']}", color=discord.Color.red()))
    return embeds


# =========================================================================
# Modal: nuova proposta / pubblicazione diretta
# =========================================================================

class UscitaModal(discord.ui.Modal, title="Nuova Uscita"):
    kind = "LIVE"

    def __init__(self, cog: "Uscite", event_title: str, warning: Optional[str], reservation: bool,
                 direct: bool = False, final_poll: bool = True):
        super().__init__()
        self.cog = cog
        self.event_title = event_title.strip()
        self.warning = (warning or "").strip()
        self.reservation = reservation
        self.direct = direct
        self.final_poll = final_poll

        self.image_upload = discord.ui.FileUpload(required=False, min_values=0, max_values=1)
        self.add_item(discord.ui.Label(
            text="Immagine: file (opzionale)",
            description="Carica un file, oppure usa il campo link qui sopra",
            component=self.image_upload,
        ))

    when = discord.ui.TextInput(
        label="Data e ora (GG/MM/AAAA HH:MM)",
        placeholder="es. 29/10/2026 19:00",
        min_length=16,
        max_length=16,
    )
    place = discord.ui.TextInput(
        label="Punto di ritrovo",
        placeholder="es. entrata principale del parco Rossani (lato stazione)",
        max_length=300,
    )
    description = discord.ui.TextInput(
        label="Descrizione",
        style=discord.TextStyle.paragraph,
        placeholder="Supporta il Markdown: **grassetto**, __sottolineato__, emoji...",
        max_length=1500,
        required=False,
    )
    image_url = discord.ui.TextInput(
        label="Immagine: link (opzionale)",
        placeholder="https://... (link diretto a un'immagine)",
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        event_dt = parse_event_dt(self.when.value)
        if not event_dt:
            await interaction.response.send_message(
                "❌ Formato data non valido. Usa `GG/MM/AAAA HH:MM`, es. `29/10/2026 19:00`.", ephemeral=True
            )
            return
        if event_dt <= datetime.now(TZ):
            await interaction.response.send_message("❌ La data è già passata.", ephemeral=True)
            return

        attachment = self.image_upload.values[0] if self.image_upload.values else None
        if attachment and not (attachment.content_type or "").startswith("image/"):
            await interaction.response.send_message("❌ Il file caricato non è un'immagine.", ephemeral=True)
            return

        image_url = self.image_url.value.strip()
        if image_url and not image_url.startswith(("http://", "https://")):
            await interaction.response.send_message("❌ Il link dell'immagine non è valido.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        p = {
            "title": self.event_title,
            "event_ts": int(event_dt.timestamp()),
            "place": self.place.value.strip(),
            "description": self.description.value.strip(),
            "image_url": "" if attachment else image_url,   # se c'è il file, vince il file
            "has_file": attachment is not None,
            "reservation": self.reservation,
            "warning": self.warning,
            "kaomoji": random.choice(KAOMOJI),
            "creator_id": interaction.user.id,
            "kind": self.kind,
            "final_poll": self.final_poll,
        }

        # =================================================================
        # FLUSSO DIRETTO (staff, senza approvazione)
        # =================================================================
        if self.direct:
            try:
                thread = await self.cog.publish_uscita(interaction.guild, p, attachment)
                logger.info(f"'{p['title']}' pubblicato direttamente dallo staff ({interaction.user.name})")
                await interaction.followup.send(f"⚡ Pubblicato direttamente: {thread.mention}", ephemeral=True)
            except ValueError as e:
                await interaction.followup.send(f"❌ {e}", ephemeral=True)
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Non ho i permessi per creare post/sondaggi nel canale di pubblicazione.", ephemeral=True
                )
            except discord.HTTPException as e:
                logger.error("Errore nella pubblicazione diretta", exc_info=e)
                await interaction.followup.send(f"❌ Errore durante la pubblicazione: {e}", ephemeral=True)
            return

        # =================================================================
        # FLUSSO STANDARD (proposta nel forum)
        # =================================================================
        channel = interaction.guild.get_channel(USCITE_PROPOSTE_CHANNEL_ID)
        if not isinstance(channel, discord.ForumChannel):
            await interaction.followup.send(
                "❌ Il canale delle proposte non è configurato correttamente.", ephemeral=True
            )
            return

        kwargs = {}
        filename = None
        if attachment:
            file = await attachment.to_file()
            kwargs["file"] = file
            filename = file.filename

        content, embeds = await self.cog.build_proposal_payload(interaction.guild, p, filename)

        try:
            created = await channel.create_thread(
                name=p["title"][:100],
                content=content,
                embeds=embeds,
                view=ProposalView(self.cog),
                allowed_mentions=discord.AllowedMentions.none(),
                **kwargs,
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Non ho i permessi per creare post nel forum delle proposte.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            logger.error("Errore nell'invio della proposta", exc_info=e)
            await interaction.followup.send(f"❌ Errore durante l'invio della proposta: {e}", ephemeral=True)
            return

        thread, msg = created.thread, created.message

        # Aggiunge il proponente al post, così riceve le notifiche della discussione
        try:
            await thread.add_user(interaction.user)
        except discord.HTTPException:
            pass

        self.cog.db.add_proposta(
            guild_id=interaction.guild.id,
            message_id=msg.id,
            creator_id=interaction.user.id,
            title=p["title"],
            event_ts=p["event_ts"],
            place=p["place"],
            description=p["description"],
            image_url=p["image_url"],
            has_file=p["has_file"],
            reservation=p["reservation"],
            warning=p["warning"],
            kaomoji=p["kaomoji"],
            kind=p["kind"],
            final_poll=p["final_poll"],
        )
        logger.info(f"Proposta '{p['title']}' ({p['kind']}) inviata da {interaction.user.name}")
        await interaction.followup.send(
            f"✅ Proposta inviata: {thread.mention}. Lo staff la valuterà a breve.", ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Errore nel modal uscita", exc_info=error)
        if interaction.response.is_done():
            await interaction.followup.send("❌ Si è verificato un errore.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Si è verificato un errore.", ephemeral=True)


class EventoOnlineModal(UscitaModal, title="Nuovo Evento Online"):
    kind = "ONLINE"

    place = discord.ui.TextInput(
        label="Dove (link, canale vocale...)",
        placeholder="es. canale vocale #eventi, oppure link alla piattaforma",
        max_length=300,
    )


# =========================================================================
# Modal: modifica proposta (staff)
# =========================================================================

class EditProposalModal(discord.ui.Modal, title="Modifica proposta"):
    def __init__(self, cog: "Uscite", p: dict):
        super().__init__()
        self.cog = cog
        self.p = p

        self.f_title = discord.ui.TextInput(label="Titolo", default=p["title"], max_length=100)
        self.f_when = discord.ui.TextInput(
            label="Data e ora (GG/MM/AAAA HH:MM)",
            default=datetime.fromtimestamp(p["event_ts"], TZ).strftime("%d/%m/%Y %H:%M"),
            min_length=16,
            max_length=16,
        )
        self.f_place = discord.ui.TextInput(
            label="Dove (link, canale...)" if p.get("kind") == "ONLINE" else "Punto di ritrovo",
            default=p["place"],
            max_length=300,
        )
        self.f_desc = discord.ui.TextInput(
            label="Descrizione",
            style=discord.TextStyle.paragraph,
            default=p["description"] or None,
            max_length=1500,
            required=False,
        )
        self.f_link = discord.ui.TextInput(
            label="Immagine: link (vuoto = lascia com'è)",
            default=p["image_url"] or None,
            placeholder="https://... (un nuovo link sostituisce il file caricato)",
            required=False,
        )
        for item in (self.f_title, self.f_when, self.f_place, self.f_desc, self.f_link):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        event_dt = parse_event_dt(self.f_when.value)
        if not event_dt:
            await interaction.response.send_message(
                "❌ Formato data non valido. Usa `GG/MM/AAAA HH:MM`.", ephemeral=True
            )
            return
        if event_dt <= datetime.now(TZ):
            await interaction.response.send_message("❌ La data è già passata.", ephemeral=True)
            return

        link = self.f_link.value.strip()
        if link and not link.startswith(("http://", "https://")):
            await interaction.response.send_message("❌ Il link dell'immagine non è valido.", ephemeral=True)
            return

        updates = {
            "title": self.f_title.value.strip(),
            "event_ts": int(event_dt.timestamp()),
            "place": self.f_place.value.strip(),
            "description": self.f_desc.value.strip(),
        }
        drop_file = False
        if link:
            updates["image_url"] = link
            updates["has_file"] = False
            drop_file = self.p["has_file"]
        elif not self.p["has_file"]:
            updates["image_url"] = ""

        self.cog.db.update_proposta(self.p["id"], **updates)
        p = {**self.p, **updates}

        filename = interaction.message.attachments[0].filename if interaction.message.attachments else None
        content, embeds = await self.cog.build_proposal_payload(interaction.guild, p, filename)

        kwargs = {"attachments": []} if drop_file else {}
        # view=... aggiorna anche i pulsanti dei messaggi creati con versioni precedenti
        await interaction.response.edit_message(
            content=content, embeds=embeds, view=ProposalView(self.cog), **kwargs
        )

        if isinstance(interaction.channel, discord.Thread):
            try:
                await interaction.channel.edit(name=updates["title"][:100])
            except discord.HTTPException:
                pass  # rate limit sul rename dei thread, non è grave

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error("Errore nella modifica della proposta", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Si è verificato un errore.", ephemeral=True)


class WarningModal(discord.ui.Modal, title="Avviso in evidenza"):
    def __init__(self, cog: "Uscite", p: dict):
        super().__init__()
        self.cog = cog
        self.p = p
        self.f_warning = discord.ui.TextInput(
            label="Avviso (vuoto = nessun avviso)",
            default=p["warning"] or None,
            max_length=200,
            required=False,
        )
        self.add_item(self.f_warning)

    async def on_submit(self, interaction: discord.Interaction):
        warning = self.f_warning.value.strip()
        self.cog.db.update_proposta(self.p["id"], warning=warning)
        p = {**self.p, "warning": warning}

        filename = interaction.message.attachments[0].filename if interaction.message.attachments else None
        content, embeds = await self.cog.build_proposal_payload(interaction.guild, p, filename)
        await interaction.response.edit_message(content=content, embeds=embeds, view=ProposalView(self.cog))


# =========================================================================
# View persistente della proposta
# =========================================================================

class ProposalView(discord.ui.View):
    def __init__(self, cog: "Uscite"):
        super().__init__(timeout=None)
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ Solo lo staff può gestire le proposte.", ephemeral=True
            )
            return False
        return True

    async def _load(self, interaction: discord.Interaction) -> Optional[dict]:
        p = self.cog.db.get_proposta(interaction.message.id)
        if not p or p["status"] != "PENDING":
            await interaction.response.send_message(
                "❌ Questa proposta non è più in attesa.", ephemeral=True
            )
            return None
        return p

    async def _archive(self, interaction: discord.Interaction):
        if isinstance(interaction.channel, discord.Thread):
            try:
                await interaction.channel.edit(archived=True)
            except discord.HTTPException:
                pass

    async def _update_proposal(self, interaction: discord.Interaction, p: dict):
        """Riscrive la proposta con i dati aggiornati e la view corrente."""
        filename = interaction.message.attachments[0].filename if interaction.message.attachments else None
        content, embeds = await self.cog.build_proposal_payload(interaction.guild, p, filename)
        await interaction.response.edit_message(content=content, embeds=embeds, view=ProposalView(self.cog))

    @discord.ui.button(label="Approva", style=discord.ButtonStyle.success, emoji="✅",
                       custom_id="uscite:approve", row=0)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if not p:
            return
        await interaction.response.defer(ephemeral=True)

        attachment = interaction.message.attachments[0] if interaction.message.attachments else None

        try:
            thread = await self.cog.publish_uscita(interaction.guild, p, attachment)
        except ValueError as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Non ho i permessi per creare post/sondaggi nel canale di pubblicazione.", ephemeral=True
            )
            return
        except discord.HTTPException as e:
            logger.error("Errore nella pubblicazione", exc_info=e)
            await interaction.followup.send(f"❌ Errore durante la pubblicazione: {e}", ephemeral=True)
            return

        self.cog.db.update_proposta(p["id"], status="APPROVED")
        await interaction.message.edit(
            content=f"✅ Proposta **approvata** da {interaction.user.mention} → {thread.mention}",
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await self._archive(interaction)
        logger.info(f"Proposta {p['id']} approvata da {interaction.user.name}: {thread.name} ({thread.id})")
        await interaction.followup.send(f"✅ Pubblicato: {thread.mention}", ephemeral=True)

        # Avvisa chi l'ha proposta (se ha i DM aperti)
        creator = await self.cog.get_creator(interaction.guild, p["creator_id"])
        if creator:
            try:
                await creator.send(f"✅ La tua proposta **{p['title']}** è stata approvata: {thread.jump_url}")
            except (discord.Forbidden, discord.HTTPException):
                pass

    @discord.ui.button(label="Modifica", style=discord.ButtonStyle.primary, emoji="📝",
                       custom_id="uscite:edit", row=0)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if p:
            await interaction.response.send_modal(EditProposalModal(self.cog, p))

    @discord.ui.button(label="Avviso", style=discord.ButtonStyle.secondary, emoji="⚠️",
                       custom_id="uscite:warning", row=1)
    async def warning(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if p:
            await interaction.response.send_modal(WarningModal(self.cog, p))

    @discord.ui.button(label="Prenotazione sì/no", style=discord.ButtonStyle.secondary, emoji="🔴",
                       custom_id="uscite:reservation", row=1)
    async def reservation(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if not p:
            return
        if p.get("kind") == "ONLINE":
            await interaction.response.send_message(
                "❌ La prenotazione non è disponibile per gli eventi online.", ephemeral=True
            )
            return

        p["reservation"] = not p["reservation"]
        self.cog.db.update_proposta(p["id"], reservation=p["reservation"])
        await self._update_proposal(interaction, p)

    @discord.ui.button(label="Sondaggi sì/no", style=discord.ButtonStyle.secondary, emoji="📢",
                       custom_id="uscite:final_poll", row=1)
    async def final_poll_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if not p:
            return
        if p.get("kind") != "ONLINE":
            await interaction.response.send_message(
                "❌ I sondaggi si possono disattivare solo per gli eventi online.", ephemeral=True
            )
            return

        p["final_poll"] = not p["final_poll"]
        self.cog.db.update_proposta(p["id"], final_poll=p["final_poll"])
        await self._update_proposal(interaction, p)

    @discord.ui.button(label="Rifiuta", style=discord.ButtonStyle.danger, emoji="✖️",
                       custom_id="uscite:reject", row=1)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = await self._load(interaction)
        if not p:
            return
        self.cog.db.update_proposta(p["id"], status="REJECTED")
        await interaction.response.edit_message(
            content=f"❌ Proposta **rifiutata** da {interaction.user.mention}",
            view=None,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        await self._archive(interaction)
        logger.info(f"Proposta {p['id']} rifiutata da {interaction.user.name}")


# =========================================================================
# Cog
# =========================================================================

class Uscite(commands.Cog):
    def __init__(self, bot, uscite_system):
        self.bot = bot
        self.db = uscite_system
        self._refresh_tasks: dict[int, asyncio.Task] = {}

    async def cog_load(self):
        self.bot.add_view(ProposalView(self))   # rende i pulsanti persistenti dopo i riavvii
        self.check_reminders.start()

    async def cog_unload(self):
        self.check_reminders.cancel()

    # ---------------------------------------------------------------------
    # Comandi
    # ---------------------------------------------------------------------

    @app_commands.command(name="uscita", description="Proponi una nuova uscita allo staff o pubblicala direttamente.")
    @app_commands.describe(
        titolo="Titolo dell'uscita.",
        prenotazione="L'uscita è su prenotazione? (aggiunge il box con le regole e gli strike)",
        avviso="Avviso in evidenza (opzionale), es. restrizioni o regole particolari.",
        diretto="Bypassa l'approvazione e pubblica direttamente l'uscita (solo Staff).",
    )
    @app_commands.guilds(*GUILD_ID)
    async def uscita(
            self,
            interaction: discord.Interaction,
            titolo: app_commands.Range[str, 1, 100],
            prenotazione: bool = False,
            avviso: Optional[app_commands.Range[str, 1, 200]] = None,
            diretto: bool = False,
    ):
        if diretto and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ Solo lo staff può pubblicare direttamente un'uscita senza approvazione.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(UscitaModal(self, titolo, avviso, prenotazione, direct=diretto))

    @app_commands.command(name="evento_online",
                          description="Proponi un evento online allo staff o pubblicalo direttamente.")
    @app_commands.describe(
        titolo="Titolo dell'evento.",
        avviso="Avviso in evidenza (opzionale).",
        sondaggio_conferma="Sondaggi e lista partecipanti? Se no, niente sondaggi né lista (default: sì)",
        diretto="Bypassa l'approvazione e pubblica direttamente l'evento (solo Staff).",
    )
    @app_commands.guilds(*GUILD_ID)
    async def evento_online(
            self,
            interaction: discord.Interaction,
            titolo: app_commands.Range[str, 1, 100],
            avviso: Optional[app_commands.Range[str, 1, 200]] = None,
            sondaggio_conferma: bool = True,
            diretto: bool = False,
    ):
        if diretto and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ Solo lo staff può pubblicare direttamente un evento senza approvazione.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            EventoOnlineModal(self, titolo, avviso, False, direct=diretto, final_poll=sondaggio_conferma)
        )

    @app_commands.command(name="kaomoji", description="Mostra tutte le kaomoji disponibili per i titoli delle uscite.")
    @app_commands.guilds(*GUILD_ID)
    async def kaomoji(self, interaction: discord.Interaction):
        lines = [f"`{i}.` {discord.utils.escape_markdown(k)}" for i, k in enumerate(KAOMOJI, 1)]

        chunks, current = [], ""
        for line in lines:
            if len(current) + len(line) + 1 > 1900:
                chunks.append(current)
                current = ""
            current += line + "\n"
        chunks.append(current)

        await interaction.response.send_message(chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    @app_commands.command(
        name="uscita_termina",
        description="Termina il sondaggio e invia subito quello di conferma (solo mod).",
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.guilds(*GUILD_ID)
    async def uscita_termina(self, interaction: discord.Interaction):
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or thread.parent_id not in (USCITE_ID, EVENTI_ONLINE_ID):
            await interaction.response.send_message(
                "❌ Usa questo comando dentro il thread di un'uscita o di un evento.", ephemeral=True
            )
            return

        row = self.db.get_by_thread(thread.id)
        if not row:
            await interaction.response.send_message(
                "❌ Questo thread non ha sondaggi registrati (ad esempio un evento online senza sondaggi).",
                ephemeral=True,
            )
            return

        uscita_id, poll_message_id, event_ts, sent = row
        await interaction.response.defer(ephemeral=True)

        try:
            if not sent:
                # Il primo sondaggio può non esistere (uscita vicina): in quel caso `sent` è già True
                poll_msg = await thread.fetch_message(poll_message_id)
                if poll_msg.poll and not poll_msg.poll.is_finalised():
                    await poll_msg.poll.end()

                final_id = await self.send_final_poll(thread.id, poll_message_id, event_ts, forced=True)
                self.db.set_final_poll(uscita_id, final_id)
                self.db.mark_sent(uscita_id)

                logger.info(f"Uscita {uscita_id}: sondaggio terminato e conferma inviata da {interaction.user.name}")
                await interaction.followup.send(
                    "✅ Sondaggio terminato e sondaggio di conferma inviato.", ephemeral=True
                )
            else:
                target = None
                async for msg in thread.history(limit=50):
                    if msg.author.id == self.bot.user.id and msg.poll and not msg.poll.is_finalised():
                        target = msg
                        break

                if not target:
                    await interaction.followup.send("❌ Non c'è nessun sondaggio attivo in questo thread.",
                                                    ephemeral=True)
                    return

                await target.poll.end()
                logger.info(f"Sondaggio {target.id} terminato da {interaction.user.name}")
                await interaction.followup.send("✅ Sondaggio terminato.", ephemeral=True)

        except discord.NotFound:
            await interaction.followup.send("❌ Il messaggio del sondaggio non esiste più.", ephemeral=True)
        except discord.HTTPException as e:
            logger.error("Errore in /uscita_termina", exc_info=e)
            await interaction.followup.send(f"❌ Errore: {e}", ephemeral=True)

    @uscita_termina.error
    async def uscita_termina_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ Non hai i permessi per usare questo comando.", ephemeral=True)
        else:
            logger.error("Errore in /uscita_termina", exc_info=error)

    # ---------------------------------------------------------------------
    # Proposte e pubblicazione
    # ---------------------------------------------------------------------

    async def get_creator(self, guild: discord.Guild, user_id: int) -> Optional[discord.abc.User]:
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await self.bot.fetch_user(user_id)
        except discord.HTTPException:
            return None

    async def build_proposal_payload(self, guild: discord.Guild, p: dict, filename: Optional[str]):
        """(content, embeds) del messaggio di proposta."""
        creator = await self.get_creator(guild, p["creator_id"])
        image_ref = None
        if p["has_file"] and filename:
            image_ref = f"attachment://{filename}"
        elif p["image_url"]:
            image_ref = p["image_url"]

        online = p.get("kind") == "ONLINE"
        content = (
            f"📝 **Proposta di {'evento online' if online else 'uscita'}** di <@{p['creator_id']}> "
            "— in attesa di approvazione dello staff."
        )
        if online:
            content += f"\n-# Sondaggi e lista partecipanti: {'sì' if p.get('final_poll', True) else 'no'}"
        else:
            content += f"\n-# Prenotazione: {'sì' if p['reservation'] else 'no'}"
        return content, build_uscita_embeds(p, creator, image_ref)

    @staticmethod
    def find_voice_channel(guild: discord.Guild, text: str) -> Optional[discord.abc.GuildChannel]:
        """Cerca nel testo un link (o una menzione) a un canale vocale/stage del server."""
        for m in CHANNEL_REF_RE.finditer(text or ""):
            channel = guild.get_channel(int(m.group(1) or m.group(2)))
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                return channel
        return None

    @staticmethod
    async def _download_image(url: str) -> Optional[bytes]:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200 or not resp.content_type.startswith("image/"):
                        return None
                    data = await resp.content.read(8 * 1024 * 1024 + 1)
                    return data if len(data) <= 8 * 1024 * 1024 else None
        except Exception:
            return None

    async def create_discord_event(self, guild: discord.Guild, p: dict, thread: discord.Thread,
                                   image_bytes: Optional[bytes]):
        """Crea l'evento programmato di Discord. Non solleva mai: un errore qui non deve bloccare la pubblicazione."""
        try:
            start = datetime.fromtimestamp(p["event_ts"], TZ)
            online = p.get("kind") == "ONLINE"

            description = (p["description"] + "\n\n" if p["description"] else "") + f"💬 Discussione: {thread.jump_url}"
            kwargs = dict(
                name=p["title"][:100],
                start_time=start,
                end_time=start + timedelta(hours=EVENT_DURATION_HOURS),
                description=description[:1000],
                privacy_level=discord.PrivacyLevel.guild_only,
                reason=f"Evento ufficializzato: {p['title']}",
            )

            voice = self.find_voice_channel(guild, p["place"]) if online else None
            if voice:
                kwargs["channel"] = voice          # tipo (voce/stage) dedotto dal canale
            else:
                kwargs["entity_type"] = discord.EntityType.external
                kwargs["location"] = p["place"][:100]

            if image_bytes is None and p["image_url"]:
                image_bytes = await self._download_image(p["image_url"])

            try:
                event = await guild.create_scheduled_event(**kwargs, **({"image": image_bytes} if image_bytes else {}))
            except discord.HTTPException:
                if not image_bytes:
                    raise
                event = await guild.create_scheduled_event(**kwargs)   # riprova senza immagine

            logger.info(f"Evento Discord creato per '{p['title']}': {event.url} "
                        f"({'vocale: ' + voice.name if voice else 'esterno'})")
        except discord.Forbidden:
            logger.error("Mi manca il permesso 'Gestisci eventi' per creare l'evento Discord")
        except Exception as e:
            logger.error(f"Impossibile creare l'evento Discord per '{p['title']}'", exc_info=e)

    async def publish_uscita(self, guild: discord.Guild, p: dict,
                             attachment: Optional[discord.Attachment]) -> discord.Thread:
        """Pubblica messaggio, sondaggio e lista. Solleva ValueError per errori da mostrare allo staff."""
        now = datetime.now(TZ)
        event_dt = datetime.fromtimestamp(p["event_ts"], TZ)
        if event_dt <= now:
            raise ValueError("La data è già passata: modifica la proposta prima di approvarla.")

        online = p.get("kind") == "ONLINE"
        channel_id = EVENTI_ONLINE_ID if online else USCITE_ID
        role_id = EVENTI_ONLINE_ROLE_ID if online else USCITE_ROLE_ID

        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("Il canale di pubblicazione non è configurato correttamente.")

        # I sondaggi e la lista si possono disattivare solo per gli eventi online
        polls_enabled = bool(p.get("final_poll", True)) if online else True
        logger.info(f"publish_uscita '{p['title']}': kind={p.get('kind')} final_poll={p.get('final_poll')} "
                    f"-> sondaggi={polls_enabled}")

        # Le durate si calcolano ora, non quando la proposta è stata creata
        reminder_dt = (event_dt - timedelta(days=1)).replace(
            hour=REMINDER_HOUR, minute=0, second=0, microsecond=0
        )
        poll_hours = math.floor((reminder_dt - now).total_seconds() / 3600)
        send_poll_first = poll_hours >= 1
        poll_hours = min(poll_hours, MAX_POLL_HOURS)

        # Immagine: il file viene ricaricato nel canale di pubblicazione
        kwargs = {}
        image_ref = None
        image_bytes = None
        if p["has_file"] and attachment:
            image_bytes = await attachment.read()
            file = discord.File(io.BytesIO(image_bytes), filename=attachment.filename)
            kwargs["file"] = file
            image_ref = f"attachment://{file.filename}"
        elif p["image_url"]:
            image_ref = p["image_url"]

        creator = await self.get_creator(guild, p["creator_id"])
        embeds = build_uscita_embeds(p, creator, image_ref)

        main_msg = await channel.send(
            content=f"<@&{role_id}>",
            embeds=embeds,
            allowed_mentions=discord.AllowedMentions(roles=[discord.Object(id=role_id)]),
            **kwargs,
        )
        thread = await main_msg.create_thread(name=p["title"][:100], auto_archive_duration=10080)

        # Nessun sondaggio, nessuna lista, niente salvataggio: l'evento finisce qui
        if not polls_enabled:
            return thread

        poll_msg_id = 0
        final_poll_id = 0
        if send_poll_first:
            poll = discord.Poll(question="Ci sarai?", duration=timedelta(hours=poll_hours))
            poll.add_answer(text=ANSWER_YES, emoji="✅")
            poll.add_answer(text=ANSWER_MAYBE, emoji="🤔")
            poll_msg_id = (await thread.send(poll=poll)).id
        else:
            # Troppo vicino: direttamente il sondaggio di conferma
            final_poll_id = await self.send_final_poll(
                thread.id, None, p["event_ts"], forced=True, force_send=True
            )

        list_id = await self.create_list_message(thread, p["title"])

        self.db.add_uscita(
            guild_id=guild.id,
            thread_id=thread.id,
            poll_message_id=poll_msg_id,
            creator_id=p["creator_id"],
            title=p["title"],
            event_ts=p["event_ts"],
            reminder_ts=int(reminder_dt.timestamp()),
            sent=not send_poll_first,
            final_poll_message_id=final_poll_id,
            list_message_id=list_id,
            final_enabled=True,
        )
        thread = await main_msg.create_thread(name=p["title"][:100], auto_archive_duration=10080)

        await self.create_discord_event(guild, p, thread, image_bytes)

        return thread

    # ---------------------------------------------------------------------
    # Sondaggio di conferma automatico
    # ---------------------------------------------------------------------

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        for uscita_id, guild_id, thread_id, poll_message_id, title, event_ts in self.db.get_due(int(time.time())):
            try:
                final_id = await self.send_final_poll(thread_id, poll_message_id, event_ts)
                self.db.set_final_poll(uscita_id, final_id)
                self.db.mark_sent(uscita_id)
                logger.info(f"Sondaggio di conferma inviato per '{title}' ({thread_id})")
            except (discord.NotFound, discord.Forbidden) as e:
                logger.error(f"Impossibile inviare il sondaggio finale per '{title}': {e}")
                self.db.mark_sent(uscita_id)
            except Exception as e:
                logger.error(f"Errore nel sondaggio finale per '{title}', riprovo al prossimo giro", exc_info=e)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

    async def send_final_poll(self, thread_id: int, poll_message_id: Optional[int], event_ts: int,
                              forced: bool = False, force_send: bool = False) -> int:
        # Rete di sicurezza: se la conferma è disattivata, non parte (salvo invio forzato da publish/mod)
        if not forced and not force_send and not self.db.is_final_enabled(thread_id):
            logger.info(f"Conferma disattivata per il thread {thread_id}: non inviata")
            return 0

        thread = self.bot.get_channel(thread_id) or await self.bot.fetch_channel(thread_id)

        # Menziona solo chi ha votato "Forse..."
        voters: dict[int, discord.abc.User] = {}
        if poll_message_id:
            poll_msg = await thread.fetch_message(poll_message_id)
            if poll_msg.poll:
                for answer in poll_msg.poll.answers:
                    if answer.text != ANSWER_MAYBE:
                        continue
                    async for user in answer.voters():
                        if not user.bot:
                            voters.setdefault(user.id, user)

        mentions = [u.mention for u in voters.values()]

        hours = math.floor((event_ts - time.time()) / 3600)
        hours = max(1, min(hours, MAX_POLL_HOURS))
        poll = discord.Poll(question="Confermi la tua presenza?", duration=timedelta(hours=hours))
        poll.add_answer(text=ANSWER_YES, emoji="✅")
        poll.add_answer(text=ANSWER_NO, emoji="❌")

        if forced:
            header = (
                f"📢 **Sondaggio di conferma!** L'evento è <t:{event_ts}:R> (<t:{event_ts}:F>)\n"
                "Confermate la vostra presenza:"
            )
        else:
            header = f"📢 **Domani è il grande giorno!** (<t:{event_ts}:F>)\nConfermate la vostra presenza:"

        if not mentions:
            msg = await thread.send(content=header, poll=poll)
            return msg.id

        chunks, current = [], header + "\n"
        for m in mentions:
            if len(current) + len(m) + 1 > 1900:
                chunks.append(current)
                current = ""
            current += m + " "
        chunks.append(current)

        for chunk in chunks[:-1]:
            await thread.send(content=chunk)
        msg = await thread.send(content=chunks[-1], poll=poll)
        return msg.id

    # ---------------------------------------------------------------------
    # Lista partecipanti
    # ---------------------------------------------------------------------

    @staticmethod
    def build_list_embed(title: str, url: str, names: list[str]) -> discord.Embed:
        lines = [f"`{i}.` {discord.utils.escape_markdown(n)}" for i, n in enumerate(names, 1)]

        text = ""
        for idx, line in enumerate(lines):
            if len(text) + len(line) + 1 > 3900:
                text += f"*...e altri {len(lines) - idx}*"
                break
            text += line + "\n"

        embed = discord.Embed(
            title=f"📋 Lista partecipanti — {title}"[:256],
            url=url,
            description=text or "*Nessun iscritto per ora.*",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"{len(names)} partecipanti")
        return embed

    async def _get_list_channel(self):
        return self.bot.get_channel(USCITE_LISTA_CHANNEL_ID) or await self.bot.fetch_channel(USCITE_LISTA_CHANNEL_ID)

    async def create_list_message(self, thread: discord.Thread, title: str) -> int:
        try:
            channel = await self._get_list_channel()
            msg = await channel.send(embed=self.build_list_embed(title, thread.jump_url, []))
            return msg.id
        except (discord.HTTPException, AttributeError) as e:
            logger.error("Impossibile creare il messaggio della lista", exc_info=e)
            return 0

    async def refresh_list(self, row):
        uscita_id, thread_id, poll_id, final_id, list_id, title = row
        thread = self.bot.get_channel(thread_id) or await self.bot.fetch_channel(thread_id)

        async def voters_of(message_id: int, text: str) -> set[int]:
            ids: set[int] = set()
            if not message_id:
                return ids
            try:
                msg = await thread.fetch_message(message_id)
            except discord.NotFound:
                return ids
            if msg.poll:
                for answer in msg.poll.answers:
                    if answer.text == text:
                        async for user in answer.voters():
                            if not user.bot:
                                ids.add(user.id)
            return ids

        yes = await voters_of(poll_id, ANSWER_YES) | await voters_of(final_id, ANSWER_YES)
        yes -= await voters_of(final_id, ANSWER_NO)   # il "No" della conferma ha la precedenza

        names = []
        for uid in yes:
            member = thread.guild.get_member(uid)
            names.append(member.display_name if member else f"utente {uid}")
        names.sort(key=str.casefold)

        embed = self.build_list_embed(title, thread.jump_url, names)

        channel = await self._get_list_channel()
        if list_id:
            try:
                await channel.get_partial_message(list_id).edit(embed=embed)
                return
            except discord.NotFound:
                pass

        msg = await channel.send(embed=embed)
        self.db.set_list_message(uscita_id, msg.id)

    def _schedule_refresh(self, message_id: int):
        row = self.db.get_by_poll_message(message_id)
        if not row:
            return
        uscita_id = row[0]
        old = self._refresh_tasks.get(uscita_id)
        if old and not old.done():
            old.cancel()
        self._refresh_tasks[uscita_id] = asyncio.create_task(self._debounced_refresh(row))

    async def _debounced_refresh(self, row):
        try:
            await asyncio.sleep(2)
            await self.refresh_list(row)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Errore nell'aggiornamento della lista", exc_info=e)

    @commands.Cog.listener()
    async def on_raw_poll_vote_add(self, payload: discord.RawPollVoteActionEvent):
        self._schedule_refresh(payload.message_id)

    @commands.Cog.listener()
    async def on_raw_poll_vote_remove(self, payload: discord.RawPollVoteActionEvent):
        self._schedule_refresh(payload.message_id)