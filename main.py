import asyncio
import re
import os
import sys
import discord
from datetime import timedelta, datetime
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import json

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
# OWNER ID
# ==========================
bot.owner_id = 1454256976048558240

# ==========================
# SETTINGS
# ==========================
BAD_WORDS = ["rab", "omik", "o5tek"]
LOG_CHANNEL_NAME = "logs"
warnings = {}
last_voice_channel = {}
manual_leave = set()
warn_reasons = {}  # لتخزين أسباب التحذيرات

# ==========================
# ⭐ إعدادات الـ DEAF ⭐
# ==========================
AFK_CHANNEL_ID = 123456789012345678  # 🔥 غيرو بـ ID الروم الـ AFK متاعك
DEAF_THRESHOLD_MINUTES = 20  # المدة قبل النقل للـ AFK (بالدقائق)
deafened_users = {}  # لتخزين الأعضاء المتديفنيين مع وقت بداية الديفنينغ

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
    print(f"👑 Owner ID: {bot.owner_id}")
    
    # ⭐ بدء المهمة الدورية للتحقق من الـ Deaf
    check_deaf_users.start()
    print("🔇 Deaf monitor started!")

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
@commands.is_owner()
async def write(ctx, *, message):
    await ctx.message.delete()
    await ctx.send(message)

# ==========================
# VOICE COMMANDS
# ==========================
@bot.command()
@commands.is_owner()
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
@commands.is_owner()
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
    # ⭐ معالجة الـ Deaf
    if not member.bot:  # نتجاهل البوتات
        # إذا العضو أصبح متديفن (Server Deaf)
        if after.deaf and not before.deaf:
            deafened_users[member.id] = datetime.now()
            print(f"🔇 {member.name} has been deafened at {deafened_users[member.id]}")
            
            # نرسل تحذير خاص
            try:
                await member.send(f"🔇 You have been deafened in **{member.guild.name}**. You will be moved to AFK after {DEAF_THRESHOLD_MINUTES} minutes of being deaf.")
            except:
                pass
            
            # نبعث رسالة في الـ logs
            log = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
            if log:
                await log.send(f"🔇 {member.mention} has been deafened. Will be moved to AFK after {DEAF_THRESHOLD_MINUTES} minutes.")

        # إذا العضو فك الديفنينغ
        elif not after.deaf and before.deaf:
            if member.id in deafened_users:
                elapsed = (datetime.now() - deafened_users[member.id]).total_seconds() / 60
                del deafened_users[member.id]
                print(f"🔊 {member.name} is no longer deafened (was deaf for {elapsed:.1f} min)")
                
                # نرسل رسالة في الـ logs
                log = discord.utils.get(member.guild.text_channels, name=LOG_CHANNEL_NAME)
                if log:
                    await log.send(f"🔊 {member.mention} is no longer deafened (was deaf for {elapsed:.1f} minutes)")

    # ==========================
    # الجزء القديم لإعادة الاتصال (خاص بالبوت)
    # ==========================
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
# ⭐ مهمة التحقق من الـ Deaf (كل دقيقة) ⭐
# ==========================
@tasks.loop(seconds=60)  # تتحقق كل 60 ثانية
async def check_deaf_users():
    now = datetime.now()
    
    for user_id, deaf_since in list(deafened_users.items()):
        elapsed = (now - deaf_since).total_seconds() / 60
        
        if elapsed >= DEAF_THRESHOLD_MINUTES:
            # نجيب العضو
            member = bot.get_user(user_id)
            if member is None:
                # نحاول نجيبو من الـ guilds
                for guild in bot.guilds:
                    member = guild.get_member(user_id)
                    if member:
                        break
            
            if member is None:
                # إذا ما لقيناهش نحيوه من القائمة
                del deafened_users[user_id]
                continue
            
            # نجيب الـ AFK channel
            afk_channel = bot.get_channel(AFK_CHANNEL_ID)
            if not afk_channel:
                print(f"❌ AFK channel not found! ID: {AFK_CHANNEL_ID}")
                # نجيب أول قناة AFK في السيرفر
                for guild in bot.guilds:
                    for channel in guild.voice_channels:
                        if channel.name.lower() == "afk":
                            afk_channel = channel
                            break
                    if afk_channel:
                        break
            
            if not afk_channel:
                print("❌ No AFK channel found!")
                continue
            
            # نجيب الـ voice state متاع العضو
            voice_state = None
            for guild in bot.guilds:
                member_in_guild = guild.get_member(user_id)
                if member_in_guild and member_in_guild.voice:
                    voice_state = member_in_guild.voice
                    break
            
            if voice_state and voice_state.channel:
                try:
                    # نحرك العضو للـ AFK
                    await member_in_guild.move_to(afk_channel)
                    print(f"🚀 Moved {member.name} to AFK channel (deaf for {elapsed:.1f} min)")
                    
                    # نرسل رسالة في الـ logs
                    log = discord.utils.get(member_in_guild.guild.text_channels, name=LOG_CHANNEL_NAME)
                    if log:
                        await log.send(f"🚀 {member.mention} has been moved to AFK (deaf for {elapsed:.1f} minutes)")
                    
                    # نرسل رسالة خاصة للعضو
                    try:
                        await member.send(f"🚀 You have been moved to AFK in **{member_in_guild.guild.name}** because you were deafened for {DEAF_THRESHOLD_MINUTES} minutes.")
                    except:
                        pass
                    
                    # نحيو العضو من القائمة
                    del deafened_users[user_id]
                    
                except Exception as e:
                    print(f"❌ Failed to move {member.name}: {e}")
            else:
                # إذا العضو مش في voice channel نحيوه من القائمة
                del deafened_users[user_id]

