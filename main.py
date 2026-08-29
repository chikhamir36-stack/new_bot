import asyncio
import re
import os
os.system("pip install pynacl")
import sys
import discord
from datetime import datetime, timedelta
from discord.ext import commands, tasks
from flask import Flask
from threading import Thread
import json
from typing import Optional
import random

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
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================
# OWNER ID
# ==========================
bot.owner_id = 1454256976048558240

# ==========================
# SETTINGS
# ==========================
BAD_WORDS = ["rab", "omk", "o5tek"]
LOG_CHANNEL_NAME = "logs"
warnings = {}
last_voice_channel = {}
manual_leave = set()
warn_reasons = {}

# 📊 بيانات الدعوات
invite_data = {}

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?(discord\.gg|discord\.com/invite|discord\.app/invite)/\S+",
    re.I
)

# ==========================
# 📊 نظام المستويات (Level System)
# ==========================

LEVEL_FILE = "level_data.json"

# متغيرات عامة
user_data = {}  # {user_id: {"xp": 0, "level": 0}}
level_rewards = {}  # {role_name: level}
voice_time = {}  # {user_id: start_time}

# ==========================
# 💾 حفظ وتحميل البيانات
# ==========================

def load_levels():
    """تحميل بيانات المستويات من الملف"""
    global user_data, level_rewards
    try:
        with open(LEVEL_FILE, "r") as f:
            data = json.load(f)
            user_data = data.get("user_data", {})
            level_rewards = data.get("level_rewards", {})
        print("✅ تم تحميل بيانات المستويات!")
    except FileNotFoundError:
        user_data = {}
        level_rewards = {}
        print("📝 تم إنشاء ملف بيانات جديد!")
    except:
        user_data = {}
        level_rewards = {}
        print("⚠️ خطأ في تحميل البيانات، تم إنشاء بيانات جديدة!")

def save_levels():
    """حفظ بيانات المستويات في الملف"""
    data = {
        "user_data": user_data,
        "level_rewards": level_rewards
    }
    try:
        with open(LEVEL_FILE, "w") as f:
            json.dump(data, f, indent=4)
        print("💾 تم حفظ بيانات المستويات!")
    except Exception as e:
        print(f"❌ خطأ في حفظ البيانات: {e}")

# تحميل البيانات عند التشغيل
load_levels()

# ==========================
# 📊 دوال XP
# ==========================

def get_user(user_id):
    """يجيب بيانات مستخدم"""
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {"xp": 0, "level": 0}
        save_levels()
    return user_data[user_id]

def add_xp(user_id, amount):
    """يزيد نقاط المستخدم ويرجع True إذا ترقى"""
    user = get_user(user_id)
    user["xp"] += amount
    
    xp_needed = (user["level"] + 1) * 100
    
    if user["xp"] >= xp_needed:
        user["xp"] = 0
        user["level"] += 1
        save_levels()
        return True
    save_levels()
    return False

# ==========================
# 🎖️ إعطاء الرتب
# ==========================

async def check_rank(member):
    """يعطي رتبة للعضو حسب مستواه"""
    user = get_user(member.id)
    level = user["level"]
    
    role_to_give = None
    for role_name, req_level in level_rewards.items():
        if level >= req_level:
            role_to_give = role_name
    
    if role_to_give is None:
        return
    
    role = discord.utils.get(member.guild.roles, name=role_to_give)
    if role is None:
        try:
            role = await member.guild.create_role(
                name=role_to_give,
                color=discord.Color.gold(),
                reason=f"Level {level} reached"
            )
            print(f"✅ تم إنشاء رتبة: {role_to_give}")
        except:
            return
    
    if role not in member.roles:
        try:
            await member.add_roles(role, reason=f"Reached Level {level}")
            print(f"🎖️ {member.display_name} got {role_to_give}")
        except:
            pass

# ==========================
# READY
# ==========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Bot is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guilds")
    print(f"👑 Owner ID: {bot.owner_id}")
    
    load_levels()  # تحميل البيانات
    update_voice_xp_level.start()  # بدء تحديث الصوت
    print("🎵 Voice XP tracker started!")
    
    # 📊 تحميل بيانات الدعوات
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            for invite in invites:
                if invite.inviter:
                    inviter_id = str(invite.inviter.id)
                    if inviter_id not in invite_data:
                        invite_data[inviter_id] = 0
                    invite_data[inviter_id] += invite.uses
        except:
            pass
    print("📊 Invite data loaded!")

# ==========================
# HELLO COMMAND
# ==========================
@bot.command()
@commands.is_owner()
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
# 🎵 أوامر الصوت المتكاملة
# ==========================

# متغيرات لتتبع حالة البوت الصوتي
last_voice_channel = {}  # {guild_id: channel_id}
manual_leave = set()  # {guild_id} للغادرين يدوياً

