import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import re
from dotenv import load_dotenv

bot = commands.Bot(command_prefix="slate ", intents=intents)

bot.remove_command("help")

SOB_EMOJI = "😭"
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="slate ", intents=intents)

SOB_EMOJI = "😭"

DATA_FILE = "sob_scores.json"
LOCK_FILE = "bot_lock.json"

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
# BOT LOCK SYSTEM
# --------------------

if os.path.exists(LOCK_FILE):
    with open(LOCK_FILE, "r") as f:
        bot_locked = json.load(f).get("locked", False)
else:
    bot_locked = False

def save_lock():
    with open(LOCK_FILE, "w") as f:
        json.dump({"locked": bot_locked}, f)

def is_locked():
    return bot_locked

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
# MESSAGE HANDLER (NEW GIF SYSTEM ADDED HERE)
# --------------------

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    content = message.content.lower()

    # 🎬 GIF TRIGGERS
    for phrase, gif in TRIGGERS.items():
        if phrase in content:
            await message.channel.send(gif)
            break

    await bot.process_commands(message)

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

    except:
        pass

# --------------------
# PREFIX COMMAND GUARD
# --------------------

async def lock_check_ctx(ctx):
    if is_locked():
        await ctx.send("🚫 Bot commands are currently disabled.")
        return True
    return False

# --------------------
# TOP SOBS
# --------------------

@bot.command(name="topsobs")
async def topsobs(ctx):

    if await lock_check_ctx(ctx):
        return

    if not scores:
        return await ctx.send("No 😭 reactions tracked yet.")

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="😭 Top Sobbers", color=0x5865F2)

    medals = ["🥇", "🥈", "🥉"]

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

        prefix = medals[rank - 1] if rank <= 3 else f"#{rank}"

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

    if await lock_check_ctx(ctx):
        return

    count = scores.get(str(ctx.author.id), 0)

    await ctx.send(f"😭 You have {count} sob reactions.")

# --------------------
# SAY
# --------------------

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):

    if await lock_check_ctx(ctx):
        return

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)

# --------------------
# SEAL SYSTEM
# --------------------

@bot.command(name="seal")
@commands.has_permissions(administrator=True)
async def seal(ctx, member: discord.Member, duration: str = None):

    if await lock_check_ctx(ctx):
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
            return await ctx.send("❌ Invalid format (10m, 1h, 2d).")
        label = duration

    try:
        await member.timeout(td, reason=f"Sealed by {ctx.author}")
        await ctx.send(f"🔒 {member.mention} sealed for {label}")
    except:
        await ctx.send("❌ Missing permissions.")

@bot.command(name="unseal")
@commands.has_permissions(administrator=True)
async def unseal(ctx, member: discord.Member):

    if await lock_check_ctx(ctx):
        return

    await member.timeout(None)
    await ctx.send(f"🔓 {member.mention} unsealed.")

# --------------------
# BOT LOCK COMMANDS
# --------------------

@bot.command(name="disable")
@commands.has_permissions(administrator=True)
async def disable(ctx):

    global bot_locked
    bot_locked = True
    save_lock()

    await ctx.send("🚫 Bot commands disabled.")

@bot.command(name="enable")
@commands.has_permissions(administrator=True)
async def enable(ctx):

    global bot_locked
    bot_locked = False
    save_lock()

    await ctx.send("✅ Bot commands enabled.")

# --------------------
# SLASH COMMANDS
# --------------------

@bot.tree.command(name="mysobs")
async def mysobs_slash(interaction: discord.Interaction):

    if is_locked():
        return await interaction.response.send_message("🚫 Disabled", ephemeral=True)

    count = scores.get(str(interaction.user.id), 0)
    await interaction.response.send_message(f"😭 {count} sobs")

@bot.tree.command(name="topsobs")
async def topsobs_slash(interaction: discord.Interaction):

    if is_locked():
        return await interaction.response.send_message("🚫 Disabled", ephemeral=True)

    await interaction.response.send_message("Use prefix version for now (or I can upgrade this).")

@bot.tree.command(name="disable")
@app_commands.checks.has_permissions(administrator=True)
async def disable_slash(interaction: discord.Interaction):

    global bot_locked
    bot_locked = True
    save_lock()

    await interaction.response.send_message("🚫 Disabled")

@bot.tree.command(name="enable")
@app_commands.checks.has_permissions(administrator=True)
async def enable_slash(interaction: discord.Interaction):

    global bot_locked
    bot_locked = False
    save_lock()

    await interaction.response.send_message("✅ Enabled")
# --------------------
# HELP COMMAND
# --------------------

@bot.command(name="help")
async def help_command(ctx):

    embed = discord.Embed(
        title="📖 Slate Bot Commands",
        description="Available commands for the bot.",
        color=0x5865F2
    )

    embed.add_field(
        name="😭 Sob Commands",
        value=(
            "`slate mysobs` - View your sob count\n"
            "`slate topsobs` - View the leaderboard"
        ),
        inline=False
    )

    embed.add_field(
        name="🛠️ Admin Commands",
        value=(
            "`slate say <message>` - Make the bot send a message\n"
            "`slate seal @user [time]` - Timeout a user\n"
            "`slate unseal @user` - Remove timeout\n"
            "`slate disable` - Disable bot commands\n"
            "`slate enable` - Enable bot commands"
        ),
        inline=False
    )

    embed.add_field(
        name="⏱️ Seal Duration Examples",
        value=(
            "`10m` = 10 minutes\n"
            "`1h` = 1 hour\n"
            "`2d` = 2 days"
        ),
        inline=False
    )

    embed.add_field(
        name="Slash Commands",
        value=(
            "`/mysobs`\n"
            "`/topsobs`\n"
            "`/disable`\n"
            "`/enable`"
        ),
        inline=False
    )

    embed.set_footer(text="Prefix: slate ")

    await ctx.send(embed=embed) 
# --------------------
# RUN BOT
# --------------------

bot.run(TOKEN)
