import os
os.environ['SSL_CERT_FILE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

import ssl
import threading
import asyncio
import re

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

import aiohttp
from aiohttp import TCPConnector

_orig_tcp_init = TCPConnector.__init__
def _new_tcp_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    if 'verify_ssl' in kwargs:
        del kwargs['verify_ssl']
    _orig_tcp_init(self, *args, **kwargs)
TCPConnector.__init__ = _new_tcp_init

import discord
from discord import app_commands
from discord.ext import commands

try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# --- 1. WEB SUNUCUSU (7/24 Uptime) ---
if FLASK_AVAILABLE:
    app = Flask('')

    @app.route('/')
    def home():
        return "Storm-Guard Full Güvenlik Sistemleri Aktif!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    def keep_alive():
        t = threading.Thread(target=run)
        t.start()
else:
    def keep_alive():
        print("⚠️ Flask bulunamadı.")

# --- 2. BOT AYARLARI VE KONFİGÜRASYON ---
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

GUILD_ID = 1562558097690460321
OTOROL_ID = 1562824132796612678
SAFE_ROLE_ID = 1562922053571580046  # 👉 Safe Rolü ID'n

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.moderation = True
intents.bans = True

bot = commands.Bot(command_prefix='!', intents=intents)

ALLOWED_BOTS = set()
GLOBAL_BAN_LIST = set()
CHAT_SAFE_USERS = set()
USER_WARNINGS = {} 
MANUAL_AUTH = set()

KUFUR_LISTESI = ["amk", "aq", "orospu", "piç", "sik", "yarak", "oç", "amq", "sikik", "amina", "anan"]
REKLAM_REGEX = re.compile(r"(https?://|discord\.gg/|discord\.com/invite/)")

@bot.event
async def on_ready():
    print(f'{bot.user.name} Full Koruma Sistemleri Aktif!')
    try:
        synced = await bot.tree.sync()
        print(f"🔗 {len(synced)} adet Slash (/) komutu senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

async def send_log(guild, channel_name, embed):
    chan = discord.utils.get(guild.text_channels, name=channel_name)
    if chan:
        try:
            await chan.send(embed=embed)
        except:
            pass

def has_safe_role(member: discord.Member) -> bool:
    if not member:
        return False
    if member.id == member.guild.owner_id:
        return True
    safe_role = member.guild.get_role(SAFE_ROLE_ID)
    if safe_role and safe_role in member.roles:
        return True
    return False

# --- 3. SAĞ TIK BAN & KICK KORUMASI ---
@bot.event
async def on_member_ban(guild, user):
    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            actor = entry.user
            if actor.bot or actor.id == guild.owner_id:
                return
            member = guild.get_member(actor.id)
            if not member:
                return
            if member.id in MANUAL_AUTH:
                MANUAL_AUTH.remove(member.id)
                return
            if not has_safe_role(member):
                await guild.unban(user, reason="Storm-Guard: Yetkisiz ban kaldırıldı.")
                await guild.ban(member, reason="Storm-Guard: Safe rolü olmadan sağ tık ban denemesi!")
                embed = discord.Embed(
                    title="🚨 İzinsiz Sağ Tık Ban Engellendi!",
                    description=f"**Yetkisiz Yetkili:** {member.mention}\n**Hedef:** {user.name}\n*İşlem geri alındı ve yetkisiz kişi banlandı.*",
                    color=discord.Color.red()
                )
                await send_log(guild, "ban-logs", embed)
                return
    except Exception as e:
        print(f"Ban koruma hatası: {e}")

@bot.event
async def on_member_remove(member):
    # Sağ tık kick kontrolü
    await asyncio.sleep(1.2)
    try:
        async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                actor = entry.user
                if actor.bot or actor.id == member.guild.owner_id:
                    return
                manager = member.guild.get_member(actor.id)
                if manager and not has_safe_role(manager):
                    await member.guild.ban(manager, reason="Storm-Guard: Safe rolü olmadan sağ tık kick denemesi!")
                    embed = discord.Embed(
                        title="🚨 İzinsiz Sağ Tık Kick Engellendi!",
                        description=f"**Yetkisiz Yetkili:** {manager.mention}\n**Atılan Üye:** {member.name}\n*Yetkisiz kişi sunucudan yasaklandı.*",
                        color=discord.Color.red()
                    )
                    await send_log(member.guild, "ban-logs", embed)
                    return
    except:
        pass

    # Normal üye çıkış logu
    if member.guild.id == GUILD_ID:
        leave_embed = discord.Embed(
            title="📤 Üye Sunucudan Ayrıldı",
            description=f"{member.mention} ({member.name}) sunucudan ayrıldı.",
            color=discord.Color.orange()
        )
        leave_embed.set_thumbnail(url=member.display_avatar.url)
        await send_log(member.guild, "member-logs", leave_embed)

# --- 4. SAĞ TIK ROL VERME / ALMA KORUMASI ---
@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return

    await asyncio.sleep(1.0)
    try:
        async for entry in after.guild.audit_logs(limit=3, action=discord.AuditLogAction.member_role_update):
            actor = entry.user
            if actor.bot or actor.id == after.guild.owner_id:
                return
            manager = after.guild.get_member(actor.id)
            if not manager:
                return
            if manager.id in MANUAL_AUTH:
                MANUAL_AUTH.remove(manager.id)
                return

            if not has_safe_role(manager):
                # Değişen rolleri eski haline (before) geri döndür
                try:
                    await after.edit(roles=before.roles, reason="Storm-Guard: Yetkisiz rol değişimi geri alındı.")
                except:
                    pass

                # Rol vermeye/almaya çalışan yetkisiz kişiyi banla
                try:
                    await after.guild.ban(manager, reason="Storm-Guard: Safe rolü olmadan izinsiz rol verme/alma denemesi!")
                except:
                    pass

                embed = discord.Embed(
                    title="🚨 İzinsiz Rol İşlemi Engellendi!",
                    description=f"**Yetkisiz Yetkili:** {manager.mention}\n**Hedef Üye:** {after.mention}\n*Yapılan rol değişikliği geri alındı ve yetkisiz kişi banlandı.*",
                    color=discord.Color.red()
                )
                await send_log(after.guild, "rol-update-logs", embed)
                return
    except Exception as e:
        print(f"Rol koruma hatası: {e}")

# --- 5. KANAL VE ROL SİLME KORUMASI ---
@bot.event
async def on_guild_channel_delete(channel):
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        member = channel.guild.get_member(user.id)
        if member and not has_safe_role(member):
            try:
                await channel.guild.ban(member, reason="Storm-Guard: Safe rolü olmadan izinsiz kanal silme!")
                embed = discord.Embed(title="🚨 İzinsiz Kanal Silme", description=f"{member.mention} Safe rolü olmadığı halde kanalı sildiği için banlandı!", color=discord.Color.red())
                await send_log(channel.guild, "guard-log", embed)
            except:
                pass
            return

@bot.event
async def on_guild_role_delete(role):
    await asyncio.sleep(1)
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        user = entry.user
        member = role.guild.get_member(user.id)
        if member and not has_safe_role(member):
            try:
                await role.guild.ban(member, reason="Storm-Guard: Safe rolü olmadan izinsiz rol silme!")
                embed = discord.Embed(title="🚨 İzinsiz Rol Silme", description=f"{member.mention} Safe rolü olmadığı halde rolü sildiği için banlandı!", color=discord.Color.red())
                await send_log(role.guild, "guard-log", embed)
            except:
                pass
            return

# --- 6. ÜYE GİRİŞ & ANTI-BOT ---
@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return

    if member.id in GLOBAL_BAN_LIST:
        try:
            await member.ban(reason="Storm-Guard: Global Ban")
        except:
            pass
        return

    join_embed = discord.Embed(
        title="📥 Üye Sunucuya Katıldı",
        description=f"{member.mention} ({member.name}) sunucuya giriş yaptı.",
        color=discord.Color.green()
    )
    join_embed.set_thumbnail(url=member.display_avatar.url)
    await send_log(member.guild, "member-logs", join_embed)

    if member.bot:
        if member.id in ALLOWED_BOTS:
            ALLOWED_BOTS.remove(member.id)
            return
        try:
            async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.bot_add):
                adder = entry.user
                if adder.id == member.guild.owner_id:
                    return
                member_adder = member.guild.get_member(adder.id)
                
                bot_embed = discord.Embed(
                    title="🤖 İzinsiz Bot Tespit Edildi!",
                    description=f"**Bot:** {member.mention}\n**Ekleyen:** {member_adder.mention if member_adder else 'Bilinmiyor'}",
                    color=discord.Color.red()
                )
                await send_log(member.guild, "anti-bot-log", bot_embed)

                if not member_adder or not has_safe_role(member_adder):
                    await member.ban(reason="Storm-Guard: Yetkisiz bot")
                    if member_adder:
                        await member.guild.ban(member_adder, reason="Storm-Guard: Safe rolü olmadan izinsiz bot soktu")
                    return
        except:
            pass

    role = member.guild.get_role(OTOROL_ID)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

# --- 7. CHAT MODERATION ---
@bot.event
async def on_message(message):
    if not message.guild or message.author.bot:
        return

    if message.author.id in CHAT_SAFE_USERS or has_safe_role(message.author):
        await bot.process_commands(message)
        return

    content = message.content.lower()
    user_id = message.author.id
    
    kelimeler = content.split()
    is_kufur = any(kufur in kelimeler or kufur in content for kufur in KUFUR_LISTESI)
    is_reklam = bool(REKLAM_REGEX.search(content))

    if is_kufur or is_reklam:
        try:
            await message.delete()
        except:
            pass

        USER_WARNINGS[user_id] = USER_WARNINGS.get(user_id, 0) + 1
        warn_count = USER_WARNINGS[user_id]

        embed = discord.Embed(title="🚫 Küfür / Reklam İhlali", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(name="Uyarı Sayısı", value=f"{warn_count}/3", inline=True)
        embed.add_field(name="Yasaklı Mesaj", value=message.content[:1000], inline=False)
        await send_log(message.guild, "chat-moderation-logs", embed)

        if warn_count >= 3:
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=10), reason="Chat Moderation: 3 İhlal")
                USER_WARNINGS[user_id] = 0
            except:
                pass
        return

    await bot.process_commands(message)

# --- 8. SLASH KOMUTLARI ---
@bot.tree.command(name="ban", description="Safe rolüne sahip yetkililerin güvenli ban atması.")
async def ban(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    MANUAL_AUTH.add(interaction.user.id)
    try:
        await uye.ban(reason=sebep)
        await interaction.followup.send(f"✅ {uye.mention} başarıyla banlandı.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Ban atılamadı: {e}", ephemeral=True)

@bot.tree.command(name="botizin", description="Sunucuya eklenecek botun ID'sine izin verir.")
async def botizin(interaction: discord.Interaction, bot_id: str):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    try:
        b_id = int(bot_id)
        ALLOWED_BOTS.add(b_id)
        await interaction.followup.send(f"✅ `{b_id}` ID'li bot için giriş izni verildi.", ephemeral=True)
    except:
        await interaction.followup.send("❌ Geçerli bir Bot ID giriniz!", ephemeral=True)

# --- 9. ÇALIŞTIRMA ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ KRİTİK HATA: DISCORD_TOKEN bulunamadı!")
    else:
        if FLASK_AVAILABLE:
            keep_alive()
        print("-> Discord botu başlatılıyor...")
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"-> BOT HATA: {e}")