@bot.command()
@commands.is_owner()
async def join(ctx):
    """يدخل البوت للروم الصوتي اللي انت فيه"""
    
    if not ctx.author.voice:
        return await ctx.send("❌ You must be in a voice channel first!")
    
    channel = ctx.author.voice.channel
    
    permissions = channel.permissions_for(ctx.guild.me)
    if not permissions.connect:
        return await ctx.send("❌ I don't have permission to join that voice channel!")
    if not permissions.speak:
        return await ctx.send("❌ I don't have permission to speak in that voice channel!")
    
    try:
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"✅ Moved to **{channel.name}**")
        else:
            await channel.connect()
            await ctx.send(f"✅ Joined **{channel.name}**")
        
        last_voice_channel[ctx.guild.id] = channel.id
        
        if ctx.guild.id in manual_leave:
            manual_leave.remove(ctx.guild.id)
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

@bot.command()
@commands.is_owner()
async def leave(ctx):
    """يخرج البوت من الروم الصوتي"""
    
    if not ctx.voice_client:
        return await ctx.send("❌ I'm not in a voice channel!")
    
    manual_leave.add(ctx.guild.id)
    
    try:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left voice channel!")
        
        if ctx.guild.id in last_voice_channel:
            del last_voice_channel[ctx.guild.id]
            
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

# ==========================
# إعادة الاتصال التلقائي
# ==========================

@bot.event
async def on_voice_state_update(member, before, after):
    """
    يراقب حالة البوت الصوتي:
    - إذا طلع بالغلط (Disconnect) يرجع تلقائياً
    - إذا تحرك لروم آخر يتابعه
    """
    
    # نتجاوز كل الأعضاء ما عدا البوت نفسه
    if member.id == bot.user.id:
        guild = member.guild
        
        # ===== إذا دخل البوت لروم =====
        if after.channel:
            last_voice_channel[guild.id] = after.channel.id
            print(f"🔊 Bot moved to: {after.channel.name}")
            return
        
        # ===== إذا طلع البوت =====
        # نتحقق إذا كان طلع يدوياً (أمر !leave)
        if guild.id in manual_leave:
            manual_leave.remove(guild.id)
            print("👋 Bot left manually (via !leave)")
            return
        
        # ===== إذا طلع بالغلط (Disconnect) =====
        if before.channel and guild.id in last_voice_channel:
            await asyncio.sleep(3)  # نستنى 3 ثواني
            
            try:
                # نتحقق إذا البوت لسا خارج
                if guild.voice_client is None:
                    # نجيب الروم المخزن
                    channel = guild.get_channel(last_voice_channel[guild.id])
                    
                    if channel:
                        # نرجع البوت للروم
                        await channel.connect()
                        print(f"🔄 Bot reconnected to: {channel.name}")
                        
                        # نرسل رسالة في الـ logs
                        log_channel = discord.utils.get(guild.text_channels, name="logs")
                        if log_channel:
                            await log_channel.send("🔄 **Bot reconnected automatically!**")
                            
            except Exception as e:
                print(f"❌ Reconnect error: {e}")
    
    # 🛏️ نظام AFK (Self-Deaf) - للأعضاء العاديين
    if member.bot:
        return
    
    # ===== كشف Self-Deaf =====
    if after.self_deaf and not before.self_deaf:
        # العضو عمل Self-Deaf
        afk_tracker[member.id] = {
            "start_time": discord.utils.utcnow(),
            "message_sent": False,
            "channel_id": after.channel.id if after.channel else None
        }
        print(f"🔇 {member.display_name} عمل Self-Deaf")
        
        # نبدا المهمة لمراقبة الوقت
        asyncio.create_task(afk_monitor(member))
    
    # ===== كشف إلغاء Self-Deaf =====
    elif not after.self_deaf and before.self_deaf:
        # العضو ألغى الـ Self-Deaf
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            print(f"🔊 {member.display_name} cancel Self-Deaf")
    
    # 🎵 XP من الصوت - نظام المستويات
    afk = discord.utils.get(member.guild.voice_channels, name="├😴・𝙰𝚏𝚔")
    
    # إذا دخل روم AFK
    if after.channel == afk:
        if str(member.id) in voice_time:
            del voice_time[str(member.id)]
        return
    
    # إذا دخل روم صوتي
    if after.channel and before.channel is None:
        voice_time[str(member.id)] = datetime.utcnow()
    
    # إذا خرج من روم صوتي
    elif before.channel and after.channel is None:
        if str(member.id) in voice_time:
            start = voice_time[str(member.id)]
            diff = (datetime.utcnow() - start).total_seconds()
            xp = int(diff // 60)
            
            if xp > 0:
                leveled = add_xp(member.id, xp)
                if leveled:
                    await check_rank(member)
                    
                    channel = discord.utils.get(member.guild.text_channels, name="└📊・𝐋𝐞𝐯𝐞𝐥-𝐔𝐏")
                    if channel is None:
                        overwrites = {
                            member.guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
                            member.guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
                        }
                        channel = await member.guild.create_text_channel(
                            name="└📊・𝐋𝐞𝐯𝐞𝐥-𝐔𝐏",
                            overwrites=overwrites,
                            reason="تم إنشاء روم الترقيات"
                        )
                    
                    user = get_user(member.id)
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"{member.mention} reached **Level {user['level']}** from voice!",
                        color=discord.Color.gold()
                    )
                    await channel.send(embed=embed)
            
            del voice_time[str(member.id)]

