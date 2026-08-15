import asyncio
import re
import os
import sys
import discord
from datetime import timedelta
from discord.ext import commands
from flask import Flask
from threading import Thread
import json
from typing import Optional

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
# READY
# ==========================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"✅ Bot is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guilds")
    print(f"👑 Owner ID: {bot.owner_id}")
    
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
        return await ctx.send("❌ Please specify a number greater than 0.")
    if amount > 100:
        return await ctx.send("❌ Cannot delete more than 100 messages at once.")
    
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"✅ Deleted {len(deleted)} messages.", delete_after=3)

# ==========================
# ⭐⭐⭐ أوامر DM ⭐⭐⭐
# ==========================

# 6️⃣ أمر !dm
@bot.command()
@commands.is_owner()
async def dm(ctx, member: discord.Member, *, message: str):
    """يبعث رسالة خاصة لعضو واحد"""
    try:
        embed = discord.Embed(
            title="📩 رسالة من الإدارة",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"من: {ctx.author.display_name} • {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        await member.send(embed=embed)
        await ctx.send(f"✅ تم إرسال الرسالة إلى **{member.display_name}** بنجاح!")
    except discord.Forbidden:
        await ctx.send(f"❌ لا يمكنني إرسال رسالة لـ **{member.display_name}** (الـDM مقفل)")
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {str(e)}")

# 7️⃣ أمر !dmrole
@bot.command()
@commands.is_owner()
async def dmrole(ctx, role: discord.Role, *, message: str):
    """يبعث رسالة خاصة لجميع أعضاء دور معين"""
    confirm_msg = await ctx.send(f"⚠️ **أنت على وشك إرسال DM لـ {len(role.members)} عضو** في دور {role.mention}\nالرسالة: \"{message}\"\n\nرد بـ **yes** للتأكيد أو **no** للإلغاء (30 ثانية)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("❌ تم الإلغاء.")
        
        await ctx.send(f"⏳ جاري إرسال الرسائل إلى {len(role.members)} عضو...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="📢 رسالة من الإدارة",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"من: {ctx.author.display_name} • {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for member in role.members:
            if member.bot:
                continue
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except:
                fail_count += 1
        
        await ctx.send(f"✅ **تم الإرسال بنجاح!**\n✅ نجح: {success_count}\n❌ فشل: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ انتهى الوقت! تم الإلغاء.")

# 8️⃣ أمر !dmall
@bot.command()
@commands.is_owner()
async def dmall(ctx, *, message: str):
    """يبعث رسالة خاصة لجميع الأعضاء (باستثناء البوتات)"""
    members = [m for m in ctx.guild.members if not m.bot]
    
    confirm_msg = await ctx.send(f"⚠️ **أنت على وشك إرسال DM لـ {len(members)} عضو**\nالرسالة: \"{message}\"\n\nرد بـ **yes** للتأكيد أو **no** للإلغاء (30 ثانية)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("❌ تم الإلغاء.")
        
        await ctx.send(f"⏳ جاري إرسال الرسائل إلى {len(members)} عضو...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="📢 إعلان من الإدارة",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"من: {ctx.author.display_name} • {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for member in members:
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except:
                fail_count += 1
        
        await ctx.send(f"✅ **تم الإرسال بنجاح!**\n✅ نجح: {success_count}\n❌ فشل: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ انتهى الوقت! تم الإلغاء.")

# 9️⃣ أمر !dmwithreason
@bot.command()
@commands.is_owner()
async def dmwithreason(ctx, member: discord.Member, *, message: str):
    """يبعث رسالة خاصة مع سبب (للتحذيرات مثلاً)"""
    try:
        embed = discord.Embed(
            title="📩 تنبيه من الإدارة",
            description=message,
            color=discord.Color.red()
        )
        embed.add_field(name="📌 سبب", value="تم إرسال هذه الرسالة للإشعار", inline=False)
        embed.set_footer(text=f"من: {ctx.author.display_name} • {ctx.guild.name}")
        
        await member.send(embed=embed)
        await ctx.send(f"✅ تم إرسال الرسالة إلى **{member.display_name}** مع سبب!")
    except:
        await ctx.send(f"❌ لا يمكن إرسال رسالة لـ **{member.display_name}**")

# 🔟 أمر !dmembed
@bot.command()
@commands.is_owner()
async def dmembed(ctx, member: discord.Member, title: str, *, description: str):
    """يبعث رسالة Embed مخصصة لعضو"""
    try:
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"من: {ctx.author.display_name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        await member.send(embed=embed)
        await ctx.send(f"✅ تم إرسال Embed إلى **{member.display_name}**!")
    except:
        await ctx.send(f"❌ لا يمكن إرسال Embed لـ **{member.display_name}**")


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
# 📸 أمر !photo (النسخة الصحيحة)
# ==========================

@bot.command()
@commands.is_owner()
async def photo(ctx):
    """
    يعلق المستخدم صورة، البوت يحذف الرسالة ويعيد نشر الصورة
    استعمل: !photo (مع صورة مرفقة)
    """
    
    # نتحقق إذا كان في صورة مرفقة
    if not ctx.message.attachments:
        return await ctx.send("❌ أرفق صورة مع الأمر! استعمل: `!photo` مع صورة", delete_after=5)
    
    # ناخذ أول صورة مرفقة
    attachment = ctx.message.attachments[0]
    
    # نتحقق إذا كانت الصورة بصيغة مسموحة
    if not attachment.content_type or not attachment.content_type.startswith('image/'):
        return await ctx.send("❌ هذا الملف ليس صورة! أرفق صورة بصيغة (png, jpg, gif, ...)", delete_after=5)
    
    try:
        # نحذف رسالة المستخدم
        await ctx.message.delete()
        
        # ===== الطريقة الصحيحة لإرسال الصورة =====
        # ناخذ رابط الصورة مباشرة
        image_url = attachment.url
        
        # نعمل Embed بالصورة
        embed = discord.Embed(
            color=discord.Color.blue()
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=f"📸 طلب من: {ctx.author.display_name}")
        
        # نبعث الـ Embed
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ حدث خطأ: {str(e)}", delete_after=5)
        # ==========================
# 🛏️ نظام AFK (Self-Deaf)
# ==========================

# متغيرات لتتبع الـ AFK
afk_tracker = {}  # {user_id: {"start_time": timestamp, "message_sent": False, "channel_id": channel_id}}

@bot.event
async def on_voice_state_update(member, before, after):
    """يكتشف الـ Self-Deaf ويدير نظام AFK"""
    
    # نتجاوز البوتات
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
            print(f"🔊 {member.display_name} ألغى Self-Deaf")


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
                title="🔇 تنبيه الـ AFK",
                description="You are currently **deafened** in **𝙳𝚎𝚊𝚝𝚑 𝚆𝚑𝚒𝚜𝚙𝚎𝚛 𝙲𝚘𝚖𝚖𝚞𝚗𝚒𝚝𝚢**.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="⏰ تنبيه",
                value="You will be moved to **AFK** after **1 hour** of being deaf.",
                inline=False
            )
            embed.set_footer(text="🔊 Unmute yourself to cancel AFK")
            
            await member.send(embed=embed)
            print(f"📩 تم إرسال رسالة AFK لـ {member.display_name}")
            
        except:
            print(f"❌ ما قدرتش نرسل رسالة لـ {member.display_name} (DM مقفل)")
    
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
        await member.move_to(afk_channel, reason="Self-Deaf لمدة ساعة")
        print(f"🚀 تم نقل {member.display_name} إلى روم AFK")
        
        # نرسل رسالة في الشات
        channel = discord.utils.get(member.guild.text_channels, name="general")
        if channel is None:
            channel = member.guild.system_channel
        
        if channel:
            await channel.send(f"🔇 {member.mention} تم نقله إلى **AFK** بعد ساعة من الـ Self-Deaf.")
        
        # نحذف من التراكر
        if member.id in afk_tracker:
            del afk_tracker[member.id]
            
    except Exception as e:
        print(f"❌ خطأ في نقل العضو: {e}")


# ==========================
# 📊 LEADERBOARD (للكل)
# ==========================

@bot.command()  # شلنا @commands.is_owner()
async def leaderboard(ctx):
    """يعرض ترتيب الأعضاء حسب عدد الدعوات (للجميع)"""
    
    if not invite_data:
        return await ctx.send("📊you dont have invites !")
    
    # نرتب الدعوات من الأكبر للأصغر
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)
    
    # ناخذ الـ Top 10
    top_10 = sorted_invites[:10]
    
    embed = discord.Embed(
        title="🏆 leaderboad-invites",
        description="Top 10 Invited Members",
        color=discord.Color.gold()
    )
    
    description = ""
    for i, (user_id, count) in enumerate(top_10, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.display_name
        except:
            name = f" (ID: {user_id})"
        
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"#{i}"
        
        description += f"{medal} **{name}** → `{count}` invites\n"
    
    embed.description = description
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
    
    await ctx.send(embed=embed)

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
