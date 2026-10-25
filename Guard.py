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

# aiohttp çakışmasını önleyen temiz TCPConnector yaması
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
        return "Storm-Guard Güvenlik Sistemleri Aktif!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    def keep_alive():
        t = threading.Thread(target=run)
        t.start()
else:
    def keep_alive():
        print("⚠️ Flask bulunamadı, web sunucusu başlatılamıyor.")

# --- 2. BOT AYARLARI VE KONFİGÜRASYON ---
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

GUILD_ID = 1562558097690460321
OTOROL_ID = 1562824132796612678
SAFE_ROLE_ID = 1562922053571580046  # 👉 Sunucundaki Safe Rolünün ID'si

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True
intents.moderation = True
intents.bans = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Hafıza Veri Yapıları
ALLOWED_BOTS = set()
GLOBAL_BAN_LIST = set()
CHAT_SAFE_USERS = set()
USER_WARNINGS = {} 
MANUAL_BAN_AUTH = set()

KUFUR_LISTESI = ["amk", "aq", "orospu", "piç", "sik", "yarak", "oç", "amq", "sikik", "amina", "anan"]
REKLAM_REGEX = re.compile(r"(https?://|discord\.gg/|discord\.com/invite/)")

@bot.event
async def on_ready():
    print(f'{bot.user.name} Güvenlik ve Log Sistemleri Aktif!')
    try:
        synced = await bot.tree.sync()
        print(f"🔗 {len(synced)} adet Slash (/) komutu senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

# YARDIMCI: Log Gönderici
async def send_log(guild, channel_name, embed):
    chan = discord.utils.get(guild.text_channels, name=channel_name)
    if chan:
        try:
            await chan.send(embed=embed)
        except:
            pass

# HELPER: Safe Rolü Kontrolü
def has_safe_role(member: discord.Member) -> bool:
    if not member:
        return False
    if member.id == member.guild.owner_id:
        return True
    safe_role = member.guild.get_role(SAFE_ROLE_ID)
    if safe_role and safe_role in member.roles:
        return True
    return False

# --- 3. ÜYE GİRİŞ / ÇIKIŞ & ANTI-BOT KORUMASI ---
@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return

    # Global Ban Kontrolü
    if member.id in GLOBAL_BAN_LIST:
        try:
            await member.ban(reason="Storm-Guard: Global Ban")
            embed = discord.Embed(title="🌍 Global Ban Uygulandı", description=f"{member.mention} global ban listesinde olduğu için sunucudan yasaklandı.", color=discord.Color.dark_red())
            await send_log(member.guild, "global-ban", embed)
        except:
            pass
        return

    # Üye Giriş Logu (member-logs)
    join_embed = discord.Embed(
        title="📥 Üye Sunucuya Katıldı",
        description=f"{member.mention} ({member.name}) sunucuya giriş yaptı.",
        color=discord.Color.green()
    )
    join_embed.add_field(name="Hesap Oluşturma Tarihi", value=member.created_at.strftime("%d/%m/%Y %H:%M"), inline=False)
    join_embed.set_thumbnail(url=member.display_avatar.url)
    join_embed.set_footer(text=f"Kullanıcı ID: {member.id}")
    await send_log(member.guild, "member-logs", join_embed)

    # İzinsiz Bot Koruması & Anti-Bot Log
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
                
                # Anti-bot log kanalına raporla
                bot_embed = discord.Embed(
                    title="🤖 İzinsiz Bot Tespit Edildi!",
                    description=f"**Bot:** {member.mention}\n**Ekleyen Yetkili:** {member_adder.mention if member_adder else 'Bilinmiyor'}",
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

    # Otorol verme
    role = member.guild.get_role(OTOROL_ID)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

@bot.event
async def on_member_remove(member):
    if member.guild.id != GUILD_ID:
        return

    # Üye Çıkış Logu (member-logs)
    leave_embed = discord.Embed(
        title="📤 Üye Sunucudan Ayrıldı",
        description=f"{member.mention} ({member.name}) sunucudan ayrıldı.",
        color=discord.Color.orange()
    )
    leave_embed.set_thumbnail(url=member.display_avatar.url)
    leave_embed.set_footer(text=f"Kullanıcı ID: {member.id}")
    await send_log(member.guild, "member-logs", leave_embed)

# --- 4. CHAT MODERATION & KÜFÜR ENGELLEME (chat-moderation-logs) ---
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
            await message.delete() # Mesajı siler
        except:
            pass

        USER_WARNINGS[user_id] = USER_WARNINGS.get(user_id, 0) + 1
        warn_count = USER_WARNINGS[user_id]

        # chat-moderation-logs kanalına log düşer
        embed = discord.Embed(title="🚫 Küfür / Reklam İhlali", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
        embed.add_field(name="Kanal", value=message.channel.mention, inline=True)
        embed.add_field(name="Uyarı Sayısı", value=f"{warn_count}/3", inline=True)
        embed.add_field(name="Yasaklı Mesaj", value=message.content[:1000], inline=False)
        embed.set_footer(text=f"Kullanıcı ID: {user_id}")
        await send_log(message.guild, "chat-moderation-logs", embed)

        if warn_count >= 3:
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=10), reason="Chat Moderation: 3 İhlal")
                USER_WARNINGS[user_id] = 0
            except:
                pass
        return

    await bot.process_commands(message)

# --- 5. DİĞER KORUMALAR VE SLASH KOMUTLARI ---
@bot.event
async def on_member_ban(guild, user):
    await asyncio.sleep(1.2)
    try:
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
            actor = entry.user
            if actor.bot or actor.id == guild.owner_id:
                return
            member = guild.get_member(actor.id)
            if not member:
                return
            if member.id in MANUAL_BAN_AUTH:
                MANUAL_BAN_AUTH.remove(member.id)
                return
            if not has_safe_role(member):
                await guild.unban(user, reason="Guard: Safe rolü olmadan sağ tık ban kaldırıldı")
                await guild.ban(member, reason="Guard: Safe rolü olmadan sağ tık ban denemesi!")
                return
    except:
        pass

@bot.tree.command(name="botizin", description="Sunucuya eklenecek botun ID'sine izin verir (Safe Rolü gerekir).")
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

@bot.tree.command(name="globalban", description="Kullanıcıyı global banlar.")
async def globalban(interaction: discord.Interaction, user_id: str, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    try:
        u_id = int(user_id)
        GLOBAL_BAN_LIST.add(u_id)
        user_obj = await bot.fetch_user(u_id)
        MANUAL_BAN_AUTH.add(interaction.user.id)
        await interaction.guild.ban(user_obj, reason=sebep)
        await interaction.followup.send(f"🌍 `{u_id}` global banlandı.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)

# --- 6. ÇALIŞTIRMA ---
if __name__ == "__main__":
    if not TOKEN:
        print("❌ KRİTİK HATA: DISCORD_TOKEN bulunamadı!")
    else:
        if FLASK_AVAILABLE:
            keep_alive()
        print("-> Discord botu başlatılıyor (bot.run çağırılıyor)...")
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"-> BOT BAŞLATIRKEN HATA OLUŞTU: {e}")