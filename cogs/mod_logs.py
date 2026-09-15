import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone
from utils.server_system import ServerSystem


class ModLogs(commands.Cog):
    def __init__(self, bot: commands.Bot, server_system: ServerSystem):
        self.bot = bot
        self.server_system = server_system

    def _get_log_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        """Recupera il canale log configurato nel database."""
        row = self.server_system.get_log_channel(guild.id)
        if not row:
            return None
        return guild.get_channel(row[0])

    async def _find_audit_entry(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int | None = None):
        """Trova la voce corrispondente negli Audit Log per identificare l'esecutore."""
        if not guild.me.guild_permissions.view_audit_log:
            return None

        await asyncio.sleep(1)
        try:
            async for entry in guild.audit_logs(limit=5, action=action):
                if target_id is None or (entry.target and entry.target.id == target_id):
                    time_diff = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                    if time_diff < 15:
                        return entry
        except discord.HTTPException:
            pass
        return None

    # =========================================================================
    # 1. MESSAGE EVENTS
    # =========================================================================

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Deleted messages."""
        if not message.guild or message.author.bot:
            return

        log_channel = self._get_log_channel(message.guild)
        if not log_channel:
            return

        executor = message.author
        entry = await self._find_audit_entry(message.guild, discord.AuditLogAction.message_delete, message.author.id)
        if entry and entry.user:
            executor = entry.user

        embed = discord.Embed(
            title="🗑️ Messaggio Eliminato",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{message.author} ({message.author.id})", icon_url=message.author.display_avatar.url)
        embed.add_field(name="Canale", value=message.channel.mention, inline=True)
        embed.add_field(name="Eliminato da", value=executor.mention, inline=True)

        content = message.content if message.content else "*Nessun contenuto testuale*"
        if len(content) > 1024:
            content = content[:1020] + "..."
        embed.add_field(name="Contenuto", value=content, inline=False)

        if message.attachments:
            files_list = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
            embed.add_field(name="Allegati", value=files_list, inline=False)

        embed.set_footer(text=f"Message ID: {message.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        """Purged messages."""
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        log_channel = self._get_log_channel(guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(guild, discord.AuditLogAction.message_bulk_delete)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        channel = guild.get_channel(payload.channel_id)
        ch_mention = channel.mention if channel else f"`ID: {payload.channel_id}`"

        embed = discord.Embed(
            title="🧹 Messaggi Cancellati in Massa (Purge)",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Canale", value=ch_mention, inline=True)
        embed.add_field(name="Quantità", value=f"{len(payload.message_ids)} messaggi", inline=True)
        embed.add_field(name="Eseguito da", value=moderator, inline=True)

        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Edited messages."""
        if not before.guild or before.author.bot or before.content == after.content:
            return

        log_channel = self._get_log_channel(before.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="✏️ Messaggio Modificato",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{before.author} ({before.author.id})", icon_url=before.author.display_avatar.url)
        embed.add_field(name="Canale", value=before.channel.mention, inline=True)
        embed.add_field(name="Link", value=f"[Vai al messaggio]({after.jump_url})", inline=True)

        old_text = before.content[:1020] + "..." if len(before.content) > 1024 else (before.content or "*Vuoto*")
        new_text = after.content[:1020] + "..." if len(after.content) > 1024 else (after.content or "*Vuoto*")

        embed.add_field(name="Prima", value=old_text, inline=False)
        embed.add_field(name="Dopo", value=new_text, inline=False)
        embed.set_footer(text=f"Message ID: {before.id}")

        await log_channel.send(embed=embed)

    # =========================================================================
    # 2. SERVER EVENTS (Channels, Roles, Server & Emojis)
    # =========================================================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """Channel creation."""
        log_channel = self._get_log_channel(channel.guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="📁 Canale Creato",
            description=f"Il canale {channel.mention} (`{channel.name}`) è stato creato.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Tipo", value=str(channel.type).capitalize(), inline=True)
        embed.add_field(name="Creato da", value=moderator, inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Channel deletion."""
        log_channel = self._get_log_channel(channel.guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🗑️ Canale Eliminato",
            description=f"Il canale `#{channel.name}` è stato eliminato.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Eliminato da", value=moderator, inline=True)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        """Updated channel con tracciamento completo di proprietà e permessi."""
        log_channel = self._get_log_channel(after.guild)
        if not log_channel:
            return

        changes = []

        # =====================================================================
        # 1. PROPRIETÀ GENERALI
        # =====================================================================
        if before.name != after.name:
            changes.append(f"• **Nome:** `{before.name}` ➔ `{after.name}`")

        if hasattr(before, "topic") and hasattr(after, "topic") and before.topic != after.topic:
            b_topic = before.topic or "*Nessuno*"
            a_topic = after.topic or "*Nessuno*"
            changes.append(f"• **Topic:**\n  Prima: `{b_topic}`\n  Dopo: `{a_topic}`")

        if hasattr(before, "nsfw") and hasattr(after, "nsfw") and before.nsfw != after.nsfw:
            changes.append(f"• **NSFW:** `{'Sì' if before.nsfw else 'No'}` ➔ `{'Sì' if after.nsfw else 'No'}`")

        if hasattr(before, "slowmode_delay") and hasattr(after,
                                                         "slowmode_delay") and before.slowmode_delay != after.slowmode_delay:
            changes.append(f"• **Slowmode:** `{before.slowmode_delay}s` ➔ `{after.slowmode_delay}s`")

        if before.category != after.category:
            b_cat = before.category.name if before.category else "*Nessuna*"
            a_cat = after.category.name if after.category else "*Nessuna*"
            changes.append(f"• **Categoria:** `{b_cat}` ➔ `{a_cat}`")

        if hasattr(before, "bitrate") and hasattr(after, "bitrate") and before.bitrate != after.bitrate:
            changes.append(f"• **Bitrate:** `{before.bitrate // 1000}kbps` ➔ `{after.bitrate // 1000}kbps`")

        if hasattr(before, "user_limit") and hasattr(after, "user_limit") and before.user_limit != after.user_limit:
            b_limit = f"{before.user_limit} utenti" if before.user_limit else "Illimitato"
            a_limit = f"{after.user_limit} utenti" if after.user_limit else "Illimitato"
            changes.append(f"• **Limite Utenti:** `{b_limit}` ➔ `{a_limit}`")

        # =====================================================================
        # 2. PERMESSI (Overwrites per Ruoli e Membri)
        # =====================================================================
        perm_labels = {
            "view_channel": "Visualizzare il canale",
            "send_messages": "Inviare messaggi",
            "send_messages_in_threads": "Inviare messaggi nei thread",
            "create_public_threads": "Creare thread pubblici",
            "create_private_threads": "Creare thread privati",
            "embed_links": "Inserire link",
            "attach_files": "Allegare file",
            "add_reactions": "Aggiungere reazioni",
            "use_external_emojis": "Usare emoji esterne",
            "use_external_stickers": "Usare sticker esterni",
            "mention_everyone": "Menzionare @everyone e ruoli",
            "manage_messages": "Gestire messaggi",
            "manage_threads": "Gestire thread",
            "read_message_history": "Leggere cronologia messaggi",
            "send_tts_messages": "Inviare messaggi TTS",
            "connect": "Connettersi (Voce)",
            "speak": "Parlare (Voce)",
            "stream": "Condividere video / Schermo",
            "mute_members": "Mute membri",
            "deafen_members": "Deafen membri",
            "move_members": "Spostare membri",
            "manage_channels": "Gestire canale",
            "manage_permissions": "Gestire permessi"
        }

        def format_state(val: bool | None) -> str:
            if val is True:
                return "✅ Concesso"
            elif val is False:
                return "❌ Negato"
            return "⚪ Neutro"

        is_perm_action = False

        if before.overwrites != after.overwrites:
            all_targets = set(before.overwrites.keys()) | set(after.overwrites.keys())

            for target in all_targets:
                target_mention = target.mention if hasattr(target, "mention") else f"`{target.name}`"
                b_ow = before.overwrites.get(target)
                a_ow = after.overwrites.get(target)

                # Overwrite rimosso del tutto
                if b_ow and not a_ow:
                    changes.append(f"• **Permessi ripristinati/rimossi per:** {target_mention}")
                    is_perm_action = True
                    continue

                # Nuovo overwrite aggiunto
                if not b_ow and a_ow:
                    changes.append(f"• **Nuova configurazione permessi impostata per:** {target_mention}")
                    for perm, val in iter(a_ow):
                        if val is not None:
                            name_str = perm_labels.get(perm, perm.replace("_", " ").title())
                            changes.append(f"  └ `{name_str}`: {format_state(val)}")
                    is_perm_action = True
                    continue

                # Overwrite modificato
                if b_ow and a_ow and b_ow != a_ow:
                    sub_changes = []
                    b_dict = dict(iter(b_ow))
                    a_dict = dict(iter(a_ow))

                    for perm, after_val in a_dict.items():
                        before_val = b_dict.get(perm)
                        if before_val != after_val:
                            name_str = perm_labels.get(perm, perm.replace("_", " ").title())
                            sub_changes.append(
                                f"  └ `{name_str}`: {format_state(before_val)} ➔ {format_state(after_val)}"
                            )

                    if sub_changes:
                        changes.append(f"• **Permessi modificati per:** {target_mention}")
                        changes.extend(sub_changes)
                        is_perm_action = True

        if not changes:
            return

        # =====================================================================
        # 3. AUDIT LOG & INVIO
        # =====================================================================
        # Prova prima con l'azione per permessi se c'è stata una modifica permessi, altrimenti channel_update
        action = discord.AuditLogAction.overwrite_update if is_perm_action else discord.AuditLogAction.channel_update
        entry = await self._find_audit_entry(after.guild, action, after.id)
        if not entry and is_perm_action:
            entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.overwrite_delete, after.id)
        if not entry:
            entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.channel_update, after.id)

        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        full_description = f"Modifiche applicate a {after.mention}:\n\n" + "\n".join(changes)
        if len(full_description) > 4000:
            full_description = full_description[:3990] + "\n... *(altre modifiche omesse)*"

        embed = discord.Embed(
            title="⚙️ Canale Modificato",
            description=full_description,
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Modificato da", value=moderator, inline=True)
        embed.set_footer(text=f"Channel ID: {after.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        """Role creation."""
        log_channel = self._get_log_channel(role.guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(role.guild, discord.AuditLogAction.role_create, role.id)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🛡️ Ruolo Creato",
            description=f"Creato il ruolo {role.mention} (`{role.name}`).",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Creato da", value=moderator, inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        """Role deletion."""
        log_channel = self._get_log_channel(role.guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(role.guild, discord.AuditLogAction.role_delete, role.id)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🗑️ Ruolo Eliminato",
            description=f"Il ruolo `@{role.name}` è stato eliminato.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Eliminato da", value=moderator, inline=True)
        embed.set_footer(text=f"Role ID: {role.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        """Role updates."""
        log_channel = self._get_log_channel(after.guild)
        if not log_channel:
            return

        changes = []
        if before.name != after.name:
            changes.append(f"**Nome:** `{before.name}` ➔ `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Colore:** `{before.color}` ➔ `{after.color}`")
        if before.permissions != after.permissions:
            changes.append("**Permessi modificati**")

        if not changes:
            return

        entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.role_update, after.id)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🛡️ Ruolo Modificato",
            description=f"Modifiche applicate a {after.mention}:\n" + "\n".join(changes),
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Modificato da", value=moderator, inline=True)
        embed.set_footer(text=f"Role ID: {after.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        """Server updates."""
        log_channel = self._get_log_channel(after)
        if not log_channel:
            return

        changes = []
        if before.name != after.name:
            changes.append(f"**Nome Server:** `{before.name}` ➔ `{after.name}`")
        if before.icon != after.icon:
            changes.append("**Icona del server aggiornata**")
        if before.banner != after.banner:
            changes.append("**Banner del server aggiornato**")

        if not changes:
            return

        entry = await self._find_audit_entry(after, discord.AuditLogAction.guild_update)
        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🏰 Server Aggiornato",
            description="\n".join(changes),
            color=discord.Color.purple(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Modificato da", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild: discord.Guild, before: list[discord.Emoji], after: list[discord.Emoji]):
        """Emoji changes."""
        log_channel = self._get_log_channel(guild)
        if not log_channel:
            return

        entry = None
        action_desc = ""
        color = discord.Color.blue()

        if len(after) > len(before):
            added = [e for e in after if e not in before]
            entry = await self._find_audit_entry(guild, discord.AuditLogAction.emoji_create)
            action_desc = f"Aggiunta emoji: {added[0]} (`:{added[0].name}:`)"
            color = discord.Color.green()
        elif len(before) > len(after):
            removed = [e for e in before if e not in after]
            entry = await self._find_audit_entry(guild, discord.AuditLogAction.emoji_delete)
            action_desc = f"Rimossa emoji: `:{removed[0].name}:`"
            color = discord.Color.red()
        else:
            entry = await self._find_audit_entry(guild, discord.AuditLogAction.emoji_update)
            action_desc = "Nome o stato di un'emoji aggiornato."

        moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="😀 Modifica Emoji",
            description=action_desc,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Eseguito da", value=moderator, inline=True)
        await log_channel.send(embed=embed)

    # =========================================================================
    # 3. MEMBER EVENTS & MOVEMENT
    # =========================================================================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Members joining."""
        log_channel = self._get_log_channel(member.guild)
        if not log_channel:
            return

        embed = discord.Embed(
            title="📥 Nuovo Membro Entrato",
            description=f"{member.mention} ({member.name}) si è unito al server.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Account Creato", value=discord.utils.format_dt(member.created_at, style="R"), inline=True)
        embed.set_author(name=f"{member} ({member.id})", icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Members leaving & Kicks."""
        log_channel = self._get_log_channel(member.guild)
        if not log_channel:
            return

        kick_entry = await self._find_audit_entry(member.guild, discord.AuditLogAction.kick, member.id)

        if kick_entry:
            staff = kick_entry.user.mention if kick_entry.user else "*Sconosciuto*"
            reason = kick_entry.reason if kick_entry.reason else "*Nessun motivo specificato*"

            embed = discord.Embed(
                title="👢 Membro Espulso (Kick)",
                description=f"{member.mention} è stato espulso dal server.",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Moderatore", value=staff, inline=True)
            embed.add_field(name="Motivo", value=reason, inline=False)
        else:
            embed = discord.Embed(
                title="📤 Membro Uscito",
                description=f"{member.mention} ({member.name}) ha lasciato il server.",
                color=discord.Color.light_grey(),
                timestamp=datetime.now(timezone.utc)
            )

        embed.set_author(name=f"{member} ({member.id})", icon_url=member.display_avatar.url)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Role updates, Name changes, Avatar changes, Timeouts."""
        log_channel = self._get_log_channel(after.guild)
        if not log_channel:
            return

        # 1. Timeout / Timeout Revocato
        if before.timed_out_until != after.timed_out_until:
            entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.member_update, after.id)
            staff = entry.user.mention if (entry and entry.user) else "*Sconosciuto / Bot*"
            reason = entry.reason if (entry and entry.reason) else "*Nessun motivo specificato*"

            if after.timed_out_until:
                embed = discord.Embed(
                    title="🔇 Membro Mutato (Timeout)",
                    description=f"{after.mention} è stato messo in timeout.",
                    color=discord.Color.dark_orange(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Moderatore", value=staff, inline=True)
                embed.add_field(name="Scadenza", value=discord.utils.format_dt(after.timed_out_until, style="R"), inline=True)
                embed.add_field(name="Motivo", value=reason, inline=False)
            else:
                embed = discord.Embed(
                    title="🔊 Timeout Rimosso",
                    description=f"Il timeout di {after.mention} è stato rimosso.",
                    color=discord.Color.green(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.add_field(name="Moderatore", value=staff, inline=True)

            embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
            await log_channel.send(embed=embed)
            return

        # 2. Ruoli membro modificati
        if before.roles != after.roles:
            entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.member_role_update, after.id)
            moderator = entry.user.mention if (entry and entry.user) else "*Sconosciuto / Bot*"

            added_roles = [r.mention for r in after.roles if r not in before.roles]
            removed_roles = [r.mention for r in before.roles if r not in after.roles]

            embed = discord.Embed(
                title="🛡️ Ruoli Membro Modificati",
                description=f"Ruoli aggiornati per {after.mention}:",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
            if added_roles:
                embed.add_field(name="Ruoli Aggiunti", value=", ".join(added_roles), inline=False)
            if removed_roles:
                embed.add_field(name="Ruoli Rimossi", value=", ".join(removed_roles), inline=False)
            embed.add_field(name="Modificato da", value=moderator, inline=False)
            await log_channel.send(embed=embed)
            return

        # 3. Cambio Nickname del server
        if before.nick != after.nick:
            entry = await self._find_audit_entry(after.guild, discord.AuditLogAction.member_update, after.id)
            moderator = entry.user.mention if (entry and entry.user) else after.mention

            embed = discord.Embed(
                title="🏷️ Nickname Modificato",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
            embed.add_field(name="Prima", value=f"`{before.nick or before.name}`", inline=True)
            embed.add_field(name="Dopo", value=f"`{after.nick or after.name}`", inline=True)
            embed.add_field(name="Modificato da", value=moderator, inline=False)
            await log_channel.send(embed=embed)
            return

        # 4. Cambio Avatar del server
        if before.guild_avatar != after.guild_avatar:
            embed = discord.Embed(
                title="🖼️ Avatar Server Modificato",
                description=f"{after.mention} ha modificato il suo avatar personalizzato nel server.",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
            if after.guild_avatar:
                embed.set_thumbnail(url=after.guild_avatar.url)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Global Name & Global Avatar changes."""
        # Se cambia username o avatar globale, invia il log in ogni gilda comune che ha il canale attivo
        for guild in self.bot.guilds:
            if not guild.get_member(after.id):
                continue

            log_channel = self._get_log_channel(guild)
            if not log_channel:
                continue

            if before.name != after.name or before.discriminator != after.discriminator:
                embed = discord.Embed(
                    title="👤 Username Globale Modificato",
                    color=discord.Color.dark_grey(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
                embed.add_field(name="Prima", value=f"`{before}`", inline=True)
                embed.add_field(name="Dopo", value=f"`{after}`", inline=True)
                await log_channel.send(embed=embed)

            if before.avatar != after.avatar:
                embed = discord.Embed(
                    title="🖼️ Avatar Globale Modificato",
                    description=f"{after.mention} ha cambiato l'immagine del profilo globale.",
                    color=discord.Color.dark_grey(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=f"{after} ({after.id})", icon_url=after.display_avatar.url)
                embed.set_thumbnail(url=after.display_avatar.url)
                await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        """Member bans."""
        log_channel = self._get_log_channel(guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(guild, discord.AuditLogAction.ban, user.id)
        staff = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"
        reason = entry.reason if (entry and entry.reason) else "*Nessun motivo specificato*"

        embed = discord.Embed(
            title="🔨 Membro Bannato",
            description=f"{user.mention} è stato bandito dal server.",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.add_field(name="Moderatore", value=staff, inline=True)
        embed.add_field(name="Motivo", value=reason, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        """Member unbans."""
        log_channel = self._get_log_channel(guild)
        if not log_channel:
            return

        entry = await self._find_audit_entry(guild, discord.AuditLogAction.unban, user.id)
        staff = entry.user.mention if (entry and entry.user) else "*Sconosciuto*"

        embed = discord.Embed(
            title="🔓 Membro Sbannato",
            description=f"Il ban di {user.mention} è stato revocato.",
            color=discord.Color.teal(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.add_field(name="Moderatore", value=staff, inline=True)
        await log_channel.send(embed=embed)

        # =========================================================================
        # 4. VOICE EVENTS (Join, Leave, Server Mute/Deafen)
        # =========================================================================

        @commands.Cog.listener()
        async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                        after: discord.VoiceState):
            """Gestisce Join, Leave e azioni di moderazione vocale (Server Mute/Deafen)."""
            if member.bot:
                return

            log_channel = self._get_log_channel(member.guild)
            if not log_channel:
                return

            embed = discord.Embed(timestamp=datetime.now(timezone.utc))
            embed.set_author(name=f"{member} ({member.id})", icon_url=member.display_avatar.url)

            # ---------------------------------------------------------------------
            # A. MODERAZIONE: Server Mute (Silenzia nel server)
            # ---------------------------------------------------------------------
            if before.mute != after.mute:
                # Ricerca specifica dell'entry di member_update negli audit log
                staff = "*Sconosciuto / Non presente negli audit*"
                reason = "*Nessun motivo specificato*"

                if member.guild.me.guild_permissions.view_audit_log:
                    await asyncio.sleep(1.5)  # Discord impiega un momento a scrivere l'audit log
                    try:
                        async for entry in member.guild.audit_logs(limit=10,
                                                                   action=discord.AuditLogAction.member_update):
                            if entry.target and entry.target.id == member.id:
                                # Controlla se questa voce riguarda specificamente il cambio di 'mute'
                                if hasattr(entry.after, "mute") or hasattr(entry.before, "mute"):
                                    time_diff = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                                    if time_diff < 15:
                                        staff = entry.user.mention if entry.user else staff
                                        reason = entry.reason or reason
                                        break
                    except discord.HTTPException:
                        pass

                channel_str = after.channel.mention if after.channel else (
                    before.channel.mention if before.channel else "`Nessun canale`")

                if after.mute:
                    embed.title = "🎙️ Membro Silenziato nel Server (Server Mute)"
                    embed.description = f"{member.mention} è stato silenziato da uno staffer."
                    embed.color = discord.Color.dark_orange()
                else:
                    embed.title = "🎙️ Membro Riattivato nel Server (Server Unmute)"
                    embed.description = f"Il muto server a {member.mention} è stato rimosso."
                    embed.color = discord.Color.green()

                embed.add_field(name="Canale", value=channel_str, inline=True)
                embed.add_field(name="Moderatore", value=staff, inline=True)
                embed.add_field(name="Motivo", value=reason, inline=False)
                await log_channel.send(embed=embed)
                return

            # ---------------------------------------------------------------------
            # B. MODERAZIONE: Server Deafen (Insonorizza nel server)
            # ---------------------------------------------------------------------
            if before.deaf != after.deaf:
                staff = "*Sconosciuto / Non presente negli audit*"
                reason = "*Nessun motivo specificato*"

                if member.guild.me.guild_permissions.view_audit_log:
                    await asyncio.sleep(1.5)
                    try:
                        async for entry in member.guild.audit_logs(limit=10,
                                                                   action=discord.AuditLogAction.member_update):
                            if entry.target and entry.target.id == member.id:
                                if hasattr(entry.after, "deaf") or hasattr(entry.before, "deaf"):
                                    time_diff = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                                    if time_diff < 15:
                                        staff = entry.user.mention if entry.user else staff
                                        reason = entry.reason or reason
                                        break
                    except discord.HTTPException:
                        pass

                channel_str = after.channel.mention if after.channel else (
                    before.channel.mention if before.channel else "`Nessun canale`")

                if after.deaf:
                    embed.title = "🎧 Membro Insonorizzato nel Server (Server Deafen)"
                    embed.description = f"{member.mention} è stato insonorizzato dallo staff."
                    embed.color = discord.Color.dark_red()
                else:
                    embed.title = "🎧 Membro Dis-insonorizzato (Server Undeafen)"
                    embed.description = f"L'insonorizzazione server a {member.mention} è stata revocata."
                    embed.color = discord.Color.green()

                embed.add_field(name="Canale", value=channel_str, inline=True)
                embed.add_field(name="Moderatore", value=staff, inline=True)
                embed.add_field(name="Motivo", value=reason, inline=False)
                await log_channel.send(embed=embed)
                return

            # ---------------------------------------------------------------------
            # C. INGRESSO CANALE VOCALE
            # ---------------------------------------------------------------------
            if before.channel is None and after.channel is not None:
                embed.title = "🔊 Ingresso Canale Vocale"
                embed.description = f"{member.mention} è entrato nel canale vocale {after.channel.mention}."
                embed.color = discord.Color.green()
                embed.add_field(name="Canale", value=f"`{after.channel.name}` (ID: {after.channel.id})", inline=False)
                await log_channel.send(embed=embed)
                return

            # ---------------------------------------------------------------------
            # D. USCITA CANALE VOCALE (o Disconnessione Forzata)
            # ---------------------------------------------------------------------
            if before.channel is not None and after.channel is None:
                embed.title = "🔇 Uscita Canale Vocale"
                embed.description = f"{member.mention} ha lasciato il canale vocale `{before.channel.name}`."
                embed.color = discord.Color.red()
                embed.add_field(name="Canale", value=f"`{before.channel.name}` (ID: {before.channel.id})", inline=False)

                entry = await self._find_audit_entry(member.guild, discord.AuditLogAction.member_disconnect, member.id)
                if entry and entry.user:
                    embed.add_field(name="Disconnesso da", value=entry.user.mention, inline=True)

                await log_channel.send(embed=embed)
                return


async def setup(bot: commands.Bot):
    pass