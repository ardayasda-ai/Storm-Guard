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

# --- 1. WEB SUNUCUSU VE OTOMATİK UYANIK TUTMA (SELF-PING) ---
if FLASK_AVAILABLE:
    app = Flask('')

    @app.route('/')
    def home():
        return "Guard Kesintisiz Güvenlik Sistemleri Aktif!"

    def run():
        app.run(host='0.0.0.0', port=8080)

    def keep_alive():
        t = threading.Thread(target=run)
        t.start()

    # Render adresini buraya otomatik algılatıyoruz veya kendi URL'ni yazabilirsin
    # Botun kendi kendine istek atarak uykudan kaçmasını sağlayan döngü:
    def self_ping():
        import time
        # Render app adını otomatik alamazsa diye kendi render linkini tırnak içine yazabilirsin:
        # Örn: url = "https://storm-guard.onrender.com"
        app_name = os.getenv("RENDER_EXTERNAL_URL", "http://127.0.0.1:8080")
        while True:
            time.sleep(300) # Her 5 dakikada bir kendine istek atar
            try:
                urllib.request.urlopen(app_name)
            except:
                pass

    threading.Thread(target=self_ping, daemon=True).start()
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
    print(f'{bot.user.name} Kesintisiz Koruma ve Komut Senkronizasyonu Aktif!')
    try:
        guild_obj = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"🔗 {len(synced)} adet Slash (/) komutu sunucuya özel senkronize edildi.")
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

# --- 3. SES KANAL LOGLARI ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    guild = member.guild
    embed = None

    try:
        if before.channel is not None and after.channel is None:
            embed = discord.Embed(title="🔇 Ses Kanalından Ayrılış", description=f"{member.mention} ses kanalından ayrıldı.", color=discord.Color.orange())
            embed.add_field(name="Ayrıldığı Kanal", value=before.channel.name, inline=True)
        elif before.channel is None and after.channel is not None:
            embed = discord.Embed(title="🔊 Ses Kanalına Giriş", description=f"{member.mention} ses kanalına giriş yaptı.", color=discord.Color.green())
            embed.add_field(name="Kanal", value=after.channel.name, inline=True)
        elif before.channel != after.channel and before.channel is not None and after.channel is not None:
            embed = discord.Embed(title="🔄 Ses Kanalı Değişikliği", description=f"{member.mention} ses kanalını değiştirdi.", color=discord.Color.blue())
            embed.add_field(name="Eski Kanal", value=before.channel.name, inline=True)
            embed.add_field(name="Yeni Kanal", value=after.channel.name, inline=True)

        if embed:
            embed.set_footer(text=f"Kullanıcı ID: {member.id}")
            await send_log(guild, "voice-logs", embed)
    except Exception as e:
        print(f"Ses log hatası: {e}")

# --- 4. SAĞ TIK BAN KORUMASI ---
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
                sebep_metni = "Safe Rolü Olmadan Sağ Tık Ban Atmak"
                await guild.unban(user, reason=f"Storm-Guard: Yetkisiz işlem geri alındı.")
                await guild.ban(member, reason=f"Storm-Guard: {sebep_metni}")
                
                embed = discord.Embed(title="🚨 İzinsiz Sağ Tık Ban Engellendi!", color=discord.Color.red())
                embed.add_field(name="Yetkisiz Yetkili", value=member.mention, inline=False)
                embed.add_field(name="Haksız Banlanan", value=user.name, inline=False)
                embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                embed.set_footer(text="İşlem geri alındı ve yetkisiz kişi cezalandırıldı.")
                
                await send_log(guild, "ban-logs", embed)
                return
    except Exception as e:
        print(f"Ban koruma hatası: {e}")

