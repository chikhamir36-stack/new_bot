import asyncio
import re
import os
import sys
import discord
from datetime import timedelta, datetime
from discord.ext import commands
from flask import Flask
from threading import Thread
import json
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
# GIVEAWAY SYSTEM
# ==========================
active_giveaways = {}  # لتخزين السحوبات النشطة

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
async def joinvc(ctx):
    """الدخول إلى الروم الصوتي"""
    if not ctx.author.voice:
        return await ctx.send("❌ أنت لست في روم صوتي!")
    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    last_voice_channel[ctx.guild.id] = channel
    await ctx.send(f"✅ تم الدخول إلى **{channel.name}**")

@bot.command()
@commands.is_owner()
async def leavevc(ctx):
    """الخروج من الروم الصوتي"""
    if ctx.voice_client:
        manual_leave.add(ctx.guild.id)
        await ctx.voice_client.disconnect()
        await ctx.send("👋 تم الخروج من الروم الصوتي.")

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
    await ctx.send(f"✅ تم إعادة ضبط التحذيرات لـ {member.mention}.")

@bot.command()
@commands.is_owner()
async def check_warnings(ctx, member: discord.Member):
    await ctx.send(
        f"{member.mention} عنده **{warnings.get(member.id,0)}/3** تحذيرات."
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
    await ctx.send(f"✅ تم إضافة `{word}`")

@bot.command()
@commands.is_owner()
async def remove_bad_word(ctx, word: str):
    word = word.lower()
    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(f"✅ تم حذف `{word}`")
    else:
        await ctx.send("❌ الكلمة غير موجودة.")

@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):
    if not BAD_WORDS:
        return await ctx.send("لا توجد كلمات ممنوعة.")
    await ctx.send("\n".join(BAD_WORDS))

# ==========================
# ⭐ أوامر الصور ⭐
# ==========================

# 1️⃣ أمر !avatar
@bot.command()
async def avatar(ctx, member: discord.Member = None):
    """يعرض صورة البروفايل لعضو"""
    if member is None:
        member = ctx.author
    
    embed = discord.Embed(
        title=f"🖼️ صورة {member.display_name}",
        color=discord.Color.blue()
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"طلب بواسطة {ctx.author.display_name}")
    
    await ctx.send(embed=embed)

# 2️⃣ أمر !clear
@bot.command()
@commands.is_owner()
async def clear(ctx, amount: int):
    """يحذف عدد محدد من الرسائل"""
    if amount < 1:
        return await ctx.send("❌ الرقم يجب أن يكون أكبر من 0.")
    
    if amount > 100:
        return await ctx.send("❌ لا يمكن حذف أكثر من 100 رسالة.")
    
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ تم حذف {len(deleted) - 1} رسائل.", delete_after=3)

# 3️⃣ أمر !warn
@bot.command()
@commands.is_owner()
async def warn(ctx, member: discord.Member, *, reason: str = "لا يوجد سبب"):
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
        await member.send(f"⚠️ تم تحذيرك في **{ctx.guild.name}**\nالسبب: {reason}\nالتحذيرات: {warnings[member.id]}/3")
    except:
        pass
    
    # إرسال رسالة في الشات
    embed = discord.Embed(
        title="⚠️ تحذير",
        description=f"{member.mention} تم تحذيره!",
        color=discord.Color.orange()
    )
    embed.add_field(name="السبب", value=reason, inline=False)
    embed.add_field(name="التحذيرات", value=f"{warnings[member.id]}/3", inline=True)
    embed.add_field(name="المشرف", value=ctx.author.mention, inline=True)
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)
    
    # إذا وصل لـ 3 تحذيرات، يتم تكميمه
    if warnings[member.id] >= 3:
        await member.timeout(timedelta(minutes=10), reason="3 تحذيرات")
        await ctx.send(f"🔇 {member.mention} تم تكميمه لمدة 10 دقائق (3 تحذيرات).")
        warnings[member.id] = 0  # إعادة ضبط التحذيرات

# 4️⃣ أمر !warnings
@bot.command()
@commands.is_owner()
async def warnings(ctx, member: discord.Member):
    """يعرض تحذيرات عضو مع الأسباب"""
    count = warnings.get(member.id, 0)
    
    embed = discord.Embed(
        title=f"⚠️ تحذيرات {member.display_name}",
        color=discord.Color.blue()
    )
    embed.add_field(name="مجموع التحذيرات", value=f"{count}/3", inline=False)
    
    # عرض أسباب التحذيرات
    if member.id in warn_reasons and warn_reasons[member.id]:
        reasons_text = ""
        for i, warn_data in enumerate(warn_reasons[member.id], 1):
            reasons_text += f"**{i}.** {warn_data['reason']} (بواسطة <@{warn_data['by']}> في {warn_data['time']})\n"
        embed.add_field(name="الأسباب", value=reasons_text, inline=False)
    else:
        embed.add_field(name="الأسباب", value="لا توجد تحذيرات مسجلة.", inline=False)
    
    embed.set_footer(text=f"ID: {member.id}")
    
    await ctx.send(embed=embed)

