import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import asyncio

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.bans = True
intents.audit_logs = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== SUNUCU VE LOG KANALI AYARLARI ====================
TOKEN = "MTU2MzIxMjUxMjYzODI3OTg1Mg.GgAK2t.g8YGgAjtJzq9fIvuu4ZRY0C06-RGozSLR3tTho"
GUILD_ID = 1562558097690460321          # Sunucunun ID'si
OTOROL_ID = 1562824132796612678         # Üye Rolü ID'si
SAFE_ROLE_ID = 1562922053571580046      # Safe Rol ID'si

# 📂 GÖRSELDEKİNE BENZER DETAYLI LOG KANALI ID'LERİ
# (Aşağıdaki ID'leri Discord'daki ilgili kanal ID'leriyle değiştireceksin)
LOG_CHANNELS = {
    "guard": 123456789012345678,         # GUARD-LOG
    "antibot": 123456789012345678,     # ANTI-BOT-LOG
    "channel_del": 123456789012345678, # CHANNEL-DELETE-LOG
    "channel_create": 123456789012345678,# CHANNEL-CREATE-LOG
    "channel_upd": 123456789012345678, # CHANNEL-GUNCELLEME-LOG
    "rol_del": 123456789012345678,     # ROL-DELETE-LOG
    "rol_create": 123456789012345678,  # ROL-CREATE-LOG
    "rol_upd": 123456789012345678,     # ROL-UPDATE-LOG
    "ban": 123456789012345678,         # BAN-LOG
    "unban": 123456789012345678,       # UNBAN-LOG
    "member": 123456789012345678,      # MEMBER-LOG (Giriş/Çıkış)
    "message": 123456789012345678,     # MESSAGE-LOG (Reklam/Silinen mesajlar)
    "voice": 123456789012345678,       # VOICE-LOG (/sesgir, /sescık)
    "server_upd": 123456789012345678,  # SERVER-UPDATE-LOG
    "webhook": 123456789012345678      # WEBHOOK-LOG
}

# Korumadan muaf tutulacak Kurucu / Geliştirici ID'leri
WHITELIST = [
    123456789012345678,  # Kendi Discord ID'niz
]

LINK_BLOCKS = ["discord.gg/", "discord.com/invite/", "http://", "https://", "www."]
# ==================================================================


@bot.event
async def on_ready():
    print(f"========================================")
    print(f" Guard Botu Aktif: {bot.user.name}")
    print(f" Sunucu ID: {GUILD_ID}")
    print(f"========================================")
    
    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"⚡ {len(synced)} Slash komutu senkronize edildi.")
    except Exception as e:
        print(f"❌ Slash komutları yüklenirken hata: {e}")

    await bot.change_presence(activity=discord.Game(name="🛡️ Pack Guard Protection"))

# --- LOG GÖNDERME FONKSİYONU ---
async def send_log(guild, log_type, title, description, color=discord.Color.red()):
    channel_id = LOG_CHANNELS.get(log_type)
    if channel_id:
        log_channel = guild.get_channel(channel_id)
        if log_channel:
            embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.datetime.utcnow())
            embed.set_footer(text=f"Vox Guard System • {log_type.upper()}")
            await log_channel.send(embed=embed)

def is_safe_user(member: discord.Member):
    if not member:
        return False
    if member.id in WHITELIST:
        return True
    if any(role.id == SAFE_ROLE_ID for role in member.roles):
        return True
    return False


