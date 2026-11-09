import os
os.environ['SSL_CERT_FILE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''

import ssl
import threading
import asyncio
import re
import urllib.request

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

# --- 1. WEB SUNUCUSU ---
if FLASK_AVAILABLE:
    app = Flask('')

    @app.route('/')
    def home():
        return "Storm-Guard Güvenlik Sistemi Aktif!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    def keep_alive():
        t = threading.Thread(target=run)
        t.start()

    threading.Thread(target=keep_alive, daemon=True).start()
else:
    def keep_alive():
        pass

# --- 2. AYARLAR VE YAPILANDIRMA ---
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

GUILD_ID = 1562558097690460321
OTOROL_ID = 1562824132796612678
SAFE_ROLE_ID = 1562922053571580046

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
    print(f'🔥 {bot.user.name} Güvenlik Sistemi Hazır!')
    try:
        guild_obj = discord.Object(id=GUILD_ID)
        bot.tree.clear_commands(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"🔗 {len(synced)} adet komut senkronize edildi.")
    except Exception as e:
        print(f"Komut senkronizasyon hatası: {e}")

async def send_log(guild, channel_name, embed):
    chan = discord.utils.get(guild.text_channels, name=channel_name)
    if chan:
        try:
            await chan.send(embed=embed)
        except Exception as e:
            print(f"Log gönderme hatası ({channel_name}): {e}")

def has_safe_role(member: discord.Member) -> bool:
    if not member:
        return False
    if member.id == member.guild.owner_id:
        return True
    safe_role = member.guild.get_role(SAFE_ROLE_ID)
    if safe_role and safe_role in member.roles:
        return True
    return False

# --- 3. SES LOGLARI ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    guild = member.guild
    embed = None
    try:
        if before.channel is not None and after.channel is None:
            embed = discord.Embed(title="🔇 Üye Ses Kanalından Ayrıldı", description=f"{member.mention} ses kanalını terk etti.", color=discord.Color.orange())
            embed.add_field(name="Ayrıldığı Kanal", value=f"🔊 {before.channel.name}", inline=True)
        elif before.channel is None and after.channel is not None:
            embed = discord.Embed(title="🔊 Üye Ses Kanalına Giriş Yaptı", description=f"{member.mention} bir ses kanalına bağlandı.", color=discord.Color.green())
            embed.add_field(name="Bağlandığı Kanal", value=f"🔊 {after.channel.name}", inline=True)
        elif before.channel != after.channel and before.channel is not None and after.channel is not None:
            embed = discord.Embed(title="🔄 Ses Kanalı Değişikliği", description=f"{member.mention} ses kanalını değiştirdi.", color=discord.Color.blue())
            embed.add_field(name="Önceki Kanal", value=f"🔊 {before.channel.name}", inline=True)
            embed.add_field(name="Yeni Kanal", value=f"🔊 {after.channel.name}", inline=True)

        if embed:
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Storm-Guard • ID: {member.id} • Authorized By Zynex")
            await send_log(guild, "voice-logs", embed)
    except Exception as e:
        print(f"Ses log hatası: {e}")

# --- 4. SAĞ TIK BAN KORUMASI ---
@bot.event
async def on_member_ban(guild, user):
    await asyncio.sleep(1.5)
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
                await guild.unban(user, reason="Storm-Guard: Haksız işlem geri alındı.")
                await guild.ban(member, reason="Storm-Guard: Safe rolü olmadan yetkisiz ban.")
                
                embed = discord.Embed(title="🚨 İHLAL: Yetkisiz Ban Engellendi!", color=discord.Color.red())
                embed.add_field(name="🛡️ Cezalandırılan Yetkili", value=member.mention, inline=False)
                embed.add_field(name="👤 Haksız Banlanan", value=user.name, inline=False)
                embed.set_footer(text="Storm-Guard • Authorized By Zynex")
                await send_log(guild, "ban-logs", embed)
                return
    except Exception as e:
        print(f"Ban koruma hatası: {e}")

# --- 5. ÜYE AYRILMA / KICK ---
@bot.event
async def on_member_remove(member):
    await asyncio.sleep(1.5)
    try:
        async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                actor = entry.user
                if actor.bot or actor.id == member.guild.owner_id:
                    return
                manager = member.guild.get_member(actor.id)
                if manager and not has_safe_role(manager):
                    await member.guild.ban(manager, reason="Storm-Guard: Yetkisiz kick.")
                    embed = discord.Embed(title="🚨 İHLAL: Yetkisiz Kick Engellendi!", color=discord.Color.red())
                    embed.add_field(name="🛡️ Yetkili", value=manager.mention, inline=False)
                    embed.set_footer(text="Storm-Guard • Authorized By Zynex")
                    await send_log(member.guild, "ban-logs", embed)
                    return
    except Exception as e:
        print(f"Kick koruma hatası: {e}")

    if member.guild.id == GUILD_ID:
        leave_embed = discord.Embed(title="📤 Üye Ayrıldı", description=f"{member.mention} (`{member.name}`) sunucudan ayrıldı.", color=discord.Color.orange())
        leave_embed.set_footer(text=f"Storm-Guard • Authorized By Zynex")
        await send_log(member.guild, "member-logs", leave_embed)

# --- 6. ROL KORUMASI ---
@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return
    await asyncio.sleep(1.2)
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
                try:
                    await after.edit(roles=before.roles, reason="Geri alındı.")
                except:
                    pass
                try:
                    await after.guild.ban(manager, reason="Yetkisiz rol değişimi.")
                except:
                    pass

                embed = discord.Embed(title="🚨 İHLAL: Yetkisiz Rol Değişimi!", color=discord.Color.red())
                embed.add_field(name="Yetkili", value=manager.mention, inline=False)
                embed.set_footer(text="Storm-Guard • Authorized By Zynex")
                await send_log(after.guild, "ban-logs", embed)
                return
    except Exception as e:
        print(f"Rol koruma hatası: {e}")

# --- 7. KANAL VE ROL SİLME ---
@bot.event
async def on_guild_channel_delete(channel):
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        member = channel.guild.get_member(user.id)
        if member and not has_safe_role(member):
            try:
                await channel.guild.ban(member, reason="İzinsiz kanal sildi.")
                embed = discord.Embed(title="🚨 ACİL: Kanal Silindi!", color=discord.Color.dark_red())
                embed.add_field(name="Silen", value=member.mention, inline=False)
                embed.add_field(name="Kanal", value=channel.name, inline=False)
                embed.set_footer(text="Storm-Guard • Authorized By Zynex")
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
                await role.guild.ban(member, reason="İzinsiz rol sildi.")
                embed = discord.Embed(title="🚨 ACİL: Rol Silindi!", color=discord.Color.dark_red())
                embed.add_field(name="Silen", value=member.mention, inline=False)
                embed.add_field(name="Rol", value=role.name, inline=False)
                embed.set_footer(text="Storm-Guard • Authorized By Zynex")
                await send_log(role.guild, "guard-log", embed)
            except:
                pass
            return

# --- 8. ÜYE GİRİŞ & ANTI-BOT ---
@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return

    if member.id in GLOBAL_BAN_LIST:
        try:
            await member.ban(reason="Global Ban")
            embed = discord.Embed(title="🌍 Global Ban Engeli!", description=f"{member.mention} sunucuya girmeye çalıştı ve engellendi.", color=discord.Color.dark_red())
            await send_log(member.guild, "global-ban", embed)
        except:
            pass
        return

    join_embed = discord.Embed(title="📥 Yeni Üye", description=f"Hoş geldin {member.mention}!", color=discord.Color.green())
    join_embed.set_footer(text="Storm-Guard • Authorized By Zynex")
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
                
                bot_embed = discord.Embed(title="🤖 İzinsiz Bot Tespit!", color=discord.Color.red())
                bot_embed.add_field(name="Bot", value=member.mention, inline=False)
                bot_embed.add_field(name="Ekleyen", value=member_adder.mention if member_adder else 'Bilinmiyor', inline=False)
                await send_log(member.guild, "anti-bot-log", bot_embed)

                if not member_adder or not has_safe_role(member_adder):
                    await member.ban(reason="Yetkisiz bot")
                    if member_adder:
                        await member.guild.ban(member_adder, reason="Yetkisiz bot eklemek.")
                    return
        except:
            pass

    role = member.guild.get_role(OTOROL_ID)
    if role:
        try:
            await member.add_roles(role)
        except:
            pass

# --- 9. CHAT MODERATION ---
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

        embed = discord.Embed(title="🚫 Küfür / Reklam Engellendi", color=discord.Color.red())
        embed.add_field(name="Kullanıcı", value=message.author.mention, inline=True)
        embed.add_field(name="Uyarı", value=f"{warn_count}/3", inline=True)
        embed.set_footer(text="Storm-Guard • Authorized By Zynex")
        await send_log(message.guild, "chat-moderation-logs", embed)

        if warn_count >= 3:
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.utils.timedelta(minutes=10), reason="3 İhlal")
                USER_WARNINGS[user_id] = 0
            except:
                pass
        return

    await bot.process_commands(message)

