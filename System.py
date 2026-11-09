import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import asyncio
import random
import io
from flask import Flask
from threading import Thread

# -------------------------------------------------------------
# 🌐 Render 7/24 Uykuyu Önleme (Keep-Alive) ve Dinamik Port Altyapısı
# -------------------------------------------------------------
app = Flask('')

@app.route('/')
def home():
    return "StormSystem 7/24 Aktif ve Çalışıyor!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# -------------------------------------------------------------
# 🤖 Discord Bot Başlangıç ve Intent Ayarları
# -------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

class StormBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✨ Tüm Slash (/) komutları senkronize edildi!")

bot = StormBot()

# ID sayacı ve Veri yönetimi
ID_FILE = "ticket_data.json"

def load_data():
    if os.path.exists(ID_FILE):
        with open(ID_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "last_id": 0, 
        "stats": {}, 
        "welcome_channel": None, 
        "auto_role_id": None,
        "custom_voice_category": None,
        "custom_voice_channel": None,
        "temp_channels": []
    }

def save_data(data):
    with open(ID_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_next_ticket_id():
    data = load_data()
    data["last_id"] += 1
    save_data(data)
    return data["last_id"]

def add_staff_stat(staff_id: str):
    data = load_data()
    if "stats" not in data:
        data["stats"] = {}
    data["stats"][staff_id] = data["stats"].get(staff_id, 0) + 1
    save_data(data)

# -------------------------------------------------------------
# 🎉 ÇEKİLİŞ SİSTEMİ ALTYAPISI
# -------------------------------------------------------------
active_giveaways = {}

class GiveawayView(discord.ui.View):
    def __init__(self, prize: str, winners_count: int, end_time: datetime.datetime):
        super().__init__(timeout=None)
        self.prize = prize
        self.winners_count = winners_count
        self.end_time = end_time
        self.participants = set()

    @discord.ui.button(label="Katıl (0)", style=discord.ButtonStyle.success, emoji="🎉", custom_id="giveaway_join")
    async def join_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            self.participants.remove(interaction.user.id)
            button.label = f"Katıl ({len(self.participants)})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⚠️ Çekiliş katılımınız iptal edildi.", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            button.label = f"Katıl ({len(self.participants)})"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("🎉 Çekilişe başarıyla katıldınız! Bol şans.", ephemeral=True)

@bot.tree.command(name="cekilisbaşlat", description="Sunucuda yeni bir çekiliş başlatır.")
@app_commands.checks.has_permissions(administrator=True)
async def cekilis_baslat(interaction: discord.Interaction, dakikasuresi: int, kazanansayisi: int, odul: str):
    if dakikasuresi <= 0 or kazanansayisi <= 0:
        await interaction.response.send_message("❌ Süre ve kazanan sayısı 0'dan büyük olmalıdır.", ephemeral=True)
        return

    end_time = discord.utils.utcnow() + datetime.timedelta(minutes=dakikasuresi)
    timestamp = int(end_time.timestamp())

    embed = discord.Embed(
        title=f"🎉 **ÇEKİLİŞ: {odul.upper()}** 🎉",
        description=(
            f"🎁 **Ödül:** `{odul}`\n"
            f"👑 **Kazanan Sayısı:** `{kazanansayisi}`\n"
            f"⏱️ **Bitiş Zamanı:** <t:{timestamp}:R> (<t:{timestamp}:F>)\n"
            f"👤 **Düzenleyen:** {interaction.user.mention}\n\n"
            f"Katılmak için aşağıdaki **Katıl** butonuna tıklayın!"
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="discord.gg/stormpack • Stormpack Çekiliş Sistemi")

    view = GiveawayView(prize=odul, winners_count=kazanansayisi, end_time=end_time)
    await interaction.response.send_message("✅ Çekiliş başarıyla başlatıldı!", ephemeral=True)
    msg = await interaction.channel.send(embed=embed, view=view)

    active_giveaways[msg.id] = {
        "view": view,
        "message": msg,
        "prize": odul,
        "winners_count": kazanansayisi,
        "channel_id": interaction.channel_id
    }

    await asyncio.sleep(dakikasuresi * 60)

    if msg.id in active_giveaways:
        await finish_giveaway(msg.id)

async def finish_giveaway(message_id: int):
    giveaway = active_giveaways.pop(message_id, None)
    if not giveaway:
        return

    view = giveaway["view"]
    msg = giveaway["message"]
    prize = giveaway["prize"]
    winners_count = giveaway["winners_count"]
    participants = list(view.participants)

    for item in view.children:
        item.disabled = True

    if not participants:
        embed = discord.Embed(
            title=f"🎉 **ÇEKİLİŞ SONLANDI: {prize.upper()}**",
            description="❌ Yeterli katılım olmadığı için kazanan seçilemedi.",
            color=discord.Color.red()
        )
        await msg.edit(embed=embed, view=view)
        await msg.channel.send(f"⚠️ **{prize}** çekilişine kimse katılmadığı için kazanan olmadı.")
        return

    winners_ids = random.sample(participants, min(len(participants), winners_count))
    winners_mentions = [f"<@{uid}>" for uid in winners_ids]

    embed = discord.Embed(
        title=f"🎉 **ÇEKİLİŞ SONLANDI: {prize.upper()}** 🎉",
        description=(
            f"🎁 **Ödül:** `{prize}`\n"
            f"🏆 **Kazanan(lar):** {', '.join(winners_mentions)}\n"
            f"👥 **Toplam Katılım:** `{len(participants)}`"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="discord.gg/stormpack • Tebrikler!")

    await msg.edit(embed=embed, view=view)
    await msg.channel.send(f"🎉 Tebrikler {', '.join(winners_mentions)}! **{prize}** çekilişini kazandınız!")

# -------------------------------------------------------------
# 🛡️ 1. /systemlogkurulum & /logsifirla Komutları
# -------------------------------------------------------------
@bot.tree.command(name="systemlogkurulum", description="Kapsamlı sistem log kanallarını otomatik kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def system_log_kurulum(interaction: discord.Interaction):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    category = discord.utils.get(guild.categories, name="🛡️ StormSystem Loglar")
    if not category:
        category = await guild.create_category("🛡️ StormSystem Loglar", overwrites=overwrites)

    log_channels = [
        "📋-ticket-log",
        "⚙️-moderatör-işlem-log",
        "🔑-rol-yetki-log",
        "📁-kanal-düzen-log",
        "💬-mesaj-akış-log",
        "👤-üye-giriş-çıkış-log",
        "🎧-ses-sistem-log"
    ]

    created = []
    for channel_name in log_channels:
        existing = discord.utils.get(category.channels, name=channel_name)
        if not existing:
            await guild.create_text_channel(channel_name, category=category)
            created.append(channel_name)

    embed = discord.Embed(
        title="🛡️ **StormSystem Log Kurulumu**",
        description=f"✨ Sistem logları başarıyla oluşturuldu!\n\n**Eklenen Kanallar:**\n" + "\n".join([f"• `{c}`" for c in created]),
        color=discord.Color.dark_theme()
    )
    embed.set_footer(text="discord.gg/stormpack")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="logsifirla", description="Log kategorisini ve içindeki tüm kanalları tamamen siler.")
@app_commands.checks.has_permissions(administrator=True)
async def log_sifirla(interaction: discord.Interaction):
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name="🛡️ StormSystem Loglar")
    if category:
        for channel in category.channels:
            await channel.delete()
        await category.delete()
        
        embed = discord.Embed(
            title="🧹 **Log Sıfırlama İşlemi**",
            description="✨ Log kategorisi ve içindeki tüm log kanalları başarıyla temizlendi.",
            color=discord.Color.red()
        )
        embed.set_footer(text="discord.gg/stormpack")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Silinecek aktif bir log kategorisi bulunamadı.", ephemeral=True)

# -------------------------------------------------------------
# 🔊 2. /ozelodakur Komutu ve Ses Yönetimi (J2C)
# -------------------------------------------------------------
@bot.tree.command(name="ozelodakur", description="Katılınca otomatik özel oda açan ses sistemini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ozel_oda_kur(interaction: discord.Interaction):
    guild = interaction.guild
    
    category = discord.utils.get(guild.categories, name="🔊 | Özel Odalar")
    if not category:
        category = await guild.create_category("🔊 | Özel Odalar")

    create_channel = await guild.create_voice_channel("➕ | Oda Oluştur", category=category)

    data = load_data()
    data["custom_voice_category"] = category.id
    data["custom_voice_channel"] = create_channel.id
    save_data(data)

    embed = discord.Embed(
        title="🔊 **Özel Oda Sistemi Kuruldu!**",
        description=f"✨ Kullanıcılar **{create_channel.name}** kanalına bağlandığında otomatik olarak kendilerine özel oda oluşturulacak.",
        color=discord.Color.green()
    )
    embed.set_footer(text="discord.gg/stormpack")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    data = load_data()
    create_channel_id = data.get("custom_voice_channel")
    category_id = data.get("custom_voice_category")
    temp_channels = data.get("temp_channels", [])

    if after.channel and after.channel.id == create_channel_id:
        category = member.guild.get_channel(category_id)
        if category:
            temp_channel = await member.guild.create_voice_channel(
                name=f"🔊 | {member.name}-Odası",
                category=category
            )
            await member.move_to(temp_channel)
            temp_channels.append(temp_channel.id)
            data["temp_channels"] = temp_channels
            save_data(data)

    if before.channel and before.channel.id in temp_channels:
        if len(before.channel.members) == 0:
            try:
                temp_channels.remove(before.channel.id)
                data["temp_channels"] = temp_channels
                save_data(data)
                await before.channel.delete()
            except Exception as e:
                print(f"Oda silinirken hata: {e}")

# -------------------------------------------------------------
# 👑 3. /otorolkur Komutu
# -------------------------------------------------------------
@bot.tree.command(name="otorolkur", description="Sunucuya katılan yeni üyelere verilecek otomatik rolü ayarlar.")
@app_commands.checks.has_permissions(administrator=True)
async def oto_rol_kur(interaction: discord.Interaction, role: discord.Role):
    data = load_data()
    data["auto_role_id"] = role.id
    save_data(data)

    embed = discord.Embed(
        title="👑 **Oto Rol Sistemi Aktif!**",
        description=f"✨ Artık sunucuya katılan her yeni üyeye otomatik olarak **{role.mention}** rolü verilecektir.",
        color=discord.Color.green()
    )
    embed.set_footer(text="discord.gg/stormpack")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# -------------------------------------------------------------
# 👋 4. /welcomekur Komutu ve Karşılama
# -------------------------------------------------------------
@bot.tree.command(name="welcomekur", description="Giriş çıkış log ve hoş geldin kanalını otomatik kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_kur(interaction: discord.Interaction):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    channel = discord.utils.get(guild.text_channels, name="👋-giriş-çıkış")
    if not channel:
        channel = await guild.create_text_channel("👋-giriş-çıkış", overwrites=overwrites)

    data = load_data()
    data["welcome_channel"] = channel.id
    save_data(data)

    embed = discord.Embed(
        title="✨ **Hoş Geldin Sistemi Aktif!**",
        description=f"🎉 Karşılama kanalı başarıyla ayarlandı: {channel.mention}",
        color=discord.Color.green()
    )
    embed.set_footer(text="discord.gg/stormpack")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_member_join(member):
    data = load_data()
    
    role_id = data.get("auto_role_id")
    if role_id:
        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="StormSystem Oto Rol")
            except Exception as e:
                print(f"Oto rol verilemedi: {e}")

    channel_id = data.get("welcome_channel")
    if channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            embed = discord.Embed(
                title="🚀 **Stormpack Sunucusuna Hoş Geldin!**",
                description=f"Hey {member.mention}, aramıza katıldın! 🎉\n\n📌 Seninle birlikte **{member.guild.member_count}** kişi olduk.",
                color=discord.Color.dark_theme()
            )
            if member.avatar:
                embed.set_thumbnail(url=member.avatar.url)
            embed.set_footer(text="StormSystem | Otomatik Karşılama")
            await channel.send(embed=embed)

    log_chan = discord.utils.get(member.guild.text_channels, name="👤-üye-giriş-çıkış-log")
    if log_chan:
        log_emb = discord.Embed(title="📥 **Üye Sunucuya Katıldı**", color=discord.Color.green())
        log_emb.add_field(name="Üye", value=f"{member.mention} (`{member.id}`)", inline=False)
        log_emb.timestamp = discord.utils.utcnow()
        await log_chan.send(embed=log_emb)

@bot.event
async def on_member_remove(member):
    log_chan = discord.utils.get(member.guild.text_channels, name="👤-üye-giriş-çıkış-log")
    if log_chan:
        log_emb = discord.Embed(title="📤 **Üye Sunucudan Ayrıldı**", color=discord.Color.red())
        log_emb.add_field(name="Üye", value=f"{member.name} (`{member.id}`)", inline=False)
        log_emb.timestamp = discord.utils.utcnow()
        await log_chan.send(embed=log_emb)

# -------------------------------------------------------------
# 🎫 5. /ticketkurulum & Dropdown / Menülü Sistem
# -------------------------------------------------------------
class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Satın Alım & Sipariş", description="Ürün satın alma ve ödeme işlemleri.", emoji="💵", value="ticket_satin_alim"),
            discord.SelectOption(label="Ürün Teslimatı & Kurulum", description="Satın alınan ürünlerin teslimatı ve teknik kurulumu.", emoji="🎟️", value="ticket_teslimat"),
            discord.SelectOption(label="Teknik Destek & Kurulum", description="Bot kurulumu, panel erişimi ve teknik sorunlar.", emoji="🛠️", value="ticket_teknik"),
            discord.SelectOption(label="Genel Destek & Soru", description="Mağaza ve ürünlerle ilgili genel sorularınız.", emoji="🧳", value="ticket_genel"),
            discord.SelectOption(label="Seçim Sıfırla", description="Sadece seçiminizi sıfırlar.", emoji="🗑️", value="ticket_reset")
        ]
        super().__init__(placeholder="🛒 Destek almak istediğiniz konuyu seçin...", min_values=1, max_values=1, options=options, custom_id="ticket_dropdown")

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "ticket_reset":
            await interaction.response.send_message("🔄 Seçiminiz sıfırlandı.", ephemeral=True)
            return
        
        category_map = {
            "ticket_satin_alim": "Satın Alım & Sipariş",
            "ticket_teslimat": "Ürün Teslimatı & Kurulum",
            "ticket_teknik": "Teknik Destek & Kurulum",
            "ticket_genel": "Genel Destek & Soru"
        }
        cat_name = category_map.get(self.values[0], "Genel Destek")
        await create_ticket_channel(interaction, cat_name)

class TicketDropView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown())

async def create_ticket_channel(interaction: discord.Interaction, category_name: str):
    guild = interaction.guild
    member = interaction.user
    ticket_id = get_next_ticket_id()

    category = discord.utils.get(guild.categories, name="🎫 | Destek Talepleri")
    if not category:
        overwrites_cat = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        category = await guild.create_category("🎫 | Destek Talepleri", overwrites=overwrites_cat)

    storm_team = discord.utils.get(guild.roles, name="Storm Team")
    
    overwrites_channel = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    if storm_team:
        overwrites_channel[storm_team] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel_name = f"destek-{ticket_id}"
    ticket_channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites_channel)

    embed = discord.Embed(
        title=f"🎫 #{ticket_id} - {member.name} Destek Talebi",
        color=discord.Color.dark_theme()
    )
    embed.description = (
        f"👤 {member.mention} tarafından <t:{int(interaction.created_at.timestamp())}:F> tarihinde yeni bir destek talebi oluşturuldu.\n\n"
        f"🛡️ **Sorumlu Yetkili:** Sahiplenilmesi bekleniyor...\n"
        f"👤 **Ticket Açan:** {member.mention} (`{member.id}`)\n"
        f"📁 **Ticket Kategorisi:** `{category_name}`\n"
        f"⏱️ **Ortalama Cevap Süresi:** `2 - 5 Dakika`\n\n"
        f"⚠️ Lütfen sorununuzu detaylı bir şekilde yazarak yetkili ekibimizin size dönüş yapmasını bekleyin."
    )
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    embed.set_footer(text="StormPack | Destek ve Güvenlik Sistemi")

    view = TicketManagementView(member.id, ticket_id, category_name)
    await ticket_channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"✅ Destek talebiniz oluşturuldu: {ticket_channel.mention}", ephemeral=True)