# --- 5. SAĞ TIK KICK KORUMASI ---
@bot.event
async def on_member_remove(member):
    await asyncio.sleep(1.2)
    try:
        async for entry in member.guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            if entry.target.id == member.id:
                actor = entry.user
                if actor.bot or actor.id == member.guild.owner_id:
                    return
                manager = member.guild.get_member(actor.id)
                if manager and not has_safe_role(manager):
                    sebep_metni = "Safe Rolü Olmadan Sağ Tık Üye Atmak (Kick)"
                    await member.guild.ban(manager, reason=f"Storm-Guard: {sebep_metni}")
                    
                    embed = discord.Embed(title="🚨 İzinsiz Sağ Tık Kick Engellendi!", color=discord.Color.red())
                    embed.add_field(name="Yetkisiz Yetkili", value=manager.mention, inline=False)
                    embed.add_field(name="Atılan Üye", value=member.name, inline=False)
                    embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                    
                    await send_log(member.guild, "ban-logs", embed)
                    return
    except Exception as e:
        print(f"Kick koruma hatası: {e}")

    if member.guild.id == GUILD_ID:
        leave_embed = discord.Embed(title="📤 Üye Sunucudan Ayrıldı", description=f"{member.mention} ({member.name}) sunucudan ayrıldı.", color=discord.Color.orange())
        leave_embed.set_thumbnail(url=member.display_avatar.url)
        await send_log(member.guild, "member-logs", leave_embed)

# --- 6. SAĞ TIK ROL VERME / ALMA KORUMASI ---
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
                added_roles = [r for r in after.roles if r not in before.roles]
                removed_roles = [r for r in before.roles if r not in after.roles]
                
                if added_roles:
                    sebep_metni = "Safe Rolü Olmadan Sağ Tık Rol Vermek"
                elif removed_roles:
                    sebep_metni = "Safe Rolü Olmadan Sağ Tık Rol Almak"
                else:
                    sebep_metni = "Safe Rolü Olmadan Sağ Tık Rol Değiştirmek"

                try:
                    await after.edit(roles=before.roles, reason="Storm-Guard: Yetkisiz rol değişimi geri alındı.")
                except:
                    pass

                try:
                    await after.guild.ban(manager, reason=f"Storm-Guard: {sebep_metni}")
                except:
                    pass

                embed = discord.Embed(title="🚨 İzinsiz Rol İşlemi Engellendi!", color=discord.Color.red())
                embed.add_field(name="Yetkisiz Yetkili", value=manager.mention, inline=False)
                embed.add_field(name="Hedef Üye", value=after.mention, inline=False)
                embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                embed.set_footer(text="Rol değişimi geri alındı ve yetkisiz kişi banlandı.")
                
                await send_log(after.guild, "ban-logs", embed)
                return
    except Exception as e:
        print(f"Rol koruma hatası: {e}")

# --- 7. KANAL VE ROL SİLME KORUMASI ---
@bot.event
async def on_guild_channel_delete(channel):
    await asyncio.sleep(1)
    async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        member = channel.guild.get_member(user.id)
        if member and not has_safe_role(member):
            sebep_metni = "Safe Rolü Olmadan İzinsiz Kanal Silmek"
            try:
                await channel.guild.ban(member, reason=f"Storm-Guard: {sebep_metni}")
                embed = discord.Embed(title="🚨 İzinsiz Kanal Silme Engellendi", color=discord.Color.red())
                embed.add_field(name="Yetkisiz Yetkili", value=member.mention, inline=False)
                embed.add_field(name="Silinen Kanal", value=channel.name, inline=False)
                embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                
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
            sebep_metni = "Safe Rolü Olmadan İzinsiz Rol Silmek"
            try:
                await role.guild.ban(member, reason=f"Storm-Guard: {sebep_metni}")
                embed = discord.Embed(title="🚨 İzinsiz Rol Silme Engellendi", color=discord.Color.red())
                embed.add_field(name="Yetkisiz Yetkili", value=member.mention, inline=False)
                embed.add_field(name="Silinen Rol", value=role.name, inline=False)
                embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                
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
            await member.ban(reason="Storm-Guard: Global Ban (Kalıcı Yasaklı)")
            embed = discord.Embed(title="🌍 Global Ban Tetiklendi!", description=f"Global ban listesindeki {member.mention} ({member.name}) sunucuya girmeye çalıştı ve anında tekrar yasaklandı.", color=discord.Color.dark_red())
            embed.set_footer(text=f"Kullanıcı ID: {member.id}")
            await send_log(member.guild, "global-ban", embed)
        except:
            pass
        return

    join_embed = discord.Embed(title="📥 Üye Sunucuya Katıldı", description=f"{member.mention} ({member.name}) sunucuya giriş yaptı.", color=discord.Color.green())
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
                
                sebep_metni = "Safe Rolü Olmadan İzinsiz Bot Eklemek"
                bot_embed = discord.Embed(title="🤖 İzinsiz Bot Tespit Edildi!", color=discord.Color.red())
                bot_embed.add_field(name="Eklenen Bot", value=member.mention, inline=False)
                bot_embed.add_field(name="Ekleyen Yetkili", value=member_adder.mention if member_adder else 'Bilinmiyor', inline=False)
                bot_embed.add_field(name="Ban Sebebi", value=f"`{sebep_metni}`", inline=False)
                
                await send_log(member.guild, "anti-bot-log", bot_embed)

                if not member_adder or not has_safe_role(member_adder):
                    await member.ban(reason="Storm-Guard: Yetkisiz bot")
                    if member_adder:
                        await member.guild.ban(member_adder, reason=f"Storm-Guard: {sebep_metni}")
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

