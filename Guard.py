from flask import Flask
from threading import Thread
import discord
from discord.ext import commands

app = Flask('')


@app.route('/')
def home():
  return "Bot Aktif ve Çalışıyor!"


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# Bot ayarların
TOKEN = "MTU2MzIxMjUxMjYzODI3OTg1Mg.GxAgs2.JtkS5pn5ruOQ-dnZoH2g7txfrh2lT1swLKpJ2c"
GUILD_ID = 1562558097690460321
OTOROL_ID = 1562824132796612678
SAFE_ROLE_ID = 1562922053571580046

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


# --- KESİN ÇÖZÜM BAŞLATMA SIRASI ---
if __name__ == "__main__":
  print("-> Flask web sunucusu arka planda başlatılıyor...")
  keep_alive()

  print("-> Discord botu başlatılıyor (bot.run çağrılıyor)...")
  try:
    bot.run(TOKEN)
  except Exception as e:
    print(f"-> BOT BAŞLATıRKEN HATA OLUŞTU: {e}")