# ==========================
# ⭐ أوامر التحكم في الـ Deaf ⭐
# ==========================

@bot.command()
@commands.is_owner()
async def set_afk_channel(ctx, channel_id: int):
    """تغيير الـ AFK channel"""
    global AFK_CHANNEL_ID
    AFK_CHANNEL_ID = channel_id
    await ctx.send(f"✅ AFK channel set to <#{channel_id}>")

@bot.command()
@commands.is_owner()
async def set_deaf_time(ctx, minutes: int):
    """تغيير المدة قبل النقل للـ AFK (بالدقائق)"""
    global DEAF_THRESHOLD_MINUTES
    if minutes < 1:
        return await ctx.send("❌ Time must be at least 1 minute.")
    DEAF_THRESHOLD_MINUTES = minutes
    await ctx.send(f"✅ Deaf threshold set to {minutes} minutes")

@bot.command()
@commands.is_owner()
async def deaf_list(ctx):
    """يعرض الأعضاء المتديفنيين والمدة"""
    if not deafened_users:
        return await ctx.send("🔇 No deaf users currently tracked.")
    
    embed = discord.Embed(
        title="🔇 Deaf Users Tracking",
        color=discord.Color.red()
    )
    
    now = datetime.now()
    for user_id, since in list(deafened_users.items()):
        member = bot.get_user(user_id)
        if member is None:
            # نحاول نجيبو من الـ guilds
            for guild in bot.guilds:
                member = guild.get_member(user_id)
                if member:
                    break
        
        if member:
            elapsed = (now - since).total_seconds() / 60
            embed.add_field(
                name=member.display_name,
                value=f"⏱️ {elapsed:.1f} minutes\n🆔 {user_id}",
                inline=False
            )
    
    embed.set_footer(text=f"Threshold: {DEAF_THRESHOLD_MINUTES} minutes")
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def deaf_force_move(ctx, member: discord.Member):
    """ينقل عضو متديفن للـ AFK فوراً"""
    if member.id not in deafened_users:
        return await ctx.send(f"❌ {member.mention} is not being tracked as deaf.")
    
    afk_channel = bot.get_channel(AFK_CHANNEL_ID)
    if not afk_channel:
        return await ctx.send("❌ AFK channel not found!")
    
    try:
        await member.move_to(afk_channel)
        del deafened_users[member.id]
        await ctx.send(f"✅ {member.mention} moved to AFK channel manually.")
        
        # نرسل رسالة في الـ logs
        log = discord.utils.get(ctx.guild.text_channels, name=LOG_CHANNEL_NAME)
        if log:
            await log.send(f"🚀 {member.mention} manually moved to AFK by {ctx.author.mention}")
    except Exception as e:
        await ctx.send(f"❌ Failed to move: {e}")

# ==========================
# WARNINGS
# ==========================
@bot.command()
@commands.is_owner()
async def reset_warnings(ctx, member: discord.Member):
    warnings[member.id] = 0
    if member.id in warn_reasons:
        warn_reasons[member.id] = []
    await ctx.send(f"✅ Warnings reset for {member.mention}.")