# --- 10. SLASH KOMUTLARI ---

@bot.tree.command(name="seskatil", description="Seçilen ses kanalına sağırlaştırılmış ve susturulmuş şekilde katılır.")
@app_commands.describe(kanal="Bağlanılacak ses kanalını seçin")
async def seskatil(interaction: discord.Interaction, kanal: discord.VoiceChannel):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Bu komutu kullanmak için Safe rolüne sahip olmalısınız!", ephemeral=True)
        return
    
    try:
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(kanal)
        else:
            await kanal.connect()
            
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.guild.change_voice_state(channel=kanal, self_mute=True, self_deaf=True)
            
        await interaction.followup.send(f"✅ Başarıyla **{kanal.name}** ses kanalına katıldım (Susturulmuş ve Sağırlaştırılmış).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Ses kanalına bağlanırken hata oluştu: {e}", ephemeral=True)

@bot.tree.command(name="globalban", description="Kullanıcıyı global banlar (Yan hesaplardan bile giremez).")
@app_commands.describe(user_id="Banlanacak kullanıcının ID'si", sebep="Global ban sebebi")
async def globalban(interaction: discord.Interaction, user_id: str, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Bu komutu kullanmak için Safe rolüne sahip olmalısınız!", ephemeral=True)
        return
    try:
        u_id = int(user_id)
        GLOBAL_BAN_LIST.add(u_id)
        user_obj = await bot.fetch_user(u_id)
        
        MANUAL_AUTH.add(interaction.user.id)
        await interaction.guild.ban(user_obj, reason=f"Global Ban: {sebep}")
        
        await interaction.followup.send(f"🌍 `{u_id}` ({user_obj.name}) başarıyla global banlandı!", ephemeral=True)
        
        embed = discord.Embed(title="🌍 Yeni Global Ban Atıldı!", color=discord.Color.dark_red())
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        embed.add_field(name="Yasaklanan Kullanıcı", value=f"{user_obj.name} (`{u_id}`)", inline=False)
        embed.add_field(name="Sebep", value=f"`{sebep}`", inline=False)
        await send_log(interaction.guild, "global-ban", embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Hata oluştu: {e}", ephemeral=True)

@bot.tree.command(name="unglobalban", description="Kullanıcının global banını kaldırır.")
@app_commands.describe(user_id="Global banı kaldırılacak kullanıcının ID'si")
async def unglobalban(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    try:
        u_id = int(user_id)
        if u_id in GLOBAL_BAN_LIST:
            GLOBAL_BAN_LIST.remove(u_id)
            user_obj = await bot.fetch_user(u_id)
            
            await interaction.followup.send(f"✅ `{u_id}` kullanıcısının global banı kaldırıldı.", ephemeral=True)
            
            embed = discord.Embed(title="🔓 Global Ban Kaldırıldı", color=discord.Color.green())
            embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
            embed.add_field(name="Kullanıcı", value=f"{user_obj.name} (`{u_id}`)", inline=False)
            await send_log(interaction.guild, "global-ban", embed)
        else:
            await interaction.followup.send("❌ Bu kullanıcı global ban listesinde bulunmuyor.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Hata: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Normal banı kaldırır.")
@app_commands.describe(user_id="Banı açılacak kullanıcının ID'si")
async def unban(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    try:
        u_id = int(user_id)
        user_obj = await bot.fetch_user(u_id)
        await interaction.guild.unban(user_obj, reason=f"Yetkili: {interaction.user.name} tarafından açıldı.")
        
        await interaction.followup.send(f"✅ `{u_id}` kullanıcısının banı kaldırıldı.", ephemeral=True)
        
        embed = discord.Embed(title="🔓 Üye Banı Kaldırıldı", color=discord.Color.green())
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        embed.add_field(name="Banı Açılan", value=f"{user_obj.name} (`{u_id}`)", inline=False)
        await send_log(interaction.guild, "ban-logs", embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Ban kaldırılırken hata oluştu: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Safe rolüne sahip yetkililerin güvenli ban atması.")
@app_commands.describe(uye="Banlanacak üye", sebep="Ban sebebi")
async def ban(interaction: discord.Interaction, uye: discord.Member, sebep: str = "Belirtilmedi"):
    await interaction.response.defer(ephemeral=True)
    if not has_safe_role(interaction.user):
        await interaction.followup.send("❌ Safe rolünüz yok!", ephemeral=True)
        return
    
    try:
        MANUAL_AUTH.add(interaction.user.id)
        await uye.ban(reason=sebep)
        await interaction.followup.send(f"✅ {uye.mention} başarıyla banlandı.", ephemeral=True)
        
        embed = discord.Embed(title="🔨 Güvenli Ban İşlemi", color=discord.Color.red())
        embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
        embed.add_field(name="Banlanan Üye", value=f"{uye.name} (`{uye.id}`)", inline=False)
        embed.add_field(name="Sebep", value=f"`{sebep}`", inline=False)
        await send_log(interaction.guild, "ban-logs", embed)
    except Exception as e:
        await interaction.followup.send(f"❌ Ban atılamadı: {e}", ephemeral=True)

@bot.tree.command(name="botizin", description="Sunucuya eklenecek botun ID'sine izin verir.")
@app_commands.describe(bot_id="İzin verilecek botun ID'si")
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

@bot.tree.command(name="logkurulum", description="Tüm güvenlik ve log kanallarını otomatik kurar (Yönetici gerekir).")
@app_commands.checks.has_permissions(administrator=True)
async def logkurulum(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    guild = interaction.guild
    
    category = discord.utils.get(guild.categories, name="Server Logs")
    if not category:
        category = await guild.create_category("Server Logs")

    kanal_isimleri = ["guard-log", "ban-logs", "member-logs", "chat-moderation-logs", "anti-bot-log", "voice-logs", "global-ban"]
    
    kurulanlar = 0
    for isim in kanal_isimleri:
        existing = discord.utils.get(discord.utils.get(guild.categories, name="Server Logs").text_channels, name=isim) if category else None
        # Basitleştirilmiş kontrol:
        chan_check = discord.utils.get(guild.text_channels, name=isim)
        if not chan_check:
            try:
                await guild.create_text_channel(isim, category=category)
                kurulanlar += 1
            except:
                pass
                
    await interaction.followup.send(f"✅ Log sistemi başarıyla kuruldu! ({kurulanlar} yeni kanal oluşturuldu.)", ephemeral=True)

@bot.tree.command(name="logsifirla", description="Server Logs kategorisini ve içindeki tüm kanalları siler (Yönetici gerekir).")
@app_commands.checks.has_permissions(administrator=True)
async def logsifirla(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True, ephemeral=True)
    guild = interaction.guild
    silinen_kanal = 0
    
    for category in guild.categories:
        if category.name == "Server Logs":
            for channel in category.channels:
                try: 
                    await channel.delete()
                    silinen_kanal += 1
                except: 
                    pass
            try: 
                await category.delete()
            except: 
                pass
                
    await interaction.followup.send(f"🔄 Log sistemi sıfırlandı. Toplam {silinen_kanal} log kanalı silindi.", ephemeral=True)

# --- 11. ÇALIŞTIRMA ---
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