import discord
from discord.ext import commands
from discord import app_commands
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
# DATA
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
# READY
# --------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Slash commands synced: {len(synced)}")
    except Exception as e:
        print(e)

# --------------------
# REACTION TRACKING
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

    except Exception as e:
        print(e)

# --------------------
# TOP SOBS (shared logic)
# --------------------

async def build_leaderboard(ctx):

    if not scores:
        return "No 😭 reactions tracked yet.", None

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="😭 Top Sobbers", color=0x5865F2)

    medals = ["🥇", "🥈", "🥉"]

    user_rank = None
    user_count = scores.get(str(ctx.user.id if isinstance(ctx, discord.Interaction) else ctx.author.id), 0)

    user_id_check = str(ctx.user.id if isinstance(ctx, discord.Interaction) else ctx.author.id)

    for rank, (uid, count) in enumerate(sorted_scores, start=1):
        if uid == user_id_check:
            user_rank = rank
            break

    for rank, (user_id, count) in enumerate(sorted_scores[:5], start=1):

        member = None

        if ctx.guild:
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

        if user_id == user_id_check:
            name = f"⭐ {name} (You)"

        embed.add_field(
            name=f"{prefix} {name}",
            value=f"😭 {count} sobs",
            inline=False
        )

    if user_rank:
        embed.set_footer(text=f"Your Rank: #{user_rank} • 😭 {user_count} sobs")

    return None, embed

# =====================================================
# PREFIX COMMANDS
# =====================================================

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):
    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)

@bot.command(name="topsobs")
async def topsobs(ctx):
    _, embed = await build_leaderboard(ctx)
    if embed:
        await ctx.send(embed=embed)
    else:
        await ctx.send("No data.")

@bot.command(name="mysobs")
async def mysobs(ctx):
    count = scores.get(str(ctx.author.id), 0)

    embed = discord.Embed(
        title="😭 Your Sob Count",
        description=f"You have {count} sob reactions.",
        color=0x5865F2
    )

    await ctx.send(embed=embed)

# SEAL PREFIX
@bot.command(name="seal")
@commands.has_permissions(administrator=True)
async def seal(ctx, member: discord.Member, duration: str = None):

    if member.timed_out_until is not None:
        await member.timeout(None)
        await ctx.send(f"🔓 {member.mention} unsealed.")
        return

    if duration is None:
        td = datetime.timedelta(hours=1)
        label = "1h"
    else:
        td = parse_duration(duration)
        if not td:
            await ctx.send("❌ Invalid format.")
            return
        label = duration

    await member.timeout(td, reason=f"Sealed by {ctx.author}")
    await ctx.send(f"🔒 {member.mention} sealed for {label}")

@bot.command(name="unseal")
@commands.has_permissions(administrator=True)
async def unseal(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔓 {member.mention} unsealed")

# =====================================================
# SLASH COMMANDS
# =====================================================

@bot.tree.command(name="say", description="Make the bot say something (admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def say_slash(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

@bot.tree.command(name="mysobs", description="Check your sob count")
async def mysobs_slash(interaction: discord.Interaction):
    count = scores.get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"😭 You have {count} sob reactions.")

@bot.tree.command(name="topsobs", description="Top sob leaderboard")
async def topsobs_slash(interaction: discord.Interaction):
    _, embed = await build_leaderboard(interaction)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="seal", description="Timeout a user (toggle + duration support)")
@app_commands.checks.has_permissions(administrator=True)
async def seal_slash(interaction: discord.Interaction, member: discord.Member, duration: str = None):

    if member.timed_out_until is not None:
        await member.timeout(None)
        await interaction.response.send_message(f"🔓 {member.mention} unsealed.")
        return

    if duration is None:
        td = datetime.timedelta(hours=1)
        label = "1h"
    else:
        td = parse_duration(duration)
        if not td:
            await interaction.response.send_message("❌ Invalid format (10m, 1h, 2d).")
            return
        label = duration

    await member.timeout(td, reason=f"Sealed by {interaction.user}")
    await interaction.response.send_message(f"🔒 {member.mention} sealed for {label}")

@bot.tree.command(name="unseal", description="Remove timeout from a user")
@app_commands.checks.has_permissions(administrator=True)
async def unseal_slash(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None)
    await interaction.response.send_message(f"🔓 {member.mention} unsealed.")

# --------------------
# RUN
# --------------------

bot.run(TOKEN)
