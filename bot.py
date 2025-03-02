import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import InputStream, AudioPiped
from youtube_dl import YoutubeDL
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Config
API_ID = "YOUR_API_ID"
API_HASH = "YOUR_API_HASH"
BOT_TOKEN = "BOT_TOKEN"
SPOTIFY_CLIENT_ID = "YOUR_SPOTIFY_CLIENT_ID"
SPOTIFY_CLIENT_SECRET = "YOUR_SPOTIFY_CLIENT_SECRET"

app = Client("MusicBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
vc = PyTgCalls(app)
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

queue = {}  # Queue system for songs

# Download and return audio file
def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': 'song.mp3'
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return 'song.mp3'

# Play command
@app.on_message(filters.command("play") & filters.group)
async def play(client, message):
    query = " ".join(message.command[1:])
    if not query:
        return await message.reply("❌ Usage: /play song_name or YouTube/Spotify link")

    chat_id = message.chat.id

    msg = await message.reply("🔍 Searching...")

    if "spotify.com" in query:
        track = sp.track(query)
        query = track["name"] + " " + track["artists"][0]["name"]

    ydl_opts = {'format': 'bestaudio'}
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=False)['entries'][0]
        url = info['url']
        title = info['title']

    file_path = download_audio(url)

    if chat_id not in queue:
        queue[chat_id] = []

    queue[chat_id].append(file_path)

    if len(queue[chat_id]) == 1:
        await vc.join_group_call(chat_id, AudioPiped(file_path, StreamType().local_stream))
        await msg.edit(f"🎶 Now Playing: **{title}**", reply_markup=control_buttons())
    else:
        await msg.edit(f"✅ Added to queue: **{title}**")

# Pause command
@app.on_message(filters.command("pause") & filters.group)
async def pause(client, message):
    chat_id = message.chat.id
    await vc.pause_stream(chat_id)
    await message.reply("⏸ Music Paused!")

# Resume command
@app.on_message(filters.command("resume") & filters.group)
async def resume(client, message):
    chat_id = message.chat.id
    await vc.resume_stream(chat_id)
    await message.reply("▶ Music Resumed!")

# Skip command
@app.on_message(filters.command("skip") & filters.group)
async def skip(client, message):
    chat_id = message.chat.id
    if chat_id in queue and len(queue[chat_id]) > 1:
        queue[chat_id].pop(0)
        next_song = queue[chat_id][0]
        await vc.change_stream(chat_id, AudioPiped(next_song, StreamType().local_stream))
        await message.reply("⏭ Skipped to next song!")
    else:
        await vc.leave_group_call(chat_id)
        queue[chat_id] = []
        await message.reply("🛑 No more songs in queue. Leaving VC!")

# Stop command
@app.on_message(filters.command("stop") & filters.group)
async def stop(client, message):
    chat_id = message.chat.id
    await vc.leave_group_call(chat_id)
    queue[chat_id] = []
    await message.reply("🛑 Stopped Music!")

# Auto Leave If No Songs In Queue
async def auto_leave():
    while True:
        await asyncio.sleep(60)
        for chat_id in list(queue.keys()):
            if len(queue[chat_id]) == 0:
                await vc.leave_group_call(chat_id)
                del queue[chat_id]

# Inline Button Controls
def control_buttons():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏸ Pause", callback_data="pause"), InlineKeyboardButton("▶ Resume", callback_data="resume")],
        [InlineKeyboardButton("⏭ Skip", callback_data="skip"), InlineKeyboardButton("🛑 Stop", callback_data="stop")]
    ])

@app.on_callback_query()
async def button_callback(client, query):
    chat_id = query.message.chat.id
    if query.data == "pause":
        await vc.pause_stream(chat_id)
        await query.message.edit_text("⏸ Music Paused!", reply_markup=control_buttons())
    elif query.data == "resume":
        await vc.resume_stream(chat_id)
        await query.message.edit_text("▶ Music Resumed!", reply_markup=control_buttons())
    elif query.data == "skip":
        if chat_id in queue and len(queue[chat_id]) > 1:
            queue[chat_id].pop(0)
            next_song = queue[chat_id][0]
            await vc.change_stream(chat_id, AudioPiped(next_song, StreamType().local_stream))
            await query.message.edit_text("⏭ Skipped to next song!", reply_markup=control_buttons())
        else:
            await vc.leave_group_call(chat_id)
            queue[chat_id] = []
            await query.message.edit_text("🛑 No more songs in queue. Leaving VC!")
    elif query.data == "stop":
        await vc.leave_group_call(chat_id)
        queue[chat_id] = []
        await query.message.edit_text("🛑 Stopped Music!")

# Start Bot
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("🎵 **VC Music Bot is Active!**\n\nCommands:\n/play [song name or YouTube/Spotify link]\n/pause\n/resume\n/skip\n/stop")

vc.start()
app.loop.create_task(auto_leave())
app.run()
