import discord
from discord.ext import commands
from discord import app_commands, ui, Interaction
import json
import os
from flask import Flask
import threading
import requests
import time
import traceback
from datetime import timedelta

# ---------- Discord Bot ----------
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------- JSON 儲存檔 ----------
WHITELIST_FILE = "whitelist.json"

def load_whitelist():
    if os.path.exists(WHITELIST_FILE):
        try:
            with open(WHITELIST_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 將 keys 轉成 int（Discord ID）
                return set(int(uid) for uid in data)
        except Exception as e:
            print(f"❗ 讀取 {WHITELIST_FILE} 發生錯誤，已備份並回退空集合: {e}")
            try:
                os.rename(WHITELIST_FILE, WHITELIST_FILE + ".bak")
                print(f"備份檔案為 {WHITELIST_FILE}.bak")
            except Exception as e2:
                print(f"備份失敗：{e2}")
            return set()
    else:
        return set()

def save_whitelist():
    try:
        with open(WHITELIST_FILE, "w", encoding="utf-8") as f:
            json.dump(list(WHITELIST), f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ 儲存 {WHITELIST_FILE} 發生錯誤：{e}")

WHITELIST = load_whitelist()

# ---------- 防炸功能 ----------
async def punish(message, member, minutes=0, hours=0, reason=""):
    try:
        await message.delete()
    except discord.Forbidden:
        print(f"⚠️ 無法刪除 {member} 的訊息（權限不足）")
    duration = timedelta(minutes=minutes, hours=hours)
    try:
        await member.timeout_for(duration, reason=reason)
        print(f"🚫 已禁言 {member} {duration} - 原因: {reason}")
    except discord.Forbidden:
        print(f"❌ 權限不足，無法禁言 {member}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    member = message.author
    if member.id in WHITELIST:
        return
    content = message.content or ""
    try:
        if len(content) > 100:
            await punish(message, member, minutes=10, reason="訊息超過100字")
        elif "@everyone" in content and "http" in content:
            await punish(message, member, hours=24, reason="@everyone + 連結")
        elif "@everyone" in content:
            await punish(message, member, hours=12, reason="@everyone")
    except Exception:
        traceback.print_exc()
    finally:
        await bot.process_commands(message)

# ---------- 斜線指令管理白名單 ----------
@bot.event
async def on_ready():
    print(f"✅ {bot.user} 已上線")
    try:
        synced = await bot.tree.sync()
        print(f"🌐 已同步 {len(synced)} 個斜線指令")
    except Exception as e:
        print(f"❌ 同步斜線指令失敗: {e}")

@bot.tree.command(name="whitelist_add", description="將使用者加入白名單")
@app_commands.describe(member="要加入白名單的使用者")
async def whitelist_add(interaction: Interaction, member: discord.Member):
    if member.id in WHITELIST:
        await interaction.response.send_message(f"{member.mention} 已經在白名單內", ephemeral=True)
    else:
        WHITELIST.add(member.id)
        save_whitelist()
        await interaction.response.send_message(f"{member.mention} 已加入白名單", ephemeral=True)

@bot.tree.command(name="whitelist_remove", description="將使用者從白名單移除")
@app_commands.describe(member="要移除白名單的使用者")
async def whitelist_remove(interaction: Interaction, member: discord.Member):
    if member.id not in WHITELIST:
        await interaction.response.send_message(f"{member.mention} 不在白名單內", ephemeral=True)
    else:
        WHITELIST.remove(member.id)
        save_whitelist()
        await interaction.response.send_message(f"{member.mention} 已從白名單移除", ephemeral=True)

# ---------- Flask Web 伺服器 ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, threaded=True)

threading.Thread(target=run_web, daemon=True).start()

# ---------- 自動 ping 自己（可選） ----------
def ping_self():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        print("⚠️ 未設定 RENDER_EXTERNAL_URL，ping_self 不啟動")
        return
    while True:
        try:
            r = requests.get(url, timeout=10)
            print(f"🟢 Ping {url} -> {r.status_code}")
        except Exception as e:
            print(f"🔴 Ping 失敗: {e}")
        time.sleep(300)

if os.environ.get("RENDER_EXTERNAL_URL"):
    threading.Thread(target=ping_self, daemon=True).start()

# ---------- 啟動 Bot ----------
TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()
if not TOKEN:
    print("❌ 未設定 DISCORD_TOKEN 環境變數！")
    raise SystemExit(1)

try:
    bot.run(TOKEN)
except Exception:
    traceback.print_exc()
