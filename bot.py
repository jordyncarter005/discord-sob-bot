import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv

# Load token
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="slate ", intents=intents)

SOB_EMOJI = "😭"
DATA_FILE = "sob_scores.json"
SEALED_USERS_FILE = "sealed_users.json"

# --------------------
# LOAD DATA
# --------------------

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        scores = json.load(f)
else:
    scores = {}

if os.path.exists(SEALED_USERS_FILE):
    with open(SEALED_USERS_FILE, "r") as f:
        sealed_users = json.load(f)
else:
    sealed_users = []

def save_scores():
    with open(DATA_FILE, "w") as f:
        json.dump(scores, f)

def save_sealed_users():
    with open(SEALED_USERS_FILE, "w") as f:
        json.dump(sealed_users, f)

# --------------------
# EVENTS
# --------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

# Delete messages from sealed users
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    if str(message.author.id) in sealed_users:
        try:
            await message.delete()
            return
        except discord.Forbidden:
            pass

    await bot.process_commands(message)

# Track 😭 reactions
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

# --------------------
# COMMANDS
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
# SAY COMMAND (ADMIN ONLY)
# --------------------

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    await ctx.send(message)

@say.error
async def say_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        try:
            await ctx.message.delete()
        except:
            pass

        await ctx.send("❌ Administrator only.", delete_after=5)

# --------------------
# SEAL COMMAND
# --------------------

@bot.command(name="seal")
@commands.has_permissions(administrator=True)
async def seal(ctx, member: discord.Member):

    user_id = str(member.id)

    if user_id in sealed_users:
        sealed_users.remove(user_id)
        save_sealed_users()
        await ctx.send(f"🔓 {member.mention} unsealed.")
    else:
        sealed_users.append(user_id)
        save_sealed_users()
        await ctx.send(f"🔒 {member.mention} sealed (messages will be deleted).")

@seal.error
async def seal_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Administrator only.")

    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ User not found.")

# --------------------
# RUN BOT
# --------------------

bot.run(TOKEN)