# --- 10. SLASH KOMUTLARI ---

@bot.tree.command(name="seskatil", description="Seçilen ses kanalına katılır.")
@app_commands.describe(kanal="Ses kanalı")
async def seskatil(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Yetkiniz yok!", ephemeral=True)
        return
    try:
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(kanal)
        else:
            await kanal.connect()
        await interaction.followup.send(f"✅ **{kanal.name}** kanalına katıldım.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)

@bot.tree.command(name="sesayril", description="Ses kanalından ayrılır.")
async def sesayril(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Yetkiniz yok!", ephemeral=True)
        return
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.followup.send("👋 Ses kanalından ayrıldım.", ephemeral=True)
    else:
        await interaction.followup.send("⚠️ Zaten bir ses kanalında değilim.", ephemeral=True)

@bot.tree.command(name="globalban", description="Kullanıcıyı global banlar.")
@app_commands.describe(user_id="Kullanıcı ID", sebep="Sebep")
async def globalban(interaction: discord.Interaction, user_id: str, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Yetkiniz yok!", ephemeral=True)
        return
    try:
        u_id = int(user_id)
        GLOBAL_BAN_LIST.add(u_id)
        user_obj = await bot.fetch_user(u_id)
        MANUAL_AUTH.add(interaction.user.id)
        await interaction.guild.ban(user_obj, reason=sebep)
        await interaction.followup.send(f"🌍 `{u_id}` global banlandı.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Güvenli ban atar.")
@app_commands.describe(uye="Üye", sebep="Sebep")
async def ban(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Yetkiniz yok!", ephemeral=True)
        return
    try:
        MANUAL_AUTH.add(interaction.user.id)
        await uye.ban(reason=sebep)
        await interaction.followup.send(f"✅ {uye.mention} banlandı.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)

@bot.tree.command(name="logkurulum", description="Log kanallarını kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def logkurulum(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name="Server Logs")
    if not category:
        category = await guild.create_category("Server Logs")

    for isim in ["guard-log", "ban-logs", "member-logs", "chat-moderation-logs", "anti-bot-log", "voice-logs", "global-ban"]:
        if not discord.utils.get(guild.text_channels, name=isim):
            await guild.create_text_channel(isim, category=category)
    await interaction.followup.send("✅ Log kanalları kuruldu!", ephemeral=True)

# --- 11. BAŞLATMA ---
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)