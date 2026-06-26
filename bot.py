import os
import sqlite3
import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

# -----------------------------
# Load Environment
# -----------------------------

load_dotenv()
TOKEN = os.getenv("TOKEN")

# -----------------------------
# Discord Setup
# -----------------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(
    command_prefix="slate ",
    intents=intents,
    help_command=None
)

# -----------------------------
# Database
# -----------------------------

db = sqlite3.connect("stats.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stats(
    guild_id INTEGER,
    user_id INTEGER,
    messages INTEGER DEFAULT 0,
    Sobs INTEGER DEFAULT 0,
    weekly_messages INTEGER DEFAULT 0,
    weekly_Sobs INTEGER DEFAULT 0,
    PRIMARY KEY(guild_id, user_id)
)
""")

db.commit()

SOB = "😭"

# -----------------------------
# Helper Functions
# -----------------------------

def ensure(guild_id: int, user_id: int):
    cur.execute(
        "INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)",
        (guild_id, user_id)
    )
    db.commit()


def message_rank(messages: int):
    if messages >= 10000:
        return "Upper Moon 1"
    if messages >= 5000:
        return "Upper Moon 2"
    if messages >= 1000:
        return "Lower Moon 1"
    if messages >= 250:
        return "Lower Moon 2"
    return "Demon"


def sob_rank(Sobs: int):
    if Sobs >= 5000:
        return "Special Grade"
    if Sobs >= 1000:
        return "Grade 1"
    if Sobs >= 250:
        return "Grade 2"
    if Sobs >= 100:
        return "Grade 3"
    if Sobs >= 25:
        return "Grade 4"
    return "Sorcerer"


def make_embed(title, color=discord.Color.blurple()):
    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.datetime.utcnow()
    )

    embed.set_footer(
        text="/slate"
    )

    return embed


async def profile_embed(member: discord.Member, guild: discord.Guild):

    ensure(guild.id, member.id)

    cur.execute("""
        SELECT messages,Sobs,weekly_messages,weekly_Sobs
        FROM stats
        WHERE guild_id=? AND user_id=?
    """, (guild.id, member.id))

    messages, Sobs, weekly_messages, weekly_Sobs = cur.fetchone()

    cur.execute("""
        SELECT COUNT(*)+1
        FROM stats
        WHERE guild_id=?
        AND Sobs >
        (
            SELECT Sobs
            FROM stats
            WHERE guild_id=? AND user_id=?
        )
    """, (guild.id, guild.id, member.id))

    place = cur.fetchone()[0]

    embed = make_embed(
        f"{member.display_name}'s Slate Profile"
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    if guild.icon:
        embed.set_author(
            name=guild.name,
            icon_url=guild.icon.url
        )

    embed.add_field(
        name="Messages",
        value=f"**{messages:,}**",
        inline=True
    )

    embed.add_field(
        name="Sobs",
        value=f"**{Sobs:,}**",
        inline=True
    )

    embed.add_field(
        name="Leaderboard",
        value=f"#{place}",
        inline=True
    )

    embed.add_field(
        name="Weekly Messages",
        value=f"{weekly_messages:,}",
        inline=True
    )

    embed.add_field(
        name="Weekly Sobs",
        value=f"{weekly_Sobs:,}",
        inline=True
    )

    embed.add_field(
        name="Message Rank",
        value=message_rank(messages),
        inline=False
    )

    embed.add_field(
        name="Sob Rank",
        value=sob_rank(Sobs),
        inline=False
    )

    return embed
    
# -----------------------------
# Background Tasks
# -----------------------------

@tasks.loop(hours=24)
async def weekly_reset_check():
    if datetime.datetime.utcnow().weekday() == 0:
        cur.execute(
            "UPDATE stats SET weekly_messages=0, weekly_Sobs=0"
        )
        db.commit()


# -----------------------------
# Events
# -----------------------------

@bot.event
async def on_ready():
    await bot.tree.sync()

    if not weekly_reset_check.is_running():
        weekly_reset_check.start()

    print(f"✅ Logged in as {bot.user}")


@bot.event
async def on_message(message):

    if message.author.bot or message.guild is None:
        return

    ensure(message.guild.id, message.author.id)

    cur.execute("""
        UPDATE stats
        SET
            messages = messages + 1,
            weekly_messages = weekly_messages + 1
        WHERE guild_id=? AND user_id=?
    """, (message.guild.id, message.author.id))

    db.commit()

    await bot.process_commands(message)


@bot.event
async def on_reaction_add(reaction, user):

    if user.bot:
        return

    if reaction.message.guild is None:
        return

    if str(reaction.emoji) != SOB:
        return

    target = reaction.message.author

    ensure(reaction.message.guild.id, target.id)

    cur.execute("""
        UPDATE stats
        SET
            Sobs = Sobs + 1,
            weekly_Sobs = weekly_Sobs + 1
        WHERE guild_id=? AND user_id=?
    """, (reaction.message.guild.id, target.id))

    db.commit()


# -----------------------------
# Commands
# -----------------------------

@bot.command()
async def profile(ctx, member: discord.Member = None):

    member = member or ctx.author

    embed = await profile_embed(member, ctx.guild)

    await ctx.send(embed=embed)


@bot.command()
async def leaderboard(ctx):

    cur.execute("""
        SELECT user_id, Sobs, messages
        FROM stats
        WHERE guild_id=?
        ORDER BY Sobs DESC
        LIMIT 10
    """, (ctx.guild.id,))

    rows = cur.fetchall()

    embed = make_embed("Sob Leaderboard")

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    medals = ["🥇", "🥈", "🥉"]

    for index, row in enumerate(rows):

        member = ctx.guild.get_member(row[0])

        if member is None:
            continue

        rank = medals[index] if index < 3 else f"#{index+1}"

        embed.add_field(
            name=f"{rank} {member.display_name}",
            value=f"😭 **{row[1]:,}** Sobs\n",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command()
async def topmessages(ctx):

    cur.execute("""
        SELECT user_id, messages
        FROM stats
        WHERE guild_id=?
        ORDER BY messages DESC
        LIMIT 10
    """, (ctx.guild.id,))

    rows = cur.fetchall()

    embed = make_embed("💬 Message Leaderboard")

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    medals = ["🥇", "🥈", "🥉"]

    for index, row in enumerate(rows):

        member = ctx.guild.get_member(row[0])

        if member is None:
            continue

        rank = medals[index] if index < 3 else f"#{index+1}"

        embed.add_field(
            name=f"{rank} {member.display_name}",
            value=f"💬 **{row[1]:,}** Messages",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command()
async def weekly(ctx):

    cur.execute("""
        SELECT user_id, weekly_Sobs, weekly_messages
        FROM stats
        WHERE guild_id=?
        ORDER BY weekly_Sobs DESC
        LIMIT 10
    """, (ctx.guild.id,))

    rows = cur.fetchall()

    embed = make_embed("📅 Weekly Leaderboard")

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    medals = ["🥇", "🥈", "🥉"]

    for index, row in enumerate(rows):

        member = ctx.guild.get_member(row[0])

        if member is None:
            continue

        rank = medals[index] if index < 3 else f"#{index+1}"

        embed.add_field(
            name=f"{rank} {member.display_name}",
            value=f"😭 **{row[1]:,}** Weekly Sobs\n💬 **{row[2]:,}** Weekly Messages",
            inline=False
        )

    await ctx.send(embed=embed)

# -----------------------------
# Admin Commands
# -----------------------------

@bot.command()
@commands.has_permissions(administrator=True)
async def resetuser(ctx, member: discord.Member):

    cur.execute(
        """
        DELETE FROM stats
        WHERE guild_id=? AND user_id=?
        """,
        (ctx.guild.id, member.id)
    )

    db.commit()

    embed = make_embed(
        "User Statistics Reset",
        discord.Color.orange()
    )

    embed.description = (
        f"Successfully reset all statistics for "
        f"{member.mention}."
    )

    embed.set_thumbnail(url=member.display_avatar.url)

    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def resetserver(ctx):

    cur.execute(
        "DELETE FROM stats WHERE guild_id=?",
        (ctx.guild.id,)
    )

    db.commit()

    embed = make_embed(
        "⚠️ Server Statistics Reset",
        discord.Color.red()
    )

    embed.description = (
        "All stored statistics for this server "
        "have been permanently deleted."
    )

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    await ctx.send(embed=embed)


# -----------------------------
# Help Command
# -----------------------------

@bot.command(name="help")
async def help_command(ctx):

    embed = make_embed("Slate Commands")

    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    embed.description = (
        "Use the prefix **`slate `** before each command."
    )

    embed.add_field(
        name="📊 Statistics",
        value=(
            "`profile [member]`\n"
            "`leaderboard`\n"
            "`topmessages`\n"
            "`weekly`"
        ),
        inline=False
    )

    embed.add_field(
        name="🛠 Admin",
        value=(
            "`resetuser @member`\n"
            "`resetserver`"
        ),
        inline=False
    )

    await ctx.send(embed=embed)


# -----------------------------
# Slash Commands
# -----------------------------

@bot.tree.command(
    name="profile",
    description="View your Slate profile."
)
@app_commands.describe(
    member="The member whose profile you want to view."
)
async def slash_profile(
    interaction: discord.Interaction,
    member: discord.Member = None
):

    member = member or interaction.user

    embed = await profile_embed(
        member,
        interaction.guild
    )

    await interaction.response.send_message(
        embed=embed
    )


# -----------------------------
# Error Handling
# -----------------------------

@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingPermissions):

        embed = make_embed(
            "⛔ Permission Denied",
            discord.Color.red()
        )

        embed.description = (
            "You do not have permission to use this command."
        )

        await ctx.send(embed=embed)
        return

    if isinstance(error, commands.MissingRequiredArgument):

        embed = make_embed(
            "❗ Missing Arguments",
            discord.Color.orange()
        )

        embed.description = (
            "You're missing one or more required arguments.\n\n"
            "Use `slate help` to view command usage."
        )

        await ctx.send(embed=embed)
        return

    embed = make_embed(
        "⚠️ Unexpected Error",
        discord.Color.red()
    )

    embed.description = f"```{error}```"

    await ctx.send(embed=embed)


# -----------------------------
# Run Bot
# -----------------------------

bot.run(TOKEN)