@bot.command()
@commands.is_owner()
async def check_warnings(ctx, member: discord.Member):
    await ctx.send(
        f"{member.mention} has **{warnings.get(member.id,0)}/3** warnings."
    )

# ==========================
# BAD WORDS MANAGEMENT
# ==========================
@bot.command()
@commands.is_owner()
async def add_bad_word(ctx, word: str):
    word = word.lower()
    if word not in BAD_WORDS:
        BAD_WORDS.append(word)
    await ctx.send(f"✅ Added `{word}`")

@bot.command()
@commands.is_owner()
async def remove_bad_word(ctx, word: str):
    word = word.lower()
    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(f"✅ Removed `{word}`")
    else:
        await ctx.send("❌ Word not found.")

@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):
    if not BAD_WORDS:
        return await ctx.send("No bad words.")
    await ctx.send("\n".join(BAD_WORDS))

# ==========================
# ⭐ الأوامر الجديدة ⭐
# ==========================

# 1️⃣ أمر !avatar
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """يعرض صورة البروفايل لعضو"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(
        title=f"🖼️ {member.display_name}'s Avatar",
        color=discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

# 2️⃣ أمر !clear
@bot.command()
@commands.is_owner()
async def clear(ctx, amount: int):
    """يحذف عدد محدد من الرسائل"""
    if amount < 1:
        return await ctx.send("❌ Please specify a number greater than 0.")
    
    if amount > 100:
        return await ctx.send("❌ Cannot delete more than 100 messages at once.")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ Deleted {len(deleted) - 1} messages.", delete_after=3)

# 3️⃣ أمر !warn
@bot.command()
@commands.is_owner()
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """يحذر عضو مع سبب"""
    # زيادة عدد التحذيرات
    warnings[member.id] = warnings.get(member.id, 0) + 1
    
    # حفظ سبب التحذير
    if member.id not in warn_reasons:
        warn_reasons[member.id] = []
    warn_reasons[member.id].append({
        "reason": reason,
        "by": ctx.author.id,
        "time": ctx.message.created_at.strftime("%Y-%m-%d %H:%M")
    })
    
    # إرسال تحذير خاص للعضو
    try:
        await member.send(f"⚠️ You have been warned in **{ctx.guild.name}**\nReason: {reason}\nWarnings: {warnings[member.id]}/3")
    except:
        pass
    
    # إرسال رسالة في الشات
    embed = discord.Embed(
        title="⚠️ Warning",
        description=f"{member.mention} has been warned!",
        color=discord.Color.orange()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Warnings", value=f"{warnings[member.id]}/3", inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)
    
    # إذا وصل لـ 3 تحذيرات، يتم تكميمه
    if warnings[member.id] >= 3:
        await member.timeout(timedelta(minutes=10), reason="3 warnings")
        await ctx.send(f"🔇 {member.mention} has been timed out for 10 minutes (3 warnings).")
        warnings[member.id] = 0  # إعادة ضبط التحذيرات

# 4️⃣ أمر !warnings
@bot.command()
@commands.is_owner()
async def warnings(ctx, member: discord.Member):
    """يعرض تحذيرات عضو مع الأسباب"""
    count = warnings.get(member.id, 0)
    
    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Total Warnings", value=f"{count}/3", inline=False)
    
    # عرض أسباب التحذيرات
    if member.id in warn_reasons and warn_reasons[member.id]:
        reasons_text = ""
        for i, warn_data in enumerate(warn_reasons[member.id], 1):
            reasons_text += f"**{i}.** {warn_data['reason']} (by <@{warn_data['by']}> at {warn_data['time']})\n"
        embed.add_field(name="Reasons", value=reasons_text, inline=False)
    else:
        embed.add_field(name="Reasons", value="No warnings recorded.", inline=False)
    
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)

# 5️⃣ أمر !clear (نسخة بدون Admin)
@bot.command()
@commands.is_owner()
async def clear_all(ctx, amount: int):
    """يحذف عدد محدد من الرسائل (نسخة احتياطية)"""
    if amount < 1:
        return await ctx.send("❌ Please specify a number greater than 0.")
    if amount > 100:
        return await ctx.send("❌ Cannot delete more than 100 messages at once.")
    
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ Deleted {len(deleted)} messages.", delete_after=3)

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
