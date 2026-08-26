import asyncio
import re
import os
os.system("pip install pynacl")
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
    if member.id != bot.user.id:
        return
    
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
            title="📩 Message from 𝙳𝚎𝚊𝚝𝚑 𝚆𝚑𝚒𝚜𝚙𝚎𝚛 𝙲𝚘𝚖𝚖𝚞𝚗𝚒𝚝𝚢",
            description=message,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} • {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        await member.send(embed=embed)
        await ctx.send(f"✅ The message was sent successfully! **{member.display_name}** ")
    except discord.Forbidden:
        await ctx.send(f"❌ I can't send a message to**{member.display_name}** (DM locked )")
    except Exception as e:
        await ctx.send(f"❌error : {str(e)}")

# 7️⃣ أمر !dmrole
@bot.command()
@commands.is_owner()
async def dmrole(ctx, role: discord.Role, *, message: str):
    """يبعث رسالة خاصة لجميع أعضاء دور معين"""
    confirm_msg = await ctx.send(f"⚠️ **You are about to send a DM to {len(role.members)} member ** In a role {role.mention}\nmessage : \"{message}\"\n\nReply with **yes** Confirmation or **no** to cancel  (30 S )")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("❌Cancelled.")
        
        await ctx.send(f"⏳Messages are being sent to {len(role.members)} member ...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="📢  Message from 𝙳𝚎𝚊𝚝𝚑 𝚆𝚑𝚒𝚜𝚙𝚎𝚛 𝙲𝚘𝚖𝚖𝚞𝚗𝚒𝚝𝚢",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} • {ctx.guild.name}")
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
        
        await ctx.send(f"✅ **Sent successfully!**\n✅succeeded: {success_count}\n❌ fail: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("⏰Time's up! Cancelled.")

# 8️⃣ أمر !dmall
@bot.command()
@commands.is_owner()
async def dmall(ctx, *, message: str):
    """يبعث رسالة خاصة لجميع الأعضاء (باستثناء البوتات)"""
    members = [m for m in ctx.guild.members if not m.bot]
    
    confirm_msg = await ctx.send(f"⚠️ **You are about to send a DM to {len(members)} member **\nmessage: \"{message}\"\n\nReply with **yes** To confirm or **no** Cancel (30 S)")
    
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['yes', 'no']
    
    try:
        response = await bot.wait_for('message', timeout=30.0, check=check)
        
        if response.content.lower() == 'no':
            return await ctx.send("❌ Cancelled.")
        
        await ctx.send(f"⏳ Messages are being sent to {len(members)} member ...")
        
        success_count = 0
        fail_count = 0
        
        embed = discord.Embed(
            title="📢  Message from 𝙳𝚎𝚊𝚝𝚑 𝚆𝚑𝚒𝚜𝚙𝚎𝚛 𝙲𝚘𝚖𝚖𝚞𝚗𝚒𝚝𝚢",
            description=message,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"from: {ctx.author.display_name} • {ctx.guild.name}")
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        for member in members:
            try:
                await member.send(embed=embed)
                success_count += 1
                await asyncio.sleep(0.3)
            except:
                fail_count += 1
        
        await ctx.send(f"✅ **Sent successfully!**\n✅  succeeded: {success_count}\n❌fail: {fail_count}")
        
    except asyncio.TimeoutError:
        await ctx.send("⏰ime's up! Cancelled.")


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
            print(f"🔊 {member.display_name} cancel Self-Deaf")


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
# 📊 LEADERBOARD (للكل) - النسخة المتطورة
# ==========================

# متغيرات لتتبع الدعوات
invite_data = {}  # {user_id: invites_count}
invite_cache = {}  # {guild_id: {invite_code: invite_object}}

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
            # نخزن الدعوات في الكاش
            invite_cache[guild.id] = {}
            for invite in invites:
                invite_cache[guild.id][invite.code] = invite
                
                # نخزن عدد الدعوات لكل عضو
                if invite.inviter:
                    inviter_id = str(invite.inviter.id)
                    if inviter_id not in invite_data:
                        invite_data[inviter_id] = 0
                    invite_data[inviter_id] += invite.uses
        except Exception as e:
            print(f"❌ Error loading invitations: {e}")
    print("📊 Invite data loaded!")

@bot.event
async def on_member_join(member):
    """تحديث الدعوات عند دخول عضو جديد"""
    
    guild = member.guild
    
    # نتجاوز البوتات
    if member.bot:
        return
    
    try:
        # نجيب الدعوات الجديدة
        new_invites = await guild.invites()
        
        # نقارن مع الدعوات القديمة
        for invite in new_invites:
            # نبحث عن الدعوة اللي زاد فيها العدد
            old_invite = invite_cache.get(guild.id, {}).get(invite.code)
            
            if old_invite:
                # إذا زاد عدد الدعوات
                if invite.uses > old_invite.uses:
                    inviter = invite.inviter
                    if inviter and not inviter.bot:
                        # نزيد عدد الدعوات للداعي
                        inviter_id = str(inviter.id)
                        invite_data[inviter_id] = invite_data.get(inviter_id, 0) + 1
                        print(f"✅ {inviter.display_name} invite {member.display_name}")
                        
                        # نبعث رسالة للداعي
                        try:
                            await inviter.send(f"🎉 {member.display_name} You entered the server with your invitation! Your current number of invitations: {invite_data[inviter_id]}")
                        except:
                            pass
                        break
        
        # نحدث الكاش
        for invite in new_invites:
            invite_cache[guild.id][invite.code] = invite
            
    except Exception as e:
        print(f"❌ خطأ في تحديث الدعوات: {e}")

@bot.command()  # للكل
async def leaderboard(ctx):
    """يعرض ترتيب الأعضاء حسب عدد الدعوات (للجميع)"""
    
    if not invite_data:
        return await ctx.send("📊 No invites found! Start inviting people!")
    
    # نرتب الدعوات من الأكبر للأصغر
    sorted_invites = sorted(invite_data.items(), key=lambda x: x[1], reverse=True)
    
    # ناخذ الـ Top 10
    top_10 = sorted_invites[:10]
    
    embed = discord.Embed(
        title="🏆 Leaderboard - Invites",
        description="Top 10 Invited Members",
        color=discord.Color.gold()
    )
    
    description = ""
    for i, (user_id, count) in enumerate(top_10, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.display_name
        except:
            name = f"Unknown User"
        
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
# أوامر إضافية للدعوات
# ==========================

@bot.command()
async def invites(ctx, member: discord.Member = None):
    """يعرض عدد دعوات عضو معين"""
    
    if member is None:
        member = ctx.author
    
    count = invite_data.get(str(member.id), 0)
    
    embed = discord.Embed(
        title="📊 Invites",
        description=f"{member.mention} has **{count}** invites!",
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    embed.set_thumbnail(url=member.display_avatar.url)
    
    await ctx.send(embed=embed)

@bot.command()
@commands.is_owner()
async def reset_invites(ctx, member: discord.Member = None):
    """يعيد ضبط دعوات عضو (للـ Owner فقط)"""
    
    if member is None:
        return await ctx.send("❌ identif the member: `!reset_invites @user`")
    
    invite_data[str(member.id)] = 0
    await ctx.send(f"✅The invitations have been reset {member.mention}")

@bot.command()
@commands.is_owner()
async def set_invites(ctx, member: discord.Member, count: int):
    """يحدد عدد دعوات عضو (للـ Owner فقط)"""
    
    if count < 0:
        return await ctx.send("❌ The number must be positive!")
    
    invite_data[str(member.id)] = count
    await ctx.send(f"✅ The invitations have been {member.mention} to `{count}`")

# ==========================
# 📦 أمر !embed (النسخة الكاملة)
# ==========================

@bot.command()
@commands.is_owner()
async def embed(ctx, *, message: str):
    """
    يبعث رسالة في Embed مع إطار جميل
    استعمل: !embed نص الرسالة
    """
    
    # نقسم الرسالة إلى عنوان ووصف إذا كانت تحتوي على "|"
    if "|" in message:
        parts = message.split("|", 1)
        title = parts[0].strip()
        description = parts[1].strip()
    else:
        title = None
        description = message
    
    # نعمل Embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blue()
    )
    
    # نضيف معلومات إضافية
    embed.set_footer(
        text=f"📝 from: {ctx.author.display_name}",
        icon_url=ctx.author.display_avatar.url
    )
    
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    
    embed.timestamp = discord.utils.utcnow()
    
    # نحذف رسالة المستخدم
    await ctx.message.delete()
    
    # نبعث الـ Embed
    await ctx.send(embed=embed)
# ==========================
# 8️⃣ أمر !lock (يقفل الشات)
# ==========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    """يقفل الشات (يمنع الأعضاء من الكتابة)"""
    
    channel = ctx.channel
    
    # نجيب صلاحيات @everyone
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    
    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔒 **{channel.mention} has been locked!**")
    except:
        await ctx.send("❌ I don't have permission to lock this channel!")

# ==========================
# 9️⃣ أمر !unlock (يفتح الشات)
# ==========================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    """يفتح الشات (يسمح للأعضاء بالكتابة)"""
    
    channel = ctx.channel
    
    # نجيب صلاحيات @everyone
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None  # نرجعها للوضع الافتراضي
    
    try:
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"🔓 **{channel.mention} has been unlocked!**")
    except:
        await ctx.send("❌ I don't have permission to unlock this channel!")
# ==========================
# 🚀 أوامر المعلومات (مضافة)
# ==========================

@bot.command()
async def serverinfo(ctx):
    """يعرض معلومات عن السيرفر"""
    
    guild = ctx.guild
    
    total_members = guild.member_count
    humans = len([m for m in guild.members if not m.bot])
    bots = total_members - humans
    
    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    categories = len(guild.categories)
    total_roles = len(guild.roles)
    
    embed = discord.Embed(
        title=f"📊 Server Info - {guild.name}",
        color=discord.Color.blue()
    )
    
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="🆔 ID", value=guild.id, inline=True)
    embed.add_field(name="📅 Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="👥 Members", value=f"{total_members} (👤{humans} 🤖{bots})", inline=True)
    embed.add_field(name="💬 Channels", value=f"📝{text_channels} 🔊{voice_channels} 📁{categories}", inline=True)
    embed.add_field(name="🎭 Roles", value=total_roles, inline=True)
    embed.add_field(name="🔗 Boost Level", value=guild.premium_tier, inline=True)
    embed.add_field(name="⭐ Boost Count", value=guild.premium_subscription_count, inline=True)
    
    if guild.vanity_url:
        embed.add_field(name="🔗 Vanity URL", value=guild.vanity_url, inline=False)
    
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    """يعرض معلومات عن عضو"""
    
    if member is None:
        member = ctx.author
    
    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
    roles_text = ", ".join(roles) if roles else "No roles"
    
    embed = discord.Embed(
        title=f"👤 User Info - {member.display_name}",
        color=member.color if member.color != discord.Color.default() else discord.Color.blue()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    
    embed.add_field(name="🆔 ID", value=member.id, inline=True)
    embed.add_field(name="📛 Name", value=member.name, inline=True)
    embed.add_field(name="🎭 Nickname", value=member.nick if member.nick else "None", inline=True)
    embed.add_field(name="📅 Joined", value=member.joined_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="📅 Created", value=member.created_at.strftime("%Y-%m-%d %H:%M"), inline=True)
    embed.add_field(name="🎭 Roles", value=roles_text, inline=False)
    embed.add_field(name="🤖 Bot", value="Yes" if member.bot else "No", inline=True)
    embed.add_field(name="🔊 In Voice", value="Yes" if member.voice else "No", inline=True)
    
    embed.set_footer(text=f"Requested by: {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

@bot.command()
async def ping(ctx):
    """يعرض سرعة استجابة البوت"""
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! `{latency}ms`")
# ==========================
# 👋 نظام المغادرة والدعوات
# ==========================

@bot.event
async def on_member_join(member):
    """عند دخول عضو جديد - يكتب في روم الدعوات"""
    
    guild = member.guild
    
    if member.bot:
        return
    
    # نجيب روم الدعوات
    invite_channel = discord.utils.get(guild.text_channels, name="├💌・𝗜𝗻𝘃𝗶𝘁𝗲")
    
    if invite_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
        }
        invite_channel = await guild.create_text_channel(
            name="├💌・𝗜𝗻𝘃𝗶𝘁𝗲",
            overwrites=overwrites,
            reason="تم إنشاء روم الدعوات"
        )
        print("✅ تم إنشاء روم الدعوات!")
    
    try:
        new_invites = await guild.invites()
        inviter = None
        
        for invite in new_invites:
            old_invite = invite_cache.get(guild.id, {}).get(invite.code)
            
            if old_invite:
                if invite.uses > old_invite.uses:
                    inviter = invite.inviter
                    break
        
        for invite in new_invites:
            if guild.id not in invite_cache:
                invite_cache[guild.id] = {}
            invite_cache[guild.id][invite.code] = invite
        
        if inviter and not inviter.bot:
            embed = discord.Embed(
                description=f"{member.mention} **Has Been Invited By** {inviter.mention}",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.utcnow()
            
            await invite_channel.send(embed=embed)
        else:
            embed = discord.Embed(
                description=f"{member.mention} **Joined the server!**",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"ID: {member.id}")
            embed.timestamp = datetime.utcnow()
            
            await invite_channel.send(embed=embed)
            
    except Exception as e:
        print(f"❌ خطأ في نظام الدعوات: {e}")

@bot.event
async def on_member_remove(member):
    """عند خروج عضو - يكتب في روم المغادرين"""
    
    guild = member.guild
    
    if member.bot:
        return
    
    leave_channel = discord.utils.get(guild.text_channels, name="├👋・𝐋𝐞𝐚𝐯𝐞𝐬")
    
    if leave_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=True, read_messages=True),
            guild.me: discord.PermissionOverwrite(send_messages=True, read_messages=True)
        }
        leave_channel = await guild.create_text_channel(
            name="├👋・𝐋𝐞𝐚𝐯𝐞𝐬",
            overwrites=overwrites,
            reason="تم إنشاء روم المغادرين"
        )
        print("✅ تم إنشاء روم المغادرين!")
    
    try:
        embed = discord.Embed(
            description=f"👋 **GODBYE** {member.mention}",
            color=discord.Color.red()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        embed.timestamp = datetime.utcnow()
        
        await leave_channel.send(embed=embed)
        
    except Exception as e:
        print(f"❌ خطأ في نظام المغادرة: {e}")
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
