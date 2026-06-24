import discord
from discord.ext import commands
import json
import os
import datetime
import re
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

# 🔐 PUT YOUR DISCORD USER ID HERE
OWNER_ID = 926720419002732575

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="slate ", intents=intents)

SOB_EMOJI = "😭"

DATA_FILE = "sob_scores.json"

# --------------------
# DATA LOAD
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
# OWNER CHECKS
# --------------------

def is_owner(user_id: int):
    return user_id == OWNER_ID

async def owner_only_ctx(ctx):
    if ctx.author.id != OWNER_ID:
        await ctx.send("🚫 Only the bot owner can use this bot.")
        return True
    return False

def owner_only_interaction(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return False
    return True

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
# READY
# --------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()
    print("Slash commands synced")

# --------------------
# REACTIONS
# --------------------

@bot.event
async def on_raw_reaction_add(payload):

    if str(payload.emoji) != SOB_EMOJI:
        return

    if payload.user_id == bot.user.id:
        return

    try:
        channel = bot.get_channel(payload.channel_id) or await bot.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        user_id = str(message.author.id)
        scores[user_id] = scores.get(user_id, 0) + 1
        save_scores()

    except:
        pass

# --------------------
# TOP SOBS
# --------------------

@bot.command(name="topsobs")
async def topsobs(ctx):

    if await owner_only_ctx(ctx):
        return

    if not scores:
        return await ctx.send("No data.")

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="😭 Top Sobbers", color=0x5865F2)

    user_id_check = str(ctx.author.id)
    user_rank = None
    user_count = scores.get(user_id_check, 0)

    for rank, (uid, _) in enumerate(sorted_scores, start=1):
        if uid == user_id_check:
            user_rank = rank
            break

    for rank, (user_id, count) in enumerate(sorted_scores[:5], start=1):

        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"

        if user_id == user_id_check:
            name = f"⭐ {name} (You)"

        embed.add_field(
            name=f"#{rank} {name}",
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

    if await owner_only_ctx(ctx):
        return

    count = scores.get(str(ctx.author.id), 0)
    await ctx.send(f"😭 You have {count} sob reactions.")

# --------------------
# SAY
# --------------------

@bot.command(name="say")
async def say(ctx, *, message):

    if await owner_only_ctx(ctx):
        return

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)

# --------------------
# SEAL (TIMEOUT SYSTEM)
# --------------------

@bot.command(name="seal")
async def seal(ctx, member: discord.Member, duration: str = None):

    if await owner_only_ctx(ctx):
        return

    if member.timed_out_until is not None:
        await member.timeout(None)
        return await ctx.send(f"🔓 {member.mention} unsealed.")

    if duration is None:
        td = datetime.timedelta(hours=1)
        label = "1h"
    else:
        td = parse_duration(duration)
        if not td:
            return await ctx.send("❌ Invalid format.")
        label = duration

    try:
        await member.timeout(td, reason=f"Sealed by owner")
        await ctx.send(f"🔒 {member.mention} sealed for {label}")
    except:
        await ctx.send("❌ Missing permissions.")

# --------------------
# UNSEAL
# --------------------

@bot.command(name="unseal")
async def unseal(ctx, member: discord.Member):

    if await owner_only_ctx(ctx):
        return

    await member.timeout(None)
    await ctx.send(f"🔓 {member.mention} unsealed.")

# --------------------
# SLASH COMMANDS (OWNER ONLY)
# --------------------

@bot.tree.command(name="mysobs")
async def mysobs_slash(interaction: discord.Interaction):

    if not owner_only_interaction(interaction):
        return await interaction.response.send_message("🚫 Owner only.", ephemeral=True)

    count = scores.get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"😭 {count} sobs")

@bot.tree.command(name="say")
async def say_slash(interaction: discord.Interaction, message: str):

    if not owner_only_interaction(interaction):
        return await interaction.response.send_message("🚫 Owner only.", ephemeral=True)

    await interaction.response.send_message(message)

@bot.tree.command(name="disable")
async def disable_slash(interaction: discord.Interaction):

    if not owner_only_interaction(interaction):
        return await interaction.response.send_message("🚫 Owner only.", ephemeral=True)

    await interaction.response.send_message("🚫 Disabled (you can extend logic here).")

# --------------------
# RUN
# --------------------

bot.run(TOKEN)
