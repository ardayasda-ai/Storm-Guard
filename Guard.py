import ssl
import threading
import asyncio
import re
import os

# --- 0. KESİN SSL VE SERTİFİKA BYPASS ---
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

import aiohttp
_old_connector_init = aiohttp.TCPConnector.__init__
def _new_connector_init(self, *args, **kwargs):
    kwargs['ssl'] = False
    _old_connector_init(self, *args, **kwargs)
aiohttp.TCPConnector.__init__ = _new_connector_init

import discord
from discord import app_commands
from discord.ext import commands

# Flask modülü kontrolü (Eğer yüklenmemişse hata vermemesi için güvenli katman)
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
        return "Storm-Guard Safe Rolü ve Güvenlik Sistemleri Aktif!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    def keep_alive():
        t = threading.Thread(target=run)
        t.start()
else:
    def keep_alive():
        print("⚠️ Flask bulunamadı, web sunucusu başlatılamıyor.")

# --- 2. BOT AYARLARI VE KONFİGÜRASYON ---
TOKEN = os.getenv("DISCORD_TOKEN", "MTU2MzIxMjUxMjYzODI3OTg1Mg.Grojg5.3kCtYduiJuLnMSOTilpEzeUHK3I6Isoao2_yoY")
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
USER_SPAM_CACHE = {} 
MOD_STATS = {} 
MANUAL_BAN_AUTH = set()

KUFUR_LISTESI = ["amk", "aq", "orospu", "piç", "sik", "yarak", "oç", "amq", "sikik", "amina", "anan"]
REKLAM_REGEX = re.compile(r"(https?://|discord\.gg/|discord\.com/invite/)")

@bot.event
async def on_ready():
    print(f'{bot.user.name} Safe Rolü Tabanlı Güvenlik Sistemleri Aktif!')
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

# --- 3. ÜYE & İZİNSİZ BOT KORUMASI ---
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

# --- 4. SAĞ TIK BAN KORUMASI ---
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

# --- 5. KANAL VE ROL SİLME KORUMALARI ---
@bot.event
async def on_guild_channel_delete(channel):
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        member = channel.guild.get_member(user.id)
        if member and not has_safe_role(member):
            try:
                await channel.guild.ban(member, reason="Guard: Safe rolü olmadan izinsiz kanal silme!")
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
                await role.guild.ban(member, reason="Guard: Safe rolü olmadan izinsiz rol silme!")
                embed = discord.Embed(title="🚨 İzinsiz Rol Silme", description=f"{member.mention} Safe rolü olmadığı halde rolü sildiği için banlandı!", color=discord.Color.red())
                await send_log(role.guild, "guard-log", embed)
            except:
                pass
            return

# --- 6. CHAT MODERATION & KÜFÜR ENGELLEME ---
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

        embed = discord.Embed(title="🚫 Küfür / Sansür İhlali", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
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

# --- 7. SLASH KOMUTLARI ---
@bot.tree.command(name="botizin", description="Sunucuya eklenecek botun ID'sine izin verir (Safe Rolü gerekir).")
async def botizin(interaction: discord.Interaction, bot_id: str):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Bu komutu kullanmak için Safe rolüne sahip olmalısınız!", ephemeral=True)
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

@bot.tree.command(name="ban", description="Safe rolüne sahip yetkililerin ban atması.")
async def ban(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    MANUAL_BAN_AUTH.add(interaction.user.id)
    await uye.ban(reason=sebep)
    await interaction.followup.send(f"✅ {uye.mention} banlandı.", ephemeral=True)

@bot.tree.command(name="logkurulum", description="Log kanallarını kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def logkurulum(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    guild = interaction.guild
    category = await guild.create_category("Server Logs")
    kanal_isimleri = ["guard-log", "ban-logs", "member-logs", "chat-moderation-logs", "global-ban"]
    for isim in kanal_isimleri:
        try:
            await guild.create_text_channel(isim, category=category)
        except:
            pass
    await interaction.followup.send("✅ Log Kanalları Kuruldu!")

@bot.tree.command(name="logsifirla", description="Log kanallarını sıfırlar.")
@app_commands.checks.has_permissions(administrator=True)
async def logsifirla(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    guild = interaction.guild
    for category in guild.categories:
        if category.name == "Server Logs":
            for channel in category.channels:
                try: await channel.delete()
                except: pass
            try: await category.delete()
            except: pass
    await interaction.followup.send("🔄 Log sistemi sıfırlandı.")

# --- 8. ÇALIŞTIRMA ---
if __name__ == "__main__":
    if FLASK_AVAILABLE:
        keep_alive()
    print("-> Discord botu başlatılıyor (bot.run çağırılıyor)...")
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"-> BOT BAŞLATIRKEN HATA OLUŞTU: {e}")