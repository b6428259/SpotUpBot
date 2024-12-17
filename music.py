import discord
from discord.ext import commands
import yt_dlp
import asyncio
from async_timeout import timeout

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.play_next_song = {}
        self.volume = 0.5
        self.current_song = {}
        self.is_playing = {}  # Track playing state per server

    async def audio_player_task(self, ctx):
        try:
            while True:
                # Check if queue is empty
                if (ctx.guild.id not in self.queue or 
                    not self.queue[ctx.guild.id]):
                    # Reset playing state
                    self.is_playing[ctx.guild.id] = False
                    return

                # Ensure voice client is still connected
                if not ctx.voice_client or not ctx.voice_client.is_connected():
                    return

                # Get next song
                current_url = self.queue[ctx.guild.id].pop(0)
                self.current_song[ctx.guild.id] = current_url
                self.is_playing[ctx.guild.id] = True

                try:
                    # Attempt to play song with timeout
                    source = await YTDLSource.from_url(
                        current_url, 
                        loop=self.bot.loop, 
                        stream=True
                    )
                    source.volume = self.volume

                    # Play with enhanced error handling
                    def after_playing(error):
                        if error:
                            print(f"Playback error: {error}")
                        
                        # Signal to play next song
                        asyncio.run_coroutine_threadsafe(
                            self.continue_playing(ctx), 
                            self.bot.loop
                        )

                    ctx.voice_client.play(source, after=after_playing)
                    await ctx.send(f'🎵 กำลังเล่นเพลง: {source.title}')

                    # Wait until song finishes or is stopped
                    while ctx.voice_client and ctx.voice_client.is_playing():
                        await asyncio.sleep(1)

                except Exception as e:
                    print(f"Error playing song: {e}")
                    await ctx.send(f'❌ เกิดปัญหาขณะเล่นเพลง: {str(e)}')
                    # Continue to next song
                    continue

        except Exception as e:
            print(f"Critical error in audio player: {e}")
            self.is_playing[ctx.guild.id] = False

    async def continue_playing(self, ctx):
        """Continue playing next song in queue"""
        try:
            # Check if more songs in queue
            if (ctx.guild.id in self.queue and 
                self.queue[ctx.guild.id]):
                # Restart audio player task
                await self.audio_player_task(ctx)
            else:
                self.is_playing[ctx.guild.id] = False
        except Exception as e:
            print(f"Error in continue_playing: {e}")

                
    def handle_song_complete(self, ctx, error):
        """Handle song completion or errors"""
        if error:
            asyncio.run_coroutine_threadsafe(
                ctx.send(f'❌ เกิดข้อผิดพลาดในการเล่นเพลง: {str(error)}'),
                self.bot.loop
            )
        
        # Clear the current song
        self.current_song.pop(ctx.guild.id, None)
        
        # Signal to play next song
        self.play_next_song[ctx.guild.id].set()
        
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle disconnections and reconnections"""
        if member.id == self.bot.user.id:
            if before.channel and not after.channel:  # Bot was disconnected
                for guild_id in self.queue:
                    if guild_id == before.channel.guild.id:
                        self.queue[guild_id] = []  # Clear queue
                        self.play_next_song[guild_id].set()  # Signal to stop current playback
                        
    
    @commands.command(name='now', help='แสดงเพลงที่กำลังเล่น')
    async def now_playing(self, ctx):
        if ctx.guild.id in self.current_song:
            await ctx.send(f'🎵 กำลังเล่น: {self.current_song[ctx.guild.id]}')
        else:
            await ctx.send('ไม่มีเพลงที่กำลังเล่นอยู่')


    @commands.command(name='join', help='เข้าร่วมห้องเสียง')
    async def join(self, ctx):
        if ctx.author.voice is None:
            return await ctx.send("คุณต้องอยู่ในห้องเสียงก่อน")

        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(ctx.author.voice.channel)

        await ctx.author.voice.channel.connect()
        self.queue[ctx.guild.id] = []
        self.play_next_song[ctx.guild.id] = asyncio.Event()

    @commands.command(name='play', help='เล่นเพลงจาก URL')
    async def play(self, ctx, *, url):
        if ctx.voice_client is None:
            await ctx.invoke(self.join)

        if ctx.guild.id not in self.queue:
            self.queue[ctx.guild.id] = []
            self.play_next_song[ctx.guild.id] = asyncio.Event()

        self.queue[ctx.guild.id].append(url)
        await ctx.send('🎵 เพิ่มเพลงในคิวแล้ว')

        if not ctx.voice_client.is_playing():
            self.bot.loop.create_task(self.audio_player_task(ctx))

    @commands.command(name='stop', help='หยุดเล่นเพลงและเคลียร์คิว')
    async def stop(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
            self.queue[ctx.guild.id] = []
            await ctx.send('⏹ หยุดเล่นเพลงแล้ว')

    @commands.command(name='leave', help='ออกจากห้องเสียง')
    async def leave(self, ctx):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await ctx.send('👋 ออกจากห้องเสียงแล้ว')

    @commands.command(name='volume', help='ปรับระดับเสียง')
    async def volume(self, ctx, volume: int):
        if ctx.voice_client is None:
            return await ctx.send("บอทไม่ได้อยู่ในห้องเสียง")

        ctx.voice_client.source.volume = volume / 100
        self.volume = volume / 100
        await ctx.send(f'🔊 ปรับระดับเสียงเป็น {volume}%')

    @commands.command(name='queue', help='ดูคิวเพลง')
    async def queue(self, ctx):
        if ctx.guild.id not in self.queue or not self.queue[ctx.guild.id]:
            return await ctx.send("คิวว่างเปล่า")

        await ctx.send(f'🎶 คิวเพลง:\n' + '\n'.join(self.queue[ctx.guild.id]))

    @commands.command(name='status')
    async def status(self, ctx):
        status = []
        if ctx.voice_client:
            status.append(f"🎵 สถานะการเชื่อมต่อ: {'เชื่อมต่อแล้ว' if ctx.voice_client.is_connected() else 'ไม่ได้เชื่อมต่อ'}")
            status.append(f"▶️ สถานะการเล่น: {'กำลังเล่น' if ctx.voice_client.is_playing() else 'ไม่ได้เล่น'}")
            status.append(f"🔊 ระดับเสียง: {int(self.volume * 100)}%")
            if ctx.guild.id in self.queue:
                status.append(f"📋 จำนวนเพลงในคิว: {len(self.queue[ctx.guild.id])}")
        else:
            status.append("❌ ไม่ได้เชื่อมต่อกับห้องเสียง")
        
        await ctx.send('\n'.join(status))

# Initialize the Music cog
async def setup(bot):
    await bot.add_cog(Music(bot))