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
warn_reasons = {}

# ==========================
# AFK SETTINGS
# ==========================
AFK_CHANNEL_ID = 1444469687483371551
AFK_CATEGORY_ID = 1444469413888786593

# 20 minutes
DEAFEN_TIME = 20 * 60

# Store active deafen timers
deafen_timers = {}


# ==========================
# DISCORD INVITE REGEX
# ==========================
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
    print("😴 Self Deafen AFK System: ON")


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

    # ==================================================
    # SELF DEAFEN → DM IMMEDIATELY → 20 MIN → AFK
    # ==================================================

    if not member.bot:

        # --------------------------
        # USER STARTED SELF DEAFEN
        # --------------------------
        if after.self_deaf and not before.self_deaf:

            # Send DM immediately
            try:
                await member.send(
                    f"🔇 You have been deafened in "
                    f"**{member.guild.name}**. "
                    f"You will be moved to AFK after "
                    f"20 minutes of being deaf."
                )

                print(
                    f"📩 Sent deafen DM to {member}"
                )

            except discord.Forbidden:
                print(
                    f"❌ Cannot send DM to {member}"
                )

            except Exception as e:
                print(
                    f"❌ DM error: {e}"
                )

            # Cancel old timer if exists
            old_task = deafen_timers.get(member.id)

            if old_task:
                old_task.cancel()

            # --------------------------
            # 20 MINUTE TIMER
            # --------------------------
            async def deaf_timer():

                try:

                    # Wait 20 minutes
                    await asyncio.sleep(DEAFEN_TIME)

                    guild = member.guild

                    # Get current member
                    current_member = guild.get_member(
                        member.id
                    )

                    if not current_member:
                        return

                    # Check if still in voice
                    if not current_member.voice:
                        return

                    # Check if STILL self deafened
                    if not current_member.voice.self_deaf:
                        return

                    # Get AFK channel
                    afk_channel = guild.get_channel(
                        AFK_CHANNEL_ID
                    )

                    if not afk_channel:
                        print(
                            "❌ AFK channel not found!"
                        )
                        return

                    # Check category
                    if afk_channel.category_id != AFK_CATEGORY_ID:
                        print(
                            "⚠️ AFK channel is not inside "
                            "the configured category!"
                        )

                    # Move member to AFK
                    try:

                        await current_member.move_to(
                            afk_channel
                        )

                        print(
                            f"😴 {current_member} "
                            f"was self deafened for 20 minute   "
                            f"→ moved to AFK"
                        )

                    except discord.Forbidden:

                        print(
                            "❌ Bot doesn't have "
                            "Move Members permission!"
                        )

                    except Exception as e:

                        print(
                            f"❌ Move error: {e}"
                        )

                except asyncio.CancelledError:

                    # User removed deafen
                    print(
                        f"🔊 {member} removed self deafen "
                        f"→ timer cancelled"
                    )

                except Exception as e:

                    print(
                        f"❌ Deafen timer error: {e}"
                    )

                finally:

                    deafen_timers.pop(
                        member.id,
                        None
                    )

            # Start timer
            deafen_timers[member.id] = (
                asyncio.create_task(
                    deaf_timer()
                )
            )

        # --------------------------
        # USER REMOVED SELF DEAFEN
        # --------------------------
        elif before.self_deaf and not after.self_deaf:

            task = deafen_timers.get(
                member.id
            )

            if task:

                task.cancel()

                deafen_timers.pop(
                    member.id,
                    None
                )

                print(
                    f"🔊 {member} removed self deafen "
                    f"→ AFK timer cancelled"
                )

    # ==================================================
    # YOUR OLD BOT VOICE SYSTEM
    # ==================================================

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

                await last_voice_channel[
                    guild.id
                ].connect()

                print("🔄 Reconnected.")

        except Exception as e:

            print(
                f"❌ Reconnect error: {e}"
            )


# ==========================
# WARNINGS
# ==========================
@bot.command()
@commands.is_owner()
async def reset_warnings(ctx, member: discord.Member):

    warnings[member.id] = 0

    if member.id in warn_reasons:
        warn_reasons[member.id] = []

    await ctx.send(
        f"✅ Warnings reset for {member.mention}."
    )


@bot.command()
@commands.is_owner()
async def check_warnings(ctx, member: discord.Member):

    await ctx.send(
        f"{member.mention} has "
        f"**{warnings.get(member.id, 0)}/3** warnings."
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

    await ctx.send(
        f"✅ Added `{word}`"
    )


@bot.command()
@commands.is_owner()
async def remove_bad_word(ctx, word: str):

    word = word.lower()

    if word in BAD_WORDS:
        BAD_WORDS.remove(word)
        await ctx.send(
            f"✅ Removed `{word}`"
        )
    else:
        await ctx.send(
            "❌ Word not found."
        )


@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):

    if not BAD_WORDS:
        return await ctx.send(
            "No bad words."
        )

    await ctx.send(
        "\n".join(BAD_WORDS)
    )


# ==========================
# AVATAR
# ==========================
@bot.command()
async def avatar(ctx, member: discord.Member = None):

    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title=f"🖼️ {member.display_name}'s Avatar",
        color=discord.Color.blue()
    )

    embed.set_image(
        url=member.display_avatar.url
    )

    embed.set_footer(
        text=f"Requested by {ctx.author.display_name}"
    )

    await ctx.send(
        embed=embed
    )