# ==========================
# 🎉 نظام GIVEAWAY المتكامل 🎉
# ==========================

def parse_duration(duration_str):
    """تحويل المدة من نص إلى ثواني"""
    match = re.match(r"(\d+)([smhd])", duration_str.lower())
    if not match:
        return None
    
    value = int(match.group(1))
    unit = match.group(2)
    
    units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400
    }
    
    return value * units[unit]

@bot.command()
@commands.is_owner()
async def giveaway(ctx, 
                   prize: str, 
                   duration: str, 
                   winners: int = 1, 
                   description: str = None,
                   channel: discord.TextChannel = None,
                   image: str = None,
                   invites: int = 0):
    """
    !giveaway <الجائزة> <المدة> <عدد الفائزين> <الوصف> <الروم> <صورة> <الدعوات>
    
    مثال: !giveaway "NFT" 2h 3 "وصف" #السحوبات https://example.com/image.png 5
    """
    
    if channel is None:
        channel = ctx.channel
    
    # تحويل المدة إلى ثواني
    duration_seconds = parse_duration(duration)
    if not duration_seconds:
        return await ctx.send("❌ مدة غير صالحة! استخدم: 1s, 1m, 1h, 1d")
    
    end_time = datetime.now() + timedelta(seconds=duration_seconds)
    
    # بناء Embed
    embed = discord.Embed(
        title=f"🎉 سحب: {prize}",
        description=description or "تفاعل بـ 🎉 للمشاركة!",
        color=discord.Color.gold(),
        timestamp=end_time
    )
    
    embed.add_field(name="🏆 الفائزون", value=f"{winners}", inline=True)
    embed.add_field(name="⏰ ينتهي", value=f"<t:{int(end_time.timestamp())}:R>", inline=True)
    embed.add_field(name="📩 الدعوات المطلوبة", value=f"{invites}", inline=True)
    
    if image:
        embed.set_image(url=image)
    
    embed.set_footer(text=f"تم النشر بواسطة {ctx.author.display_name}")
    
    # إرسال رسالة السحب
    message = await channel.send(
        content="🎉 **سحب جديد!** تفاعل بـ 🎉 للمشاركة",
        embed=embed
    )
    
    # إضافة التفاعل
    await message.add_reaction("🎉")
    
    # حفظ السحب
    giveaway_data = {
        "message_id": message.id,
        "channel_id": channel.id,
        "prize": prize,
        "winners": winners,
        "end_time": end_time.timestamp(),
        "invites_required": invites,
        "guild_id": ctx.guild.id,
        "host_id": ctx.author.id
    }
    
    # حفظ في ملف JSON
    try:
        with open("giveaways.json", "r") as f:
            giveaways = json.load(f)
    except:
        giveaways = {}
    
    giveaways[str(message.id)] = giveaway_data
    
    with open("giveaways.json", "w") as f:
        json.dump(giveaways, f)
    
    await ctx.send(f"✅ تم بدء السحب في {channel.mention}!")
    
    # جدولة إنهاء السحب
    await asyncio.sleep(duration_seconds)
    await end_giveaway(message, giveaway_data)

