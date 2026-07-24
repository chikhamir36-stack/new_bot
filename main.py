import asyncio
import re
import os
import sys
import discord
from datetime import timedelta
from discord.ext import commands
from flask import Flask
from threading import Thread

# ==========================
# FLASK KEEP-ALIVE
# ==========================
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is alive and running!"

def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    print(f"🌐 Web server running on port {os.environ.get('PORT', 8080)}")

# ==========================
# BOT SETUP
# ==========================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# SETTINGS
# ==========================
BAD_WORDS = ["rab", "omik", "o5tek"]
LOG_CHANNEL_NAME = "logs"
warnings = {}
last_voice_channel = {}
manual_leave = set()

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?(discord\.gg|discord\.com/invite|discord\.app/invite)/\S+",
    re.I
)

# ==========================
# READY
# ==========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Bot is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guilds")

# ==========================
# HELLO COMMAND
# ==========================
@bot.command()
async def hello(ctx):
    await ctx.send(f'👋 Hello {ctx.author.mention}!')

# ==========================
# WRITE COMMAND
# ==========================
@bot.command()
@commands.has_permissions(administrator=True)
async def write(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# ==========================
# VOICE COMMANDS
# ==========================
@bot.command()
@commands.has_permissions(administrator=True)
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send("❌ Join a voice channel first.")
    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    last_voice_channel[ctx.guild.id] = channel
    await ctx.send(f"✅ Joined **{channel.name}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def leave(ctx):
    if ctx.voice_client:
        manual_leave.add(ctx.guild.id)
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left voice channel.")

# ==========================
# VOICE STATE UPDATE
# ==========================
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return
    guild = member.guild
    if after.channel:
        last_voice_channel[guild.id] = after.channel
        return
    if guild.id in manual_leave:
        manual_leave.remove(guild.id)
        return
    if before.channel and guild.id in last_voice_channel:
        await asyncio.sleep(2)
        try:
            if guild.voice_client is None:
                await last_voice_channel[guild.id].connect()
                print("🔄 Reconnected.")
        except Exception as e:
            print(f"❌ Reconnect error: {e}")

# ==========================
# WARNINGS
# ==========================
@bot.command()
@commands.has_permissions(administrator=True)
async def reset_warnings(ctx, member: discord.Member):
    warnings[member.id] = 0
    await ctx.send("✅ Warnings reset.")

@bot.command()
@commands.has_permissions(administrator=True)
async def check_warnings(ctx, member: discord.Member):
    await ctx.send(
        f"{member.mention} has **{warnings.get(member.id,0)}/3** warnings."
    )

# ==========================
# BAD WORDS MANAGEMENT
# ==========================
@bot.command()
@commands.has_permissions(administrator=True)
async def add_bad_word(ctx, word: str):
    word = word.lower()
    if word not in BAD_WORDS:
        BAD_WORDS.append(word)
    await ctx.send(f"✅ Added `{word}`")

@bot.command()
@commands.has_permissions(administrator=True)
async def remove_bad_word(ctx, word: str):
    word = word.lower()
    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(f"✅ Removed `{word}`")
    else:
        await ctx.send("❌ Word not found.")

@bot.command()
@commands.has_permissions(administrator=True)
async def show_bad_words(ctx):
    if not BAD_WORDS:
        return await ctx.send("No bad words.")
    await ctx.send("\n".join(BAD_WORDS))

# ==========================
# MESSAGE FILTER
# ==========================
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if not message.guild:
        return await bot.process_commands(message)
    if not message.author.guild_permissions.administrator:
        content = message.content.lower()
        if INVITE_REGEX.search(content):
            await message.delete()
            await message.author.timeout(
                timedelta(minutes=1),
                reason="Discord Invite"
            )
            return
        for word in BAD_WORDS:
            if word in content:
                await message.delete()
                warnings[message.author.id] = warnings.get(
                    message.author.id, 0
                ) + 1
                log = discord.utils.get(
                    message.guild.text_channels,
                    name=LOG_CHANNEL_NAME
                )
                if log:
                    await log.send(
                        f"⚠️ {message.author.mention} used `{word}` "
                        f"({warnings[message.author.id]}/3)"
                    )
                if warnings[message.author.id] >= 3:
                    await message.author.timeout(
                        timedelta(minutes=10),
                        reason="3 Bad Words"
                    )
                    warnings[message.author.id] = 0
                return
    await bot.process_commands(message)

# ==========================
# RUN BOT
# ==========================
TOKEN = os.getenv('DISCORD_TOKEN')
if TOKEN is None:
    print("❌ Error: DISCORD_TOKEN not found!")
    sys.exit(1)

print("🚀 Starting bot...")
keep_alive()
print("🤖 Bot is starting...")
try:
    bot.run(TOKEN)
except Exception as e:
    print(f"❌ Bot error: {e}")
    sys.exit(1)
