import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

import sqlite3
import datetime
import asyncio
import logging
import os
import re

# ==================================================

# CONFIG

# ==================================================

load_dotenv()

TOKEN = os.getenv("TOKEN")

SOB_EMOJI = "😭"
DATABASE_NAME = "slate.db"

# Minimum sobs required in a day

# to continue a streak

STREAK_REQUIREMENT = 5

# ==================================================

# LOGGING

# ==================================================

logging.basicConfig(
level=logging.INFO,
format="[%(asctime)s] %(levelname)s: %(message)s"
)

# ==================================================

# INTENTS

# ==================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(
command_prefix="slate ",
intents=intents,
help_command=None
)

# ==================================================

# DATABASE

# ==================================================

db = sqlite3.connect(
DATABASE_NAME,
check_same_thread=False
)

db.row_factory = sqlite3.Row

cursor = db.cursor()

# ==================================================

# TABLES

# ==================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id TEXT PRIMARY KEY,
sobs INTEGER DEFAULT 0,
current_streak INTEGER DEFAULT 0,
best_streak INTEGER DEFAULT 0,
last_streak_update TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS daily_sobs(
user_id TEXT,
date TEXT,
sobs INTEGER DEFAULT 0,
PRIMARY KEY(user_id, date)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings(
key TEXT PRIMARY KEY,
value TEXT
)
""")

db.commit()

# ==================================================

# BOT LOCK

# ==================================================

bot_locked = False

# ==================================================

# DATE HELPERS

# ==================================================

def today_string():
return datetime.date.today().isoformat()

def yesterday_string():
return (
datetime.date.today()
- datetime.timedelta(days=1)
).isoformat()

# ==================================================

# USER HELPERS

# ==================================================

def ensure_user(user_id: int):

```
cursor.execute(
    """
    SELECT *
    FROM users
    WHERE user_id = ?
    """,
    (str(user_id),)
)

result = cursor.fetchone()

if result:
    return

cursor.execute(
    """
    INSERT INTO users(
        user_id,
        sobs,
        current_streak,
        best_streak
    )
    VALUES (?,0,0,0)
    """,
    (str(user_id),)
)

db.commit()
```

def get_total_sobs(user_id: int):

```
ensure_user(user_id)

cursor.execute(
    """
    SELECT sobs
    FROM users
    WHERE user_id = ?
    """,
    (str(user_id),)
)

row = cursor.fetchone()

return row["sobs"]
```

# ==================================================

# DAILY SOB HELPERS

# ==================================================

def add_daily_sob(user_id: int):

```
ensure_user(user_id)

today = today_string()

cursor.execute(
    """
    INSERT INTO daily_sobs(
        user_id,
        date,
        sobs
    )
    VALUES (?, ?, 1)

    ON CONFLICT(user_id, date)
    DO UPDATE SET
    sobs = sobs + 1
    """,
    (str(user_id), today)
)

db.commit()
```

def get_daily_sobs(
user_id: int,
date: str = None
):

```
if date is None:
    date = today_string()

cursor.execute(
    """
    SELECT sobs
    FROM daily_sobs
    WHERE user_id = ?
    AND date = ?
    """,
    (str(user_id), date)
)

row = cursor.fetchone()

if row:
    return row["sobs"]

return 0
```

# ==================================================

# SOB ADDER

# ==================================================

def add_sob(user_id: int):

```
ensure_user(user_id)

cursor.execute(
    """
    UPDATE users
    SET sobs = sobs + 1
    WHERE user_id = ?
    """,
    (str(user_id),)
)

add_daily_sob(user_id)

db.commit()
```

# ==================================================

# STREAK SYSTEM

# ==================================================

def update_streaks():

```
yesterday = yesterday_string()

cursor.execute(
    """
    SELECT DISTINCT user_id
    FROM daily_sobs
    """
)

users = cursor.fetchall()

for row in users:

    user_id = row["user_id"]

    count = get_daily_sobs(
        int(user_id),
        yesterday
    )

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    user = cursor.fetchone()

    if not user:
        continue

    current = user["current_streak"]
    best = user["best_streak"]

    if count >= STREAK_REQUIREMENT:

        current += 1

        if current > best:
            best = current

    else:

        current = 0

    cursor.execute(
        """
        UPDATE users
        SET
            current_streak = ?,
            best_streak = ?,
            last_streak_update = ?
        WHERE user_id = ?
        """,
        (
            current,
            best,
            yesterday,
            user_id
        )
    )

db.commit()
```

# ==================================================

# CHAMPION CHANNEL

# ==================================================

def set_champion_channel(
channel_id: int
):

```
cursor.execute(
    """
    INSERT OR REPLACE
    INTO settings(key,value)
    VALUES(
        'champion_channel',
        ?
    )
    """,
    (str(channel_id),)
)

db.commit()
```

def get_champion_channel():

```
cursor.execute(
    """
    SELECT value
    FROM settings
    WHERE key =
    'champion_channel'
    """
)

row = cursor.fetchone()

if row:
    return int(row["value"])

return None
```

# ==================================================

# LOCK HELPERS

# ==================================================

def is_locked():
return bot_locked

async def lock_check_ctx(ctx):

```
if is_locked():

    await ctx.send(
        "🚫 Bot commands are disabled."
    )

    return True

return False
```
# ==================================================
# REACTION DUPLICATE PROTECTION
# ==================================================

processed_reactions = set()

# ==================================================
# DAILY CHAMPION
# ==================================================

async def post_daily_champion():

    channel_id = get_champion_channel()

    if not channel_id:
        return

    channel = bot.get_channel(channel_id)

    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logging.error(
                f"Champion channel error: {e}"
            )
            return

    yesterday = yesterday_string()

    cursor.execute(
        """
        SELECT user_id, sobs
        FROM daily_sobs
        WHERE date = ?
        ORDER BY sobs DESC
        LIMIT 3
        """,
        (yesterday,)
    )

    winners = cursor.fetchall()

    if not winners:
        return

    embed = discord.Embed(
        title="🏆 Daily Sob Champion",
        description=f"Results for {yesterday}",
        color=0xFFD700
    )

    medals = ["🥇", "🥈", "🥉"]

    for i, row in enumerate(winners):

        user = await bot.fetch_user(
            int(row["user_id"])
        )

        embed.add_field(
            name=f"{medals[i]} {user.name}",
            value=f"😭 {row['sobs']} sobs",
            inline=False
        )

    await channel.send(embed=embed)

# ==================================================
# MIDNIGHT LOOP
# ==================================================

async def midnight_loop():

    await bot.wait_until_ready()

    while not bot.is_closed():

        now = datetime.datetime.now()

        tomorrow = (
            now + datetime.timedelta(days=1)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0
        )

        seconds = (
            tomorrow - now
        ).total_seconds()

        await asyncio.sleep(seconds)

        try:

            update_streaks()

            await post_daily_champion()

        except Exception as e:

            logging.error(
                f"Midnight task error: {e}"
            )

# ==================================================
# REACTION TRACKING
# ==================================================

@bot.event
async def on_raw_reaction_add(payload):

    try:

        if str(payload.emoji) != SOB_EMOJI:
            return

        if payload.user_id == bot.user.id:
            return

        key = (
            payload.message_id,
            payload.user_id
        )

        if key in processed_reactions:
            return

        processed_reactions.add(key)

        channel = (
            bot.get_channel(payload.channel_id)
            or await bot.fetch_channel(
                payload.channel_id
            )
        )

        message = await channel.fetch_message(
            payload.message_id
        )

        if message.author.bot:
            return

        add_sob(message.author.id)

    except Exception as e:

        logging.error(
            f"Reaction add error: {e}"
        )

# ==================================================
# OPTIONAL REACTION REMOVE
# ==================================================

@bot.event
async def on_raw_reaction_remove(payload):

    try:

        key = (
            payload.message_id,
            payload.user_id
        )

        if key in processed_reactions:
            processed_reactions.remove(key)

    except Exception as e:

        logging.error(
            f"Reaction remove error: {e}"
        )

# ==================================================
# READY
# ==================================================

@bot.event
async def on_ready():

    logging.info(
        f"Logged in as {bot.user}"
    )

    try:

        synced = await bot.tree.sync()

        logging.info(
            f"Synced {len(synced)} slash commands"
        )

    except Exception as e:

        logging.error(
            f"Sync error: {e}"
        )

    if not hasattr(bot, "midnight_started"):

        bot.midnight_started = True

        bot.loop.create_task(
            midnight_loop()
        )
# ==================================================
# HELP COMMAND
# ==================================================

@bot.command(name="help")
async def help_command(ctx):

    embed = discord.Embed(
        title="📖 Slate Commands",
        color=0x5865F2
    )

    embed.add_field(
        name="😭 Sob Commands",
        value=(
            "`slate mysobs`\n"
            "`slate topsobs`\n"
            "`slate sobcard`\n"
            "`slate sobcard @user`"
        ),
        inline=False
    )

    embed.add_field(
        name="🏆 Champion",
        value="`slate setchampionchannel #channel`",
        inline=False
    )

    embed.add_field(
        name="🔒 Moderation",
        value=(
            "`slate seal @user [10m|1h|2d]`\n"
            "`slate unseal @user`"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Admin",
        value=(
            "`slate say <message>`\n"
            "`slate disable`\n"
            "`slate enable`"
        ),
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name="commands")
async def commands_alias(ctx):
    await help_command(ctx)

# ==================================================
# MYSOBS
# ==================================================

@bot.command(name="mysobs")
async def mysobs(ctx):

    if await lock_check_ctx(ctx):
        return

    sobs = get_total_sobs(ctx.author.id)

    await ctx.send(
        f"😭 You have **{sobs}** sobs."
    )

# ==================================================
# TOPSOBS
# ==================================================

@bot.command(name="topsobs")
async def topsobs(ctx):

    if await lock_check_ctx(ctx):
        return

    cursor.execute("""
        SELECT user_id, sobs
        FROM users
        ORDER BY sobs DESC
        LIMIT 10
    """)

    results = cursor.fetchall()

    embed = discord.Embed(
        title="😭 Top Sobbers",
        color=0x5865F2
    )

    medals = ["🥇", "🥈", "🥉"]

    for rank, row in enumerate(results, start=1):

        member = ctx.guild.get_member(
            int(row["user_id"])
        )

        name = (
            member.display_name
            if member else
            f"User {row['user_id']}"
        )

        prefix = (
            medals[rank - 1]
            if rank <= 3
            else f"#{rank}"
        )

        embed.add_field(
            name=f"{prefix} {name}",
            value=f"😭 {row['sobs']}",
            inline=False
        )

    await ctx.send(embed=embed)

# ==================================================
# SOBCARD
# ==================================================

@bot.command(name="sobcard")
async def sobcard(
    ctx,
    member: discord.Member = None
):

    if await lock_check_ctx(ctx):
        return

    member = member or ctx.author

    ensure_user(member.id)

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (str(member.id),))

    user = cursor.fetchone()

    sobs = user["sobs"]
    streak = user["current_streak"]
    best = user["best_streak"]

    today = get_daily_sobs(member.id)

    cursor.execute("""
        SELECT COUNT(*) + 1
        FROM users
        WHERE sobs > ?
    """, (sobs,))

    rank = cursor.fetchone()[0]

    embed = discord.Embed(
        title=f"😭 {member.display_name}'s Sob Card",
        color=0x5865F2
    )

    embed.add_field(
        name="Total Sobs",
        value=sobs
    )

    embed.add_field(
        name="Rank",
        value=f"#{rank}"
    )

    embed.add_field(
        name="Today's Sobs",
        value=today
    )

    embed.add_field(
        name="🔥 Current Streak",
        value=streak
    )

    embed.add_field(
        name="🏆 Best Streak",
        value=best
    )

    embed.add_field(
        name="Goal",
        value=f"{STREAK_REQUIREMENT}+ sobs/day"
    )

    await ctx.send(embed=embed)

# ==================================================
# SET CHAMPION CHANNEL
# ==================================================

@bot.command(name="setchampionchannel")
@commands.has_permissions(administrator=True)
async def setchampionchannel(
    ctx,
    channel: discord.TextChannel
):

    set_champion_channel(channel.id)

    await ctx.send(
        f"🏆 Champion channel set to {channel.mention}"
    )

# ==================================================
# SAY
# ==================================================

@bot.command(name="say")
@commands.has_permissions(administrator=True)
async def say(ctx, *, message):

    try:
        await ctx.message.delete()
    except:
        pass

    await ctx.send(message)

# ==================================================
# DURATION PARSER
# ==================================================

def parse_duration(duration):

    match = re.match(
        r"(\d+)(s|m|h|d)",
        duration.lower()
    )

    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    multipliers = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400
    }

    return value * multipliers[unit]

# ==================================================
# SEAL / UNSEAL
# ==================================================

@bot.command(name="seal")
@commands.has_permissions(administrator=True)
async def seal(
    ctx,
    member: discord.Member,
    duration: str = "1h"
):

    seconds = parse_duration(duration)

    if not seconds:
        return await ctx.send(
            "❌ Invalid duration."
        )

    until = (
        discord.utils.utcnow()
        + datetime.timedelta(seconds=seconds)
    )

    await member.timeout(
        until,
        reason=f"Sealed by {ctx.author}"
    )

    await ctx.send(
        f"🔒 {member.mention} sealed for {duration}"
    )

@bot.command(name="unseal")
@commands.has_permissions(administrator=True)
async def unseal(
    ctx,
    member: discord.Member
):

    await member.timeout(None)

    await ctx.send(
        f"🔓 {member.mention} unsealed."
    )

# ==================================================
# ENABLE / DISABLE
# ==================================================

@bot.command(name="disable")
@commands.has_permissions(administrator=True)
async def disable(ctx):

    global bot_locked

    bot_locked = True

    await ctx.send(
        "🚫 Commands disabled."
    )

@bot.command(name="enable")
@commands.has_permissions(administrator=True)
async def enable(ctx):

    global bot_locked

    bot_locked = False

    await ctx.send(
        "✅ Commands enabled."
    )
# ==================================================
# SLASH COMMANDS
# ==================================================

@bot.tree.command(
    name="mysobs",
    description="View your sob count"
)
async def mysobs_slash(
    interaction: discord.Interaction
):

    if is_locked():
        return await interaction.response.send_message(
            "🚫 Bot commands are disabled.",
            ephemeral=True
        )

    sobs = get_total_sobs(
        interaction.user.id
    )

    await interaction.response.send_message(
        f"😭 You have **{sobs}** sobs."
    )

@bot.tree.command(
    name="topsobs",
    description="View the leaderboard"
)
async def topsobs_slash(
    interaction: discord.Interaction
):

    cursor.execute("""
        SELECT user_id, sobs
        FROM users
        ORDER BY sobs DESC
        LIMIT 10
    """)

    results = cursor.fetchall()

    embed = discord.Embed(
        title="😭 Top Sobbers",
        color=0x5865F2
    )

    medals = ["🥇", "🥈", "🥉"]

    for rank, row in enumerate(results, start=1):

        try:
            user = await bot.fetch_user(
                int(row["user_id"])
            )
            name = user.name
        except:
            name = "Unknown User"

        prefix = (
            medals[rank - 1]
            if rank <= 3
            else f"#{rank}"
        )

        embed.add_field(
            name=f"{prefix} {name}",
            value=f"😭 {row['sobs']}",
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )

@bot.tree.command(
    name="sobcard",
    description="View a sob card"
)
async def sobcard_slash(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    ensure_user(member.id)

    cursor.execute("""
        SELECT *
        FROM users
        WHERE user_id = ?
    """, (str(member.id),))

    user = cursor.fetchone()

    embed = discord.Embed(
        title=f"😭 {member.display_name}'s Sob Card",
        color=0x5865F2
    )

    embed.add_field(
        name="Total Sobs",
        value=user["sobs"]
    )

    embed.add_field(
        name="🔥 Current Streak",
        value=user["current_streak"]
    )

    embed.add_field(
        name="🏆 Best Streak",
        value=user["best_streak"]
    )

    await interaction.response.send_message(
        embed=embed
    )

# ==================================================
# ADMIN SLASH COMMANDS
# ==================================================

@bot.tree.command(name="disable")
@app_commands.default_permissions(
    administrator=True
)
async def disable_slash(
    interaction: discord.Interaction
):

    global bot_locked

    bot_locked = True

    await interaction.response.send_message(
        "🚫 Commands disabled."
    )

@bot.tree.command(name="enable")
@app_commands.default_permissions(
    administrator=True
)
async def enable_slash(
    interaction: discord.Interaction
):

    global bot_locked

    bot_locked = False

    await interaction.response.send_message(
        "✅ Commands enabled."
    )

# ==================================================
# ERROR HANDLERS
# ==================================================

@bot.event
async def on_command_error(
    ctx,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):
        return await ctx.send(
            "❌ Missing permissions."
        )

    if isinstance(
        error,
        commands.MemberNotFound
    ):
        return await ctx.send(
            "❌ Member not found."
        )

    logging.error(
        f"Command Error: {error}"
    )

@bot.tree.error
async def on_app_command_error(
    interaction,
    error
):

    logging.error(
        f"Slash Error: {error}"
    )

    if interaction.response.is_done():
        return

    await interaction.response.send_message(
        "❌ An error occurred.",
        ephemeral=True
    )

# ==================================================
# START BOT
# ==================================================

if __name__ == "__main__":

    try:

        bot.run(TOKEN)

    finally:

        db.close()