async def end_giveaway(message, data):
    """إنهاء السحب واختيار الفائزين"""
    
    try:
        # جلب الرسالة المحدثة
        message = await message.channel.fetch_message(message.id)
    except:
        return
    
    # جلب المشاركين
    reaction = discord.utils.get(message.reactions, emoji="🎉")
    if not reaction:
        return await message.channel.send("❌ لا يوجد تفاعلات على السحب!")
    
    users = await reaction.users().flatten()
    participants = [user for user in users if not user.bot]
    
    # فلترة حسب الدعوات (إذا كان مطلوب)
    eligible = participants.copy()
    if data.get("invites_required", 0) > 0:
        # هنا يمكنك إضافة نظام الدعوات الخاص بك
        # مثال: eligible = [u for u in participants if get_invites(u) >= data["invites_required"]]
        pass
    
    if len(eligible) == 0:
        embed = discord.Embed(
            title=f"❌ انتهى السحب: {data['prize']}",
            description="لا يوجد مشاركون مؤهلون!",
            color=discord.Color.red()
        )
        return await message.edit(content="❌ **انتهى السحب بدون فائزين**", embed=embed)
    
    # اختيار الفائزين
    selected = random.sample(eligible, min(data["winners"], len(eligible)))
    
    # تحديث Embed
    embed = discord.Embed(
        title=f"🏆 انتهى السحب: {data['prize']}",
        description=f"الفائزون:\n" + "\n".join([f"<@{u.id}> 🎉" for u in selected]),
        color=discord.Color.green()
    )
    
    if data.get("image"):
        embed.set_image(url=data["image"])
    
    # إرسال النتيجة
    await message.edit(content="✅ **انتهى السحب!**", embed=embed)
    
    # إرسال إشعار للفائزين
    winners_mentions = " ".join([f"<@{u.id}>" for u in selected])
    await message.channel.send(
        content=f"🎉 **مبروك للفائزين!** {winners_mentions}\n"
                f"الجائزة: **{data['prize']}**\n"
                f"تواصل مع <@{data['host_id']}> للحصول على جائزتك!",
        embed=discord.Embed(
            title="🎊 ألف مبروك!",
            description=f"لقد فزت بـ **{data['prize']}**!",
            color=discord.Color.gold()
        )
    )
    
    # حذف السحب من الملف
    try:
        with open("giveaways.json", "r") as f:
            giveaways = json.load(f)
        if str(message.id) in giveaways:
            del giveaways[str(message.id)]
        with open("giveaways.json", "w") as f:
            json.dump(giveaways, f)
    except:
        pass

@bot.command()
@commands.is_owner()
async def reroll(ctx, message_id: int):
    """إعادة سحب الفائزين من سحب سابق"""
    
    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        return await ctx.send("❌ لم أجد الرسالة!")
    
    reaction = discord.utils.get(message.reactions, emoji="🎉")
    if not reaction:
        return await ctx.send("❌ لا يوجد تفاعلات على هذه الرسالة!")
    
    users = await reaction.users().flatten()
    participants = [user for user in users if not user.bot]
    
    if len(participants) == 0:
        return await ctx.send("❌ لا يوجد مشاركين!")
    
    # اختيار فائز واحد عشوائي
    winner = random.choice(participants)
    await ctx.send(f"🎉 الفائز الجديد هو: {winner.mention}")

@bot.command()
async def giveaway_info(ctx, message_id: int):
    """عرض معلومات عن سحب معين"""
    
    try:
        message = await ctx.channel.fetch_message(message_id)
    except:
        return await ctx.send("❌ لم أجد الرسالة!")
    
    # قراءة البيانات من الملف
    try:
        with open("giveaways.json", "r") as f:
            giveaways = json.load(f)
        
        data = giveaways.get(str(message_id))
        if not data:
            return await ctx.send("❌ هذا ليس سحباً مسجلاً!")
        
        embed = discord.Embed(
            title=f"📊 معلومات السحب",
            color=discord.Color.blue()
        )
        embed.add_field(name="🎁 الجائزة", value=data['prize'], inline=False)
        embed.add_field(name="🏆 الفائزون", value=data['winners'], inline=True)
        embed.add_field(name="📩 الدعوات المطلوبة", value=data.get('invites_required', 0), inline=True)
        embed.add_field(name="⏰ ينتهي", value=f"<t:{int(data['end_time'])}:R>", inline=True)
        embed.add_field(name="👤 الناشر", value=f"<@{data['host_id']}>", inline=True)
        
        await ctx.send(embed=embed)
        
    except:
        await ctx.send("❌ لا توجد بيانات لهذا السحب!")

@bot.command()
@commands.is_owner()
async def giveaways_list(ctx):
    """عرض جميع السحوبات النشطة"""
    
    try:
        with open("giveaways.json", "r") as f:
            giveaways = json.load(f)
        
        if not giveaways:
            return await ctx.send("❌ لا توجد سحوبات نشطة!")
        
        embed = discord.Embed(
            title="🎉 السحوبات النشطة",
            color=discord.Color.blue()
        )
        
        for message_id, data in giveaways.items():
            embed.add_field(
                name=f"🎁 {data['prize']}",
                value=f"ID: `{message_id}`\nالفائزون: {data['winners']}\nينتهي: <t:{int(data['end_time'])}:R>",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    except:
        await ctx.send("❌ لا توجد سحوبات نشطة!")

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
                        f"⚠️ {message.author.mention} استخدم `{word}` "
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