class TicketManagementView(discord.ui.View):
    def __init__(self, creator_id: int, ticket_id: int, category_name: str):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.ticket_id = ticket_id
        self.category_name = category_name
        self.claimed_by = None

    @discord.ui.button(label="Yetkili - Sahiplen", style=discord.ButtonStyle.primary, emoji="👥", custom_id="ticket_claim")
    async def sahiplen(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Ticket Sorumlusu")
        if not role or (role not in interaction.user.roles and not interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Bu butonu yalnızca **Ticket Sorumlusu** kullanabilir.", ephemeral=True)
            return

        self.claimed_by = interaction.user
        add_staff_stat(str(interaction.user.id))
        
        button.disabled = True
        button.label = f"Sahiplenildi: {interaction.user.name}"

        msg = interaction.message
        if msg.embeds:
            emb = msg.embeds[0]
            emb.description = emb.description.replace("Sahiplenilmesi bekleniyor...", f"✨ {interaction.user.mention} tarafından sahiplenildi.")
            await msg.edit(embed=emb, view=self)

        await interaction.response.send_message(f"✨ Bu ticket **{interaction.user.name}** tarafından üstlenildi!", ephemeral=False)

    @discord.ui.button(label="Yetkili - Kapat", style=discord.ButtonStyle.secondary, emoji="💾", custom_id="ticket_close_staff")
    async def yetkili_kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Ticket Sorumlusu")
        if not role or (role not in interaction.user.roles and not interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Bu butonu yalnızca **Ticket Sorumlusu** kullanabilir.", ephemeral=True)
            return
        await self.close_ticket(interaction, kapatan="Yetkili")

    @discord.ui.button(label="Oyuncu - Kapat", style=discord.ButtonStyle.danger, emoji="⚙️", custom_id="ticket_close_user")
    async def oyuncu_kapat(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bu butonu sadece talebi açan oyuncu veya yetkililer kullanabilir.", ephemeral=True)
            return
        await self.close_ticket(interaction, kapatan="Oyuncu")

    @discord.ui.button(label="Yedek Al", style=discord.ButtonStyle.success, emoji="📂", custom_id="ticket_transcript")
    async def yedek_al(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = discord.utils.get(interaction.guild.roles, name="Ticket Sorumlusu")
        if not role or (role not in interaction.user.roles and not interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("❌ Ticket yedeğini yalnızca **Ticket Sorumlusu** alabilir.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        # Sohbet geçmişini toplama
        messages_text = f"--- STORM-PACK TICKET YEDEĞİ (#{self.ticket_id}) ---\n"
        async for msg in interaction.channel.history(limit=500, oldest_first=True):
            timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
            messages_text += f"[{timestamp}] {msg.author.name}: {msg.content}\n"

        file_bytes = io.BytesIO(messages_text.encode("utf-8"))
        file = discord.File(file_bytes, filename=f"ticket-{self.ticket_id}-yedek.txt")

        log_channel = discord.utils.get(interaction.guild.text_channels, name="📋-ticket-log")
        if log_channel:
            log_embed = discord.Embed(
                title=f"📂 **Ticket Yedeği Alındı (#{self.ticket_id})**",
                description=f"Alınan Yer: {interaction.channel.name}\nAçan: <@{self.creator_id}>\nYedeği Alan: {interaction.user.mention}",
                color=discord.Color.blue()
            )
            await log_channel.send(embed=log_embed, file=file)
            await interaction.followup.send("✅ Ticket yedeği başarıyla `📋-ticket-log` kanalına gönderildi.", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ `📋-ticket-log` kanalı bulunamadı, dosya gönderilemedi.", ephemeral=True)

    async def close_ticket(self, interaction: discord.Interaction, kapatan: str):
        guild = interaction.guild
        creator = guild.get_member(self.creator_id)
        creator_name = creator.name if creator else f"Bilinmeyen ({self.creator_id})"
        staff_name = self.claimed_by.name if self.claimed_by else "Sahiplenilmedi"

        log_channel = discord.utils.get(guild.text_channels, name="📋-ticket-log")
        if log_channel:
            log_embed = discord.Embed(title=f"🔒 **Destek Talebi Kapatıldı (#{self.ticket_id})**", color=discord.Color.red())
            log_embed.add_field(name="🆔 Destek ID", value=f"#{self.ticket_id}", inline=True)
            log_embed.add_field(name="📁 Kategori", value=self.category_name, inline=True)
            log_embed.add_field(name="👤 Açan Oyuncu", value=creator_name, inline=True)
            log_embed.add_field(name="👥 Sahiplenen Yetkili", value=staff_name, inline=True)
            log_embed.add_field(name="⚙️ Kapatan Taraf", value=f"{kapatan} ({interaction.user.name})", inline=True)
            log_embed.timestamp = discord.utils.utcnow()
            await log_channel.send(embed=log_embed)

        if not interaction.response.is_done():
            await interaction.response.send_message("⚠️ Destek talebi kapatılıyor...", ephemeral=True)
        else:
            await interaction.followup.send("⚠️ Destek talebi kapatılıyor...", ephemeral=True)
            
        await interaction.channel.delete()

@bot.tree.command(name="ticketkurulum", description="Destek panelini kurar.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_kurulum(interaction: discord.Interaction, banner_url: str):
    embed = discord.Embed(
        title="🛒 **StormPack # Destek & Bilet Sistemi**",
        description=(
            "Nos Store ürünleri, siparişleriniz, ödemeleriniz veya teknik destek için aşağıdan ilgili kategoriyi seçerek bilet oluşturabilirsiniz.\n\n"
            "💡 **Hızlı Destek:** Bilet açtıktan sonra sipariş numaranızı veya satın aldığınız ürün adını iletmeniz süreci hızlandıracaktır.\n"
            "⏱️ Müşteri temsilcilerimiz en kısa sürede talebinizi yanıtlayacaktır.\n\n"
            "ℹ️ **Müşteri Hizmetleri Kuralları:**\n"
            "• Satın aldığınız ürünle ilgili fatura/sipariş kodunuzu hazırlayınız.\n"
            "• Kurulum taleplerinde sunucu bilgilerinizi hazır bulundurunuz.\n"
            "• Temsilcilerimiz mesai saatleri içerisinde en kısa sürede yanıt verir."
        ),
        color=discord.Color.dark_theme()
    )
    embed.set_image(url=banner_url)
    embed.set_footer(text="Powered By StormPack - Müşteri Hizmetleri")

    view = TicketDropView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ StormPack destek paneli başarıyla kuruldu.", ephemeral=True)

@bot.tree.command(name="ticketpanelsifirla", description="Ticket kategorisini ve tüm aktif biletleri temizler.")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel_sifirla(interaction: discord.Interaction):
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name="🎫 | Destek Talepleri")
    if category:
        for channel in category.channels:
            await channel.delete()
        await category.delete()
        
        embed = discord.Embed(
            title="🧹 **Ticket Sıfırlama İşlemi**",
            description="✨ Ticket kategorisi ve içindeki tüm aktif bilet kanalları başarıyla temizlendi.",
            color=discord.Color.red()
        )
        embed.set_footer(text="discord.gg/stormpack")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ Silinecek aktif bir ticket kategorisi bulunamadı.", ephemeral=True)

# -------------------------------------------------------------
# 📊 6. /ticketsiralama & Moderasyon & Diğer Komutlar
# -------------------------------------------------------------
@bot.tree.command(name="ticketsiralama", description="En çok tickete bakan yetkilileri listeler.")
async def ticket_siralama(interaction: discord.Interaction):
    data = load_data()
    stats = data.get("stats", {})
    if not stats:
        await interaction.response.send_message("📊 Henüz kayıtlı ticket verisi yok.", ephemeral=True)
        return

    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)
    description = ""
    for index, (staff_id, count) in enumerate(sorted_stats, start=1):
        member = interaction.guild.get_member(int(staff_id))
        name = member.name if member else f"Yetkili ({staff_id})"
        description += f"**{index}.** • **{name}** — ` {count} Destek `\n"

    embed = discord.Embed(title="🏆 **Stormpack | Yetkili Sıralaması**", description=description, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="Kullanıcının avatarını gösterir.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"🖼️ {target.name} adlı kullanıcının avatarı:", color=discord.Color.dark_theme())
    embed.set_image(url=target.display_avatar.url)
    embed.set_footer(text="discord.gg/stormpack")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rolver", description="Üyeye rol verir.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rol_ver(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ **{member.name}** kullanıcısına **{role.name}** rolü verildi.")

@bot.tree.command(name="rolal", description="Üyeden rol alır.")
@app_commands.checks.has_permissions(manage_roles=True)
async def rol_al(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ **{member.name}** kullanıcısından **{role.name}** rolü alındı.")

@bot.tree.command(name="mute", description="Üyeyi belirli süreyle susturur.")
@app_commands.checks.has_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Belirtilmedi"):
    duration = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"🔇 **{member.name}** {minutes} dakika susturuldu.")

@bot.tree.command(name="unmute", description="Susturmayı kaldırır.")
@app_commands.checks.has_permissions(moderate_members=True)
async def unmute(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔊 **{member.name}** kullanıcısının susturması kaldırıldı.")

@bot.tree.command(name="systemseskatil", description="Botu ses kanalına sokar.")
@app_commands.checks.has_permissions(administrator=True)
async def system_ses_katil(interaction: discord.Interaction, channel: discord.VoiceChannel):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()
    await interaction.response.send_message(f"🎧 **{channel.name}** kanalına katınıldı.", ephemeral=True)

@bot.tree.command(name="systemsesayril", description="Botu ses kanalından çıkarır.")
@app_commands.checks.has_permissions(administrator=True)
async def system_ses_ayril(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🎧 Ses kanalından ayrıldı.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"{bot.user} olarak giriş yapıldı. StormSystem 7/24 aktif!")

# -------------------------------------------------------------
# 🚀 Bot Çalıştırma ve Keep-Alive Başlatıcı
# -------------------------------------------------------------
if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("DISCORD_TOKEN"))