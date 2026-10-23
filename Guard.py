from flask import Flask
from threading import Thread
import discord
from discord.ext import commands

# --- RENDER KAPANMASIN DİYE WEB SUNUCUSU ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Aktif ve Çalışıyor!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -------------------------------------------

# --- SUNUCU VE LOG KANALI AYARLARI ---
TOKEN = "MTU2MzIxMjUxMjYzODI3OTg1Mg.GaHPdk.oBfVK3dglig0e0TtnAC9dhLK1hZymQVKh6SQm4"
GUILD_ID = 1562558097690460321      # Sunucunun ID'si
OTOROL_ID = 1562824132796612678     # Üye Rolü ID'si
SAFE_ROLE_ID = 1562922053571580046  # Safe Rol ID'si

# Intents ayarları (Hatalı kısım düzeltildi)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} başarıyla giriş yaptı ve koruma aktif!')

@bot.event
async def on_member_join(member):
    if member.guild.id == GUILD_ID:
        role = member.guild.get_role(OTOROL_ID)
        if role:
            await member.add_roles(role)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)