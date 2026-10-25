import ssl
# Python'un bulut sunucularda Discord'a bağlanırken yaşadığı SSL sertifika doğrulama hatasını çözer
ssl._create_default_https_context = ssl._create_unverified_context

import os
import threading
from flask import Flask
import discord
from discord.ext import commands

# Flask web sunucusu (Cloud platformlarının portu açık tutması için gereklidir)
app = Flask('')

@app.route('/')
def home():
    return "Storm-Guard Bot Aktif ve Çalışıyor!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.start()

# Discord Bot Ayarları
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'-> Discord botu başarıyla giriş yaptı: {bot.user}')

if __name__ == "__main__":
    print("-> Flask web sunucusu arka planda başlatılıyor...")
    keep_alive()
    
    # Token'ı Diploi Environment kısmından güvenli bir şekilde alır
    TOKEN = os.getenv("DISCORD_TOKEN")
    
    if not TOKEN:
        print("-> HATA: DISCORD_TOKEN bulunamadı! Lütfen Diploi panelinden Environment değişkeni olarak ekleyin.")
    else:
        print("-> Discord botu başlatılıyor (bot.run çağrılıyor)...")
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"-> BOT BAŞLATIRKEN HATA OLUŞTU: {e}")