# ==========================
# CLEAR
# ==========================
@bot.command()
@commands.is_owner()
async def clear(ctx, amount: int):

    if amount < 1:
        return await ctx.send(
            "❌ Please specify a number greater than 0."
        )

    if amount > 100:
        return await ctx.send(
            "❌ Cannot delete more than 100 messages at once."
        )

    deleted = await ctx.channel.purge(
        limit=amount + 1
    )

    await ctx.send(
        f"✅ Deleted {len(deleted) - 1} messages.",
        delete_after=3
    )


# ==========================
# WARN
# ==========================
@bot.command()
@commands.is_owner()
async def warn(
    ctx,
    member: discord.Member,
    *,
    reason: str = "No reason provided"
):

    warnings[member.id] = (
        warnings.get(member.id, 0) + 1
    )

    if member.id not in warn_reasons:
        warn_reasons[member.id] = []

    warn_reasons[member.id].append({
        "reason": reason,
        "by": ctx.author.id,
        "time": ctx.message.created_at.strftime(
            "%Y-%m-%d %H:%M"
        )
    })

    # DM warning
    try:

        await member.send(
            f"⚠️ You have been warned in "
            f"**{ctx.guild.name}**\n"
            f"Reason: {reason}\n"
            f"Warnings: "
            f"{warnings[member.id]}/3"
        )

    except:
        pass

    # Warning embed
    embed = discord.Embed(
        title="⚠️ Warning",
        description=(
            f"{member.mention} has been warned!"
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Reason",
        value=reason,
        inline=False
    )

    embed.add_field(
        name="Warnings",
        value=f"{warnings[member.id]}/3",
        inline=True
    )

    embed.add_field(
        name="Moderator",
        value=ctx.author.mention,
        inline=True
    )

    embed.set_footer(
        text=f"ID: {member.id}"
    )

    await ctx.send(
        embed=embed
    )

    # 3 warnings → timeout
    if warnings[member.id] >= 3:

        await member.timeout(
            timedelta(minutes=10),
            reason="3 warnings"
        )

        await ctx.send(
            f"🔇 {member.mention} has been "
            f"timed out for 10 minutes "
            f"(3 warnings)."
        )

        warnings[member.id] = 0


# ==========================
# WARNINGS LIST
# ==========================
@bot.command()
@commands.is_owner()
async def warnings_command(
    ctx,
    member: discord.Member
):

    count = warnings.get(
        member.id,
        0
    )

    embed = discord.Embed(
        title=f"⚠️ Warnings for "
              f"{member.display_name}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Total Warnings",
        value=f"{count}/3",
        inline=False
    )

    if (
        member.id in warn_reasons
        and warn_reasons[member.id]
    ):

        reasons_text = ""

        for i, warn_data in enumerate(
            warn_reasons[member.id],
            1
        ):

            reasons_text += (
                f"**{i}.** "
                f"{warn_data['reason']} "
                f"(by <@{warn_data['by']}> "
                f"at {warn_data['time']})\n"
            )

        embed.add_field(
            name="Reasons",
            value=reasons_text,
            inline=False
        )

    else:

        embed.add_field(
            name="Reasons",
            value="No warnings recorded.",
            inline=False
        )

    embed.set_footer(
        text=f"ID: {member.id}"
    )

    await ctx.send(
        embed=embed
    )


# ==========================
# CLEAR ALL
# ==========================
@bot.command()
@commands.is_owner()
async def clear_all(ctx, amount: int):

    if amount < 1:
        return await ctx.send(
            "❌ Please specify a number greater than 0."
        )

    if amount > 100:
        return await ctx.send(
            "❌ Cannot delete more than 100 messages at once."
        )

    deleted = await ctx.channel.purge(
        limit=amount
    )

    await ctx.send(
        f"✅ Deleted {len(deleted)} messages.",
        delete_after=3
    )


# ==========================
# MESSAGE FILTER
# ==========================
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if not message.guild:
        return await bot.process_commands(
            message
        )

    if not message.author.guild_permissions.administrator:

        content = message.content.lower()

        # Discord Invite
        if INVITE_REGEX.search(content):

            await message.delete()

            await message.author.timeout(
                timedelta(minutes=1),
                reason="Discord Invite"
            )

            return

        # Bad Words
        for word in BAD_WORDS:

            if word in content:

                await message.delete()

                warnings[
                    message.author.id
                ] = (
                    warnings.get(
                        message.author.id,
                        0
                    ) + 1
                )

                log = discord.utils.get(
                    message.guild.text_channels,
                    name=LOG_CHANNEL_NAME
                )

                if log:

                    await log.send(
                        f"⚠️ "
                        f"{message.author.mention} "
                        f"used `{word}` "
                        f"("
                        f"{warnings[message.author.id]}"
                        f"/3)"
                    )

                if warnings[
                    message.author.id
                ] >= 3:

                    await message.author.timeout(
                        timedelta(minutes=10),
                        reason="3 Bad Words"
                    )

                    warnings[
                        message.author.id
                    ] = 0

                return

    await bot.process_commands(
        message
    )


# ==========================
# RUN BOT
# ==========================
TOKEN = os.getenv(
    'DISCORD_TOKEN'
)

if TOKEN is None:

    print(
        "❌ Error: DISCORD_TOKEN not found!"
    )

    sys.exit(1)


print("🚀 Starting bot...")

keep_alive()

print("🤖 Bot is starting...")

try:

    bot.run(TOKEN)

except Exception as e:

    print(
        f"❌ Bot error: {e}"
    )

    sys.exit(1)
