import discord
from discord.ext import commands
import json
import os
import datetime
import re
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="slate ", intents=intents)

SOB_EMOJI = "😭"
DATA_FILE = "sob_scores.json"

# --------------------
# LOAD DATA
# --------------------

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        scores = json.load(f)
else:
    scores = {}

def save_scores():
    with open(DATA_FILE, "w") as f:
        json.dump(scores, f)

# --------------------
# DURATION PARSER
# --------------------

def parse_duration(text: str):
    text = text.lower().strip()

    match = re.match(r"(\d+)(s|m|h|d)", text)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "s":
        return datetime.timedelta(seconds=value)
    elif unit == "m":
        return datetime.timedelta(minutes=value)
    elif unit == "h":
        return datetime.timedelta(hours=value)
    elif unit == "d":
        return datetime.timedelta(days=value)

    return None

# --------------------
# EVENTS
# --------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_raw_reaction_add(payload):

    if str(payload.emoji) != SOB_EMOJI:
        return

    if payload.user_id == bot.user.id:
        return

    try:
        channel = bot.get_channel(payload.channel_id)
        if channel is None:
            channel = await bot.fetch_channel(payload.channel_id)

        message = await channel.fetch_message(payload.message_id)

        user_id = str(message.author.id)

        scores[user_id] = scores.get(user_id, 0) + 1
        save_scores()

    except Exception as e:
        print(f"Reaction error: {e}")

# IMPORTANT: allow commands to work
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if message.author.timed_out_until is not None:
        # still allow commands, but prevent message handling confusion
        pass

    await bot.process_commands(message)

# --------------------
# TOP SOBBERS (TOP 5)
# --------------------

@bot.command(name="topsobs")
async def topsobs(ctx):

    if not scores:
        await ctx.send("No 😭 reactions tracked yet.")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title="😭 Top Sobbers",
        color=0x5865F2
    )

    medals = ["🥇", "🥈", "🥉"]

    user_rank = None
    user_count = scores.get(str(ctx.author.id), 0)

    for rank, (user_id, count) in enumerate(sorted_scores, start=1):
        if user_id == str(ctx.author.id):
            user_rank = rank
            break

    # TOP 5 ONLY
    for rank, (user_id, count) in enumerate(sorted_scores[:5], start=1):

        member = ctx.guild.get_member(int(user_id))

        if member:
            name = member.display_name
        else:
            try:
                user = await bot.fetch_user(int(user_id))
                name = user.name
            except:
                name = f"User {user_id}"

        prefix = medals[rank - 1] if rank <= 3 else f"#{rank}"

        if user_id == str(ctx.author.id):
            name = f"⭐ {name} (You)"

        embed.add_field(
            name=f"{prefix} {name}",
            value=f"😭 {count} sobs",
            inline=False
        )

    if user_rank:
        embed.set_footer(text=f"Your Rank: #{user_rank} • 😭 {user_count} sobs")

    await ctx.send(embed=embed)

# --------------------
# MY SOBS
# --------------------

@bot.command(name="mysobs")
async def mysobs(ctx):

    count = scores.get(str(ctx.author.id), 0)

    embed = discord.Embed(
        title="😭 Your Sob Count",
        description=f"You have {count} sob reactions.",
        color=0x5865F2
    )

    embed.set_thumbnail(url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)

# --------------------
# SAY (ADMIN ONLY)
# --------------------

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)

@say.error
async def say_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Administrator only.", delete_after=5)

# --------------------
# SEAL SYSTEM (TIMEOUT MUTE)
# --------------------

@bot.command(name="seal")
@commands.has_permissions(administrator=True)
async def seal(ctx, member: discord.Member, duration: str = None):

    # TOGGLE OFF IF ALREADY MUTED
    if member.timed_out_until is not None:
        try:
            await member.timeout(None)
            await ctx.send(f"🔓 {member.mention} has been unsealed.")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission.")
        return

    # DEFAULT = 1 HOUR
    if duration is None:
        timeout_duration = datetime.timedelta(hours=1)
        label = "1h"
    else:
        parsed = parse_duration(duration)

        if parsed is None:
            await ctx.send("❌ Use format like 10m, 1h, 2d")
            return

        timeout_duration = parsed
        label = duration

    try:
        await member.timeout(timeout_duration, reason=f"Sealed by {ctx.author}")
        await ctx.send(f"🔒 {member.mention} sealed for `{label}`.")
    except discord.Forbidden:
        await ctx.send("❌ Missing permissions.")

@bot.command(name="unseal")
@commands.has_permissions(administrator=True)
async def unseal(ctx, member: discord.Member):

    try:
        await member.timeout(None)
        await ctx.send(f"🔓 {member.mention} unsealed.")
    except discord.Forbidden:
        await ctx.send("❌ Missing permissions.")

# --------------------
# RUN BOT
# --------------------

bot.run(TOKEN)
