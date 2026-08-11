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

app = Flask("")


@app.route("/")
def home():
    return "🤖 Bot is alive and running!"


def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

    print(
        f"🌐 Web server running on port "
        f"{os.environ.get('PORT', 8080)}"
    )


# ==========================
# BOT SETUP
# ==========================

intents = discord.Intents.default()

intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# ==========================
# OWNER ID
# ==========================

bot.owner_id = 1454256976048558240


# ==========================
# SETTINGS
# ==========================

BAD_WORDS = [
    "rab",
    "omik",
    "o5tek"
]

LOG_CHANNEL_NAME = "logs"

# Warning system
warning_counts = {}
warn_reasons = {}

# Voice system
last_voice_channel = {}
manual_leave = set()


# ==========================
# AFK SETTINGS
# ==========================

AFK_CHANNEL_ID = 1444469687483371551
AFK_CATEGORY_ID = 1444469413888786593


# ==========================
# DISCORD INVITE REGEX
# ==========================

INVITE_REGEX = re.compile(
    r"(https?://)?(www\.)?"
    r"(discord\.gg|discord\.com/invite|discord\.app/invite)"
    r"/\S+",
    re.I
)


# ==========================
# READY
# ==========================

@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")
    print("✅ Bot is ready!")
    print(f"✅ Connected to {len(bot.guilds)} guilds")
    print(f"👑 Owner ID: {bot.owner_id}")
    print("😴 Self-Deafen AFK System: ON")


# ==========================
# HELLO COMMAND
# ==========================

@bot.command()
async def hello(ctx):

    await ctx.send(
        f"👋 Hello {ctx.author.mention}!"
    )


# ==========================
# WRITE COMMAND
# ==========================

@bot.command()
@commands.is_owner()
async def write(ctx, *, message):

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)


# ==========================
# VOICE JOIN
# ==========================

@bot.command()
@commands.is_owner()
async def join(ctx):

    if not ctx.author.voice:
        return await ctx.send(
            "❌ Join a voice channel first."
        )

    channel = ctx.author.voice.channel

    try:

        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)

        else:
            await channel.connect()

        last_voice_channel[ctx.guild.id] = channel

        await ctx.send(
            f"✅ Joined **{channel.name}**"
        )

    except Exception as e:

        await ctx.send(
            f"❌ Error: `{e}`"
        )


# ==========================
# VOICE LEAVE
# ==========================

@bot.command()
@commands.is_owner()
async def leave(ctx):

    if ctx.voice_client:

        manual_leave.add(ctx.guild.id)

        await ctx.voice_client.disconnect()

        await ctx.send(
            "👋 Left voice channel."
        )

    else:

        await ctx.send(
            "❌ I'm not in a voice channel."
        )


# ==========================
# VOICE STATE UPDATE
# ==========================

@bot.event
async def on_voice_state_update(
    member,
    before,
    after
):

    # ==========================
    # SELF DEAFEN → AFK
    # ==========================

    if not member.bot and after.channel is not None:

        # User just enabled Self Deafen
        if after.self_deaf and not before.self_deaf:

            afk_channel = member.guild.get_channel(
                AFK_CHANNEL_ID
            )

            if afk_channel is None:

                print(
                    "❌ AFK channel not found!"
                )

            else:

                # Check category
                if afk_channel.category_id != AFK_CATEGORY_ID:

                    print(
                        "⚠️ AFK channel is not inside "
                        "the configured category!"
                    )

                try:

                    await member.move_to(
                        afk_channel
                    )

                    print(
                        f"😴 {member} "
                        f"self-deafened → moved to AFK"
                    )

                except discord.Forbidden:

                    print(
                        "❌ Bot doesn't have "
                        "Move Members permission!"
                    )

                except Exception as e:

                    print(
                        f"❌ AFK move error: {e}"
                    )

    # ==========================
    # OLD BOT VOICE SYSTEM
    # ==========================

    # Ignore everyone except the bot
    if member.id != bot.user.id:
        return

    guild = member.guild

    # Bot joined/moved to a channel
    if after.channel:

        last_voice_channel[
            guild.id
        ] = after.channel

        return

    # Manual leave
    if guild.id in manual_leave:

        manual_leave.remove(
            guild.id
        )

        return

    # Bot was disconnected
    if (
        before.channel
        and guild.id in last_voice_channel
    ):

        await asyncio.sleep(2)

        try:

            if guild.voice_client is None:

                await last_voice_channel[
                    guild.id
                ].connect()

                print(
                    "🔄 Reconnected."
                )

        except Exception as e:

            print(
                f"❌ Reconnect error: {e}"
            )


# ==========================
# RESET WARNINGS
# ==========================

@bot.command()
@commands.is_owner()
async def reset_warnings(
    ctx,
    member: discord.Member
):

    warning_counts[member.id] = 0

    if member.id in warn_reasons:

        warn_reasons[member.id] = []

    await ctx.send(
        f"✅ Warnings reset for "
        f"{member.mention}."
    )


# ==========================
# CHECK WARNINGS
# ==========================