# 🛏️ متغيرات AFK
afk_tracker = {}  # {user_id: {"start_time": timestamp, "message_sent": False, "channel_id": channel_id}}

async def afk_monitor(member):
    """تراقب العضو اللي عمل Self-Deaf"""
    
    # نستنى 5 دقائق باش نبعث الرسالة
    await asyncio.sleep(300)  # 5 دقائق = 300 ثانية
    
    # نتحقق إذا كان العضو لسا في الـ AFK
    if member.id not in afk_tracker:
        return
    
    # نتحقق إذا كان لسا Self-Deaf
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    # نبعث الرسالة (مرة وحدة)
    if not afk_tracker[member.id]["message_sent"]:
        afk_tracker[member.id]["message_sent"] = True
        
        try:
            # نبعث رسالة خاصة
            embed = discord.Embed(
                title="🔇 alert to AFK",
                description="You are currently **deafened** in **𝙳𝚎𝚊𝚝𝚑 𝚆𝚑𝚒𝚜𝚙𝚎𝚛 𝙲𝚘𝚖𝚖𝚞𝚗𝚒𝚝𝚢**.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="⏰ alert",
                value="You will be moved to **AFK** after **1 hour** of being deaf.",
                inline=False
            )
            embed.set_footer(text="🔊 Unmute yourself to cancel AFK")
            
            await member.send(embed=embed)
            print(f"📩AFK message sent to{member.display_name}")
            
        except:
            print(f"❌ i cant send message to {member.display_name} (DM locked)")
    
    # نستنى ساعة كاملة (3600 ثانية) باش نحرك
    await asyncio.sleep(3600)  # ساعة = 3600 ثانية
    
    # نتحقق مرة أخرى
    if member.id not in afk_tracker:
        return
    
    if not member.voice or not member.voice.self_deaf:
        if member.id in afk_tracker:
            del afk_tracker[member.id]
        return
    
    # ===== نحرك العضو لروم AFK =====
    try:
        # نجيب الروم AFK
        afk_channel = discord.utils.get(member.guild.voice_channels, name="├😴・𝙰𝚏𝚔")
        
        if afk_channel is None:
            print("❌ روم AFK مش موجود!")
            # نعمل روم إذا مش موجود
            afk_channel = await member.guild.create_voice_channel(
                name="├😴・𝙰𝚏𝚔",
                reason="تم إنشاء روم AFK تلقائياً"
            )
            print("✅ تم إنشاء روم AFK")
        
        # نحرك العضو
        await member.move_to(afk_channel, reason="Self-Deaf For one hour ")
        print(f"🚀{member.display_name} has been moved to afk ")
        
        # نرسل رسالة في الشات
        channel = discord.utils.get(member.guild.text_channels, name="logs")
        if channel is None:
            channel = member.guild.system_channel
        
        if channel:
            await channel.send(f"🔇 {member.mention} He was transferred to **AFK** one hour after the Self-Deaf.")
        
        # نحذف من التراكر
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            
    except Exception as e:
        print(f"❌ Organ transfer error: {e}")

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
    warnings[member.id] = warnings.get(member.id, 0) + 1
    
    if member.id not in warn_reasons:
        warn_reasons[member.id] = []
    warn_reasons[member.id].append({
        "reason": reason,
        "by": ctx.author.id,
        "time": ctx.message.created_at.strftime("%Y-%m-%d %H:%M")
    })
    
    try:
        await member.send(f"⚠️ You have been warned in **{ctx.guild.name}**\nReason: {reason}\nWarnings: {warnings[member.id]}/3")
    except:
        pass
    
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
    
    if warnings[member.id] >= 3:
        await member.timeout(timedelta(minutes=10), reason="3 warnings")
        await ctx.send(f"🔇 {member.mention} has been timed out for 10 minutes (3 warnings).")
        warnings[member.id] = 0

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
        return await ctx.send("❌ Please specify
