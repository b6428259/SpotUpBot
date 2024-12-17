import discord
from discord.ext import commands
from openai import OpenAI
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()




# Configuration from environment variables
GITHUB_FEED_CHANNEL_ID = 1318527944297021446
CHANGELOG_CHANNEL_ID = 1318527944297021444
ISSUES_CHANNEL_ID = 1318554103139274824
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")
    try:
        await bot.load_extension("music")
        print("Music cog loaded successfully")
    except Exception as e:
        print(f"Error loading music cog: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.MissingRequiredArgument):
        # Help for specific command when arguments are missing
        await ctx.send(f"❌ คำสั่งไม่สมบูรณ์ กรุณาใช้งานให้ถูกต้อง\n"
                       f"พิมพ์ `!help {ctx.command}` เพื่อดูวิธีใช้งาน")
    
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ ไม่พบคำสั่งนี้ พิมพ์ `!help` เพื่อดูรายการคำสั่งทั้งหมด")
    
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ รูปแบบข้อมูลไม่ถูกต้อง\n"
                       f"พิมพ์ `!help {ctx.command}` เพื่อดูวิธีใช้งานที่ถูกต้อง")
    
    else:
        # Log unexpected errors
        print(f"Unexpected error: {error}")
        await ctx.send("❌ เกิดข้อผิดพลาดที่ไม่คาดคิด กรุณาลองใหม่อีกครั้ง")

@bot.command(name="help", help="แสดงรายการคำสั่งทั้งหมด")
async def custom_help(ctx, command_name: str = None):
    """Custom help command with more detailed information"""
    if command_name:
        # Show help for a specific command
        command = bot.get_command(command_name)
        if command:
            embed = discord.Embed(
                title=f"🆘 วิธีใช้คำสั่ง `{command_name}`",
                color=discord.Color.blue()
            )
            embed.add_field(name="คำอธิบาย", value=command.help or "ไม่มีคำอธิบาย", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ ไม่พบคำสั่ง `{command_name}`")
    else:
        # Show all commands
        embed = discord.Embed(
            title="🤖 รายการคำสั่งทั้งหมด",
            description="พิมพ์ `!help ชื่อคำสั่ง` เพื่อดูรายละเอียดเพิ่มเติมของคำสั่งนั้น เช่น `!help play`",
            color=discord.Color.green()
        )
        
        # Group commands by cog
        for cog_name, cog in bot.cogs.items():
            commands_in_cog = [f"`{cmd.name}`" for cmd in cog.get_commands()]
            if commands_in_cog:
                embed.add_field(
                name=f"📦 {cog_name}",
                value=" | ".join(commands_in_cog),
                inline=False
        )

        
        await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)