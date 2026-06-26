import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3, os, datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="slate ", intents=intents, help_command=None)

db = sqlite3.connect("stats.db")
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stats(
guild_id INTEGER,
user_id INTEGER,
messages INTEGER DEFAULT 0,
sobs INTEGER DEFAULT 0,
weekly_messages INTEGER DEFAULT 0,
weekly_sobs INTEGER DEFAULT 0,
PRIMARY KEY(guild_id,user_id)
)
""")
db.commit()

SOB = "😭"

def ensure(gid, uid):
    cur.execute("INSERT OR IGNORE INTO stats(guild_id,user_id) VALUES(?,?)",(gid,uid))
    db.commit()

def message_rank(v):
    if v >= 10000: return "Message Legend"
    if v >= 5000: return "Veteran"
    if v >= 1000: return "Active Member"
    if v >= 250: return "Chatter"
    return "Newcomer"

def sob_rank(v):
    if v >= 5000: return "Ultimate Sobber"
    if v >= 1000: return "Diamond Sobber"
    if v >= 250: return "Gold Sobber"
    if v >= 100: return "Silver Sobber"
    if v >= 25: return "Bronze Sobber"
    return "Fresh Sobber"

@tasks.loop(hours=24)
async def weekly_reset_check():
    if datetime.datetime.utcnow().weekday() == 0:
        cur.execute("UPDATE stats SET weekly_messages=0, weekly_sobs=0")
        db.commit()

@bot.event
async def on_ready():
    await bot.tree.sync()
    if not weekly_reset_check.is_running():
        weekly_reset_check.start()
    print(f"Ready: {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    ensure(message.guild.id, message.author.id)
    cur.execute("""
    UPDATE stats SET
    messages=messages+1,
    weekly_messages=weekly_messages+1
    WHERE guild_id=? AND user_id=?
    """,(message.guild.id,message.author.id))
    db.commit()
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or not reaction.message.guild:
        return
    if str(reaction.emoji) == SOB:
        target = reaction.message.author
        ensure(reaction.message.guild.id, target.id)
        cur.execute("""
        UPDATE stats SET
        sobs=sobs+1,
        weekly_sobs=weekly_sobs+1
        WHERE guild_id=? AND user_id=?
        """,(reaction.message.guild.id,target.id))
        db.commit()

async def profile_embed(member, guild):
    ensure(guild.id, member.id)
    cur.execute("""SELECT messages,sobs,weekly_messages,weekly_sobs
    FROM stats WHERE guild_id=? AND user_id=?""",(guild.id,member.id))
    m,s,wm,ws = cur.fetchone()

    cur.execute("""SELECT COUNT(*)+1 FROM stats
    WHERE guild_id=? AND sobs >
    (SELECT sobs FROM stats WHERE guild_id=? AND user_id=?)
    """,(guild.id,guild.id,member.id))
    place = cur.fetchone()[0]

    e = discord.Embed(title=f"{member.display_name}'s Profile")
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Messages", value=m)
    e.add_field(name="SOBs", value=s)
    e.add_field(name="Weekly Messages", value=wm)
    e.add_field(name="Weekly SOBs", value=ws)
    e.add_field(name="Message Rank", value=message_rank(m), inline=False)
    e.add_field(name="SOB Rank", value=sob_rank(s))
    e.add_field(name="Leaderboard Position", value=f"#{place}")
    return e

@bot.command()
async def profile(ctx, member: discord.Member=None):
    member = member or ctx.author
    await ctx.send(embed=await profile_embed(member, ctx.guild))

@bot.command()
async def leaderboard(ctx):
    cur.execute("""SELECT user_id,sobs,messages
    FROM stats WHERE guild_id=?
    ORDER BY sobs DESC LIMIT 10""",(ctx.guild.id,))
    rows=cur.fetchall()
    e=discord.Embed(title="🏆 SOB Leaderboard")
    for i,r in enumerate(rows,1):
        m=ctx.guild.get_member(r[0])
        if m:
            e.add_field(name=f"#{i} {m.display_name}",
                        value=f"😭 {r[1]} | 💬 {r[2]}",
                        inline=False)
    await ctx.send(embed=e)

@bot.command()
async def topmessages(ctx):
    cur.execute("""SELECT user_id,messages
    FROM stats WHERE guild_id=?
    ORDER BY messages DESC LIMIT 10""",(ctx.guild.id,))
    rows=cur.fetchall()
    e=discord.Embed(title="💬 Message Leaderboard")
    for i,r in enumerate(rows,1):
        m=ctx.guild.get_member(r[0])
        if m:
            e.add_field(name=f"#{i} {m.display_name}", value=r[1], inline=False)
    await ctx.send(embed=e)

@bot.command()
async def weekly(ctx):
    cur.execute("""SELECT user_id,weekly_sobs,weekly_messages
    FROM stats WHERE guild_id=?
    ORDER BY weekly_sobs DESC LIMIT 10""",(ctx.guild.id,))
    rows=cur.fetchall()
    e=discord.Embed(title="📅 Weekly Leaderboard")
    for i,r in enumerate(rows,1):
        m=ctx.guild.get_member(r[0])
        if m:
            e.add_field(name=f"#{i} {m.display_name}",
                        value=f"😭 {r[1]} | 💬 {r[2]}",
                        inline=False)
    await ctx.send(embed=e)

@bot.command()
@commands.has_permissions(administrator=True)
async def addsobs(ctx, member: discord.Member, amount: int):
    ensure(ctx.guild.id, member.id)
    cur.execute("UPDATE stats SET sobs=sobs+? WHERE guild_id=? AND user_id=?",
                (amount,ctx.guild.id,member.id))
    db.commit()
    await ctx.send("Done.")

@bot.command()
@commands.has_permissions(administrator=True)
async def addmessages(ctx, member: discord.Member, amount: int):
    ensure(ctx.guild.id, member.id)
    cur.execute("UPDATE stats SET messages=messages+? WHERE guild_id=? AND user_id=?",
                (amount,ctx.guild.id,member.id))
    db.commit()
    await ctx.send("Done.")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetuser(ctx, member: discord.Member):
    cur.execute("""DELETE FROM stats
    WHERE guild_id=? AND user_id=?""",(ctx.guild.id,member.id))
    db.commit()
    await ctx.send("User reset.")

@bot.command()
@commands.has_permissions(administrator=True)
async def resetserver(ctx):
    cur.execute("DELETE FROM stats WHERE guild_id=?",(ctx.guild.id,))
    db.commit()
    await ctx.send("Server stats reset.")

@bot.command()
async def help(ctx):
    await ctx.send("""
**Slate Bot**
slate profile
slate leaderboard
slate weekly
slate topmessages
slate addsobs
slate addmessages
slate resetuser
slate resetserver
""")

@bot.tree.command(name="profile")
async def slash_profile(interaction: discord.Interaction, member: discord.Member=None):
    member = member or interaction.user
    await interaction.response.send_message(embed=await profile_embed(member, interaction.guild))

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission.")
    else:
        await ctx.send(f"Error: {error}")

bot.run(TOKEN)