@bot.command()
@commands.is_owner()
async def check_warnings(
    ctx,
    member: discord.Member
):

    count = warning_counts.get(
        member.id,
        0
    )

    await ctx.send(
        f"{member.mention} has "
        f"**{count}/3** warnings."
    )


# ==========================
# ADD BAD WORD
# ==========================

@bot.command()
@commands.is_owner()
async def add_bad_word(
    ctx,
    word: str
):

    word = word.lower()

    if word not in BAD_WORDS:

        BAD_WORDS.append(word)

        await ctx.send(
            f"✅ Added `{word}`"
        )

    else:

        await ctx.send(
            f"⚠️ `{word}` is already in the list."
        )


# ==========================
# REMOVE BAD WORD
# ==========================

@bot.command()
@commands.is_owner()
async def remove_bad_word(
    ctx,
    word: str
):

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


# ==========================
# SHOW BAD WORDS
# ==========================

@bot.command()
@commands.is_owner()
async def show_bad_words(ctx):

    if not BAD_WORDS:

        return await ctx.send(
            "No bad words."
        )

    await ctx.send(
        "\n".join(
            f"• `{word}`"
            for word in BAD_WORDS
        )
    )


# ==========================
# AVATAR
# ==========================

@bot.command()
async def avatar(
    ctx,
    member: discord.Member = None
):

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
        text=f"Requested by "
             f"{ctx.author.display_name}"
    )

    await ctx.send(
        embed=embed
    )


# ==========================
# CLEAR
# ==========================

@bot.command()
@commands.is_owner()
async def clear(
    ctx,
    amount: int
):

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
        f"✅ Deleted "
        f"{len(deleted) - 1} messages.",
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

    # Increase warning count
    warning_counts[member.id] = (
        warning_counts.get(
            member.id,
            0
        ) + 1
    )

    # Save warning reason
    if member.id not in warn_reasons:

        warn_reasons[
            member.id
        ] = []

    warn_reasons[
        member.id
    ].append(
        {
            "reason": reason,
            "by": ctx.author.id,
            "time": ctx.message.created_at.strftime(
                "%Y-%m-%d %H:%M"
            )
        }
    )

    # DM member
    try:

        await member.send(
            f"⚠️ You have been warned in "
            f"**{ctx.guild.name}**\n"
            f"Reason: {reason}\n"
            f"Warnings: "
            f"{warning_counts[member.id]}/3"
        )

    except:
        pass

    # Warning embed
    embed = discord.Embed(
        title="⚠️ Warning",
        description=(
            f"{member.mention} "
            f"has been warned!"
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
        value=(
            f"{warning_counts[member.id]}/3"
        ),
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
    if warning_counts[member.id] >= 3:

        try:

            await member.timeout(
                timedelta(minutes=10),
                reason="3 warnings"
            )

            await ctx.send(
                f"🔇 {member.mention} "
                f"has been timed out for "
                f"10 minutes "
                f"(3 warnings)."
            )

        except discord.Forbidden:

            await ctx.send(
                "❌ I don't have permission "
                "to timeout this member."
            )

        warning_counts[
            member.id
        ] = 0


# ==========================
# WARNINGS
# ==========================

@bot.command()
@commands.is_owner()
async def warnings_command(
    ctx,
    member: discord.Member
):

    count = warning_counts.get(
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
            value=reasons_text[:1024],
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
async def clear_all(
    ctx,
    amount: int
):

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
        f"✅ Deleted "
        f"{len(deleted) - 1} messages.",
        delete_after=3
    )


# ==========================
# MESSAGE FILTER
# ==========================

@bot.event
async def on_message(message):

    # Ignore bots
    if message.author.bot:
        return

    # DMs
    if not message.guild:

        await bot.process_commands(
            message
        )

        return

    # Ignore administrators
    if not message.author.guild_permissions.administrator:

        content = message.content.lower()

        # ==========================
        # DISCORD INVITE
        # ==========================

        if INVITE_REGEX.search(content):

            try:

                await message.delete()

                await message.author.timeout(
                    timedelta(minutes=1),
                    reason="Discord Invite"
                )

            except discord.Forbidden:

                print(
                    "❌ Missing permissions "
                    "for invite filter."
                )

            return

        # ==========================
        # BAD WORDS
        # ==========================

        for word in BAD_WORDS:

            if word in content:

                try:

                    await message.delete()

                except discord.Forbidden:

                    print(
                        "❌ Cannot delete message."
                    )

                    return

                # Add warning
                warning_counts[
                    message.author.id
                ] = (
                    warning_counts.get(
                        message.author.id,
                        0
                    ) + 1
                )

                # Logs channel
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
                        f"{warning_counts[message.author.id]}"
                        f"/3)"
                    )

                # 3 warnings
                if warning_counts[
                    message.author.id
                ] >= 3:

                    try:

                        await message.author.timeout(
                            timedelta(minutes=10),
                            reason="3 Bad Words"
                        )

                    except discord.Forbidden:

                        print(
                            "❌ Cannot timeout member."
                        )

                    warning_counts[
                        message.author.id
                    ] = 0

                return

    # Commands
    await bot.process_commands(
        message
    )


# ==========================
# RUN BOT
# ==========================

TOKEN = os.getenv(
    "DISCORD_TOKEN"
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