# ==================== ÖZEL KOMUT: /safever ====================
@bot.tree.command(name="safever", description="Sadece sunucu sahibinin kullanabileceği safe rolü verme komutu.")
@app_commands.describe(member="Safe rolü verilecek üye")
async def safe_ver(interaction: discord.Interaction, member: discord.Member):
    if interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("❌ Bu komutu **sadece sunucu sahibi** kullanabilir!", ephemeral=True)
    
    safe_role = interaction.guild.get_role(SAFE_ROLE_ID)
    if not safe_role:
        return await interaction.response.send_message("❌ Ayarlanan `SAFE_ROLE_ID` sunucuda bulunamadı!", ephemeral=True)

    try:
        await member.add_roles(safe_role, reason=f"Sunucu sahibi {interaction.user.name} tarafından safe rolü verildi.")
        await interaction.response.send_message(f"✅ **{member.name}** adlı kullanıcıya başarıyla safe rolü verildi.", ephemeral=True)
        await send_log(
            interaction.guild, "guard",
            "🛡️ Safe Rol Verildi", 
            f"**Yetki Verilen Üye:** {member.mention} (`{member.id}`)\n"
            f"**İşlemi Yapan (Kurucu):** {interaction.user.mention}\n"
            f"**Verilen Rol:** {safe_role.mention}", 
            color=discord.Color.purple()
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Rol verilirken hata oluştu: {e}", ephemeral=True)


# ==================== SES KANAL KOMUTLARI ====================

@bot.tree.command(name="sesgir", description="Botu bulunduğun ses kanalına sokar ve sabit tutar.")
async def ses_gir(interaction: discord.Interaction):
    if not is_safe_user(interaction.user):
        return await interaction.response.send_message("❌ Yetkiniz yok!", ephemeral=True)

    if not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("❌ Önce bir ses kanalına girmelisin!", ephemeral=True)

    channel = interaction.user.voice.channel

    try:
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect(reconnect=True, self_deaf=True)

        await interaction.response.send_message(f"🔊 **{channel.name}** kanalına giriş yapıldı[cite: 1]!", ephemeral=True)
        await send_log(interaction.guild, "voice", "🔊 Ses Kanalına Girildi", f"**Kanal:** `{channel.name}`\n**Yetkili:** {interaction.user.mention}", color=discord.Color.blue())
    except Exception as e:
        await interaction.response.send_message(f"❌ Hata: {e}", ephemeral=True)

@bot.tree.command(name="sescık", description="Botu ses kanalından çıkarır.")
async def ses_cik(interaction: discord.Interaction):
    if not is_safe_user(interaction.user):
        return await interaction.response.send_message("❌ Yetkiniz yok!", ephemeral=True)

    if interaction.guild.voice_client:
        try:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("🔌 Ses kanalından çıkış yapıldı.", ephemeral=True)
            await send_log(interaction.guild, "voice", "🔌 Ses Kanalından Çıkıldı", f"**Yetkili:** {interaction.user.mention}", color=discord.Color.dark_red())
        except Exception as e:
            await interaction.response.send_message(f"❌ Hata: {e}", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Bot zaten bir ses kanalında değil!", ephemeral=True)


# ==================== MODERASYON KOMUTLARI (BAN / KICK / TIMEOUT) ====================

@bot.tree.command(name="ban", description="Sunucudan bir kullanıcıyı yasaklar.")
@app_commands.describe(user="Yasaklanacak kullanıcı", reason="Sebep")
async def ban_command(interaction: discord.Interaction, user: discord.User, reason: str = "Sebep yok"):
    if not is_safe_user(interaction.user):
        return await interaction.response.send_message("❌ Yetkiniz yok!", ephemeral=True)
    try:
        await interaction.guild.ban(user, reason=reason)
        await interaction.response.send_message(f"✅ **{user.name}** banlandı.", ephemeral=True)
        await send_log(interaction.guild, "ban", "🔨 Kullanıcı Banlandı", f"**Banlanan:** {user.mention}\n**Yetkili:** {interaction.user.mention}\n**Sebep:** {reason}", color=discord.Color.orange())
    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kullanıcıyı atar.")
@app_commands.describe(member="Atılacak üye", reason="Sebep")
async def kick_command(interaction: discord.Interaction, member: discord.Member, reason: str = "Sebep yok"):
    if not is_safe_user(interaction.user):
        return await interaction.response.send_message("❌ Yetkiniz yok!", ephemeral=True)
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👞 **{member.name}** atıldı.", ephemeral=True)
        await send_log(interaction.guild, "guard", "👞 Kullanıcı Atıldı", f"**Atılan:** {member.mention}\n**Yetkili:** {interaction.user.mention}\n**Sebep:** {reason}", color=discord.Color.gold())
    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)

@bot.tree.command(name="timeout", description="Kullanıcıyı susturur.")
@app_commands.describe(member="Üye", dakika="Dakika", reason="Sebep")
async def timeout_command(interaction: discord.Interaction, member: discord.Member, dakika: int, reason: str = "Sebep yok"):
    if not is_safe_user(interaction.user):
        return await interaction.response.send_message("❌ Yetkiniz yok!", ephemeral=True)
    try:
        await member.timeout(datetime.timedelta(minutes=dakika), reason=reason)
        await interaction.response.send_message(f"🔇 **{member.name}** {dakika} dk susturuldu.", ephemeral=True)
        await send_log(interaction.guild, "guard", "🔇 Susturuldu", f"**Üye:** {member.mention}\n**Süre:** {dakika} dk\n**Yetkili:** {interaction.user.mention}", color=discord.Color.dark_grey())
    except Exception as e:
        await interaction.response.send_message(f"Hata: {e}", ephemeral=True)


# ==================== KORUMA VE LOG EVENTLERİ ====================

# Üye Katılımı / Bot Ekleme ve Otorol
@bot.event
async def on_member_join(member):
    if member.bot:
        guild = member.guild
        async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            executor = entry.user
            if isinstance(executor, discord.Member) and not is_safe_user(executor):
                try:
                    await member.ban(reason="Guard: İzinsiz Bot")
                    await executor.edit(roles=[], reason="Guard: İzinsiz Bot Ekledi")
                    await send_log(
                        guild, "antibot",
                        "🚨 İzinsiz Bot Engellendi", 
                        f"**Bot:** {member.mention} (`{member.id}`)\n"
                        f"**Ekleyen:** {executor.mention}\n⚡ *Bot banlandı, yetkilinin rolleri alındı.*"
                    )
                except Exception as e:
                    print(e)
        return

    # Member Log (Giriş)
    await send_log(member.guild, "member", "📥 Üye Katıldı", f"**Üye:** {member.mention} (`{member.id}`)", color=discord.Color.green())

    # Otorol
    role = member.guild.get_role(OTOROL_ID)
    if role:
        try:
            await member.add_roles(role, reason="Otorol Sistemi")
        except Exception as e:
            print(e)

# Üye Ayrılma Logu
@bot.event
async def on_member_remove(member):
    await send_log(member.guild, "member", "📤 Üye Ayrıldı", f"**Üye:** {member.mention} (`{member.id}`)", color=discord.Color.red())

# Reklam / Mesaj Engeli
@bot.event
async def on_message(message):
    if message.author.bot or (isinstance(message.author, discord.Member) and is_safe_user(message.author)):
        await bot.process_commands(message)
        return

    if any(link in message.content.lower() for link in LINK_BLOCKS):
        try:
            await message.delete()
            await message.channel.send(f"⚠️ {message.author.mention}, reklam yasak!", delete_after=5)
            await send_log(
                message.guild, "message",
                "⚠️ Reklam Engellendi", 
                f"**Kullanıcı:** {message.author.mention}\n**Kanal:** {message.channel.mention}\n**Mesaj:** `{message.content}`"
            )
        except Exception as e:
            print(e)
            
    await bot.process_commands(message)

# Kanal Silme Koruması
@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    async for entry in guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        executor = entry.user
        if isinstance(executor, discord.Member) and not is_safe_user(executor):
            try:
                new_channel = await channel.clone(reason="Guard: Kanal Kurtarıldı")
                await new_channel.edit(position=channel.position)
                await executor.edit(roles=[], reason="Guard: Kanal Sildi")
                await send_log(
                    guild, "channel_del",
                    "🚨 Kanal Silindi & Kurtarıldı", 
                    f"**Kanal:** `{channel.name}`\n**Silen:** {executor.mention}\n⚡ *Kanal geri açıldı, yetkileri alındı.*"
                )
            except Exception as e:
                print(e)

# Kanal Oluşturma Logu
@bot.event
async def on_guild_channel_create(channel):
    await send_log(channel.guild, "channel_create", "📁 Kanal Oluşturuldu", f"**Kanal:** `{channel.name}` (`{channel.id}`)", color=discord.Color.blue())

# Kanal Güncelleme Logu
@bot.event
async def on_guild_channel_update(before, after):
    if before.name != after.name:
        await send_log(before.guild, "channel_upd", "✏️ Kanal Güncellendi", f"**Eski Adı:** `{before.name}`\n**Yeni Adı:** `{after.name}`", color=discord.Color.gold())

# Rol Silme Koruması
@bot.event
async def on_guild_role_delete(role):
    guild = role.guild
    async for entry in guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        executor = entry.user
        if isinstance(executor, discord.Member) and not is_safe_user(executor):
            try:
                await guild.create_role(name=role.name, permissions=role.permissions, color=role.color, hoist=role.hoist, mentionable=role.mentionable, reason="Guard: Rol Kurtarıldı")
                await executor.edit(roles=[], reason="Guard: Rol Sildi")
                await send_log(
                    guild, "rol_del",
                    "🚨 Rol Silindi & Kurtarıldı", 
                    f"**Rol:** `{role.name}`\n**Silen:** {executor.mention}\n⚡ *Rol yeniden açıldı, yetkileri alındı.*"
                )
            except Exception as e:
                print(e)

# Rol Oluşturma Logu
@bot.event
async def on_guild_role_create(role):
    await send_log(role.guild, "rol_create", "➕ Rol Oluşturuldu", f"**Rol:** `{role.name}` (`{role.id}`)", color=discord.Color.green())

# Rol Güncelleme Logu
@bot.event
async def on_guild_role_update(before, after):
    if before.name != after.name or before.permissions != after.permissions:
        await send_log(before.guild, "rol_upd", "🔄 Rol Güncellendi", f"**Rol:** `{after.name}`", color=discord.Color.orange())

# Ban Açılma (Unban) Logu
@bot.event
async def on_member_unban(guild, user):
    await send_log(guild, "unban", "🔓 Ban Kaldırıldı", f"**Kullanıcı:** {user.name} (`{user.id}`)", color=discord.Color.green())

# Webhook Güncelleme Logu
@bot.event
async def on_webhooks_update(channel):
    await send_log(channel.guild, "webhook", "🔗 Webhook Güncellendi", f"**Kanal:** {channel.mention}", color=discord.Color.purple())

# Sunucu Güncelleme Logu
@bot.event
async def on_guild_update(before, after):
    if before.name != after.name or before.icon != after.icon:
        await send_log(after, "server_upd", "⚙️ Sunucu Bilgileri Güncellendi", f"**Eski İsim:** {before.name}\n**Yeni İsim:** {after.name}", color=discord.Color.gold())

bot.run(TOKEN)