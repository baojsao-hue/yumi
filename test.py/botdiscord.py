# botdiscord.py (Discord adapter với Google TTS WAV)
from dotenv import load_dotenv
load_dotenv()
import discord
import os
import yumi_core
import random
import json
import datetime
import re
import asyncio
from tts import text_to_speech
from discord import FFmpegPCMAudio

TOKEN = os.getenv("DISCORD_TOKEN_YUMI")
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True

client = discord.Client(intents=intents)

LOG_FILE = "reddit_crawl_logs.txt"
LONG_MEMORY_FILE = "long_memoryyumi.json"
DISCORD_MSG_LIMIT = 1900

# per-guild voice client / queue / player task
voice_clients = {}       # guild_id -> VoiceClient
voice_queues = {}        # guild_id -> asyncio.Queue()
player_tasks = {}        # guild_id -> asyncio.Task

def safe_send(text, user_id="system", user_name="Summarizer"):
    if len(text) <= DISCORD_MSG_LIMIT:
        return text
    try:
        summary = yumi_core.chat(
            f"Hãy tóm tắt câu trả lời này gọn lại (<= {DISCORD_MSG_LIMIT} ký tự) nhưng giữ nguyên ý và giọng văn:\n{text}",
            user_id=user_id,
            user_name=user_name,
        )
        if len(summary) > DISCORD_MSG_LIMIT:
            return summary[:DISCORD_MSG_LIMIT] + "\n...(Yumi rút gọn thêm)"
        return summary
    except Exception:
        return text[:DISCORD_MSG_LIMIT] + "\n...(Yumi bị buộc cắt bớt)"

async def ensure_queue_and_task(guild_id: int):
    """Ensure a queue and player task exist for guild."""
    if guild_id not in voice_queues:
        voice_queues[guild_id] = asyncio.Queue()
    if guild_id not in player_tasks or player_tasks[guild_id].done():
        player_tasks[guild_id] = asyncio.create_task(audio_player_loop(guild_id))

async def audio_player_loop(guild_id: int):
    """Continuously consume queue and play audios for the guild."""
    q = voice_queues.get(guild_id)
    if q is None:
        return
    try:
        while True:
            item = await q.get()
            path = item.get("path")
            vc = voice_clients.get(guild_id)
            if not vc:
                guild = client.get_guild(guild_id)
                vc = discord.utils.get(client.voice_clients, guild=guild)
                if vc:
                    voice_clients[guild_id] = vc

            if not vc:
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                except:
                    pass
                q.task_done()
                continue

            done = asyncio.Event()
            def _after(err):
                if err:
                    print("⚠️ Playback error:", err)
                client.loop.call_soon_threadsafe(done.set)

            # dùng ffmpeg phát file wav/mp3
            source = FFmpegPCMAudio(
                path,
                before_options="-nostdin",
                options="-vn"
            )
            print(f"🔊 Playing audio: {path}")
            # Kiểm tra xem có đang phát audio không
            try:
                if not vc.is_playing():
                    vc.play(source, after=_after)
                else:
                    print("⚠️ Voice client đang phát audio khác")
            except AttributeError:
                # Fallback nếu không có is_playing method
                vc.play(source, after=_after)
            await done.wait()

            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print("⚠️ Could not remove audio file:", e)

            q.task_done()
    except asyncio.CancelledError:
        while not q.empty():
            item = q.get_nowait()
            p = item.get("path")
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except:
                pass
            q.task_done()
        return
    except Exception as e:
        print("⚠️ audio_player_loop crashed:", e)
        return

async def connect_voice_channel(channel):
    """Connect bot to a voice channel and store client."""
    guild_id = channel.guild.id
    vc = discord.utils.get(client.voice_clients, guild=channel.guild)
    if vc and vc.channel:
        voice_clients[guild_id] = vc
        return vc
    vc = await channel.connect()
    voice_clients[guild_id] = vc
    return vc

async def enqueue_audio(guild_id: int, path: str):
    """Add audio path to guild queue and ensure player running."""
    if guild_id not in voice_queues:
        voice_queues[guild_id] = asyncio.Queue()
    await voice_queues[guild_id].put({"path": path})
    await ensure_queue_and_task(guild_id)

@client.event
async def on_ready():
    print(f"✅ Yumi đã online trong Discord dưới user: {client.user}")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    user_id = str(message.author.id)
    user_name = str(message.author.name)
    user_input = message.content.strip()
    if not user_input:
        return

    # join
    if user_input.lower() in ["!join", "!summon"]:
        if message.author.voice and message.author.voice.channel:
            vc = discord.utils.get(client.voice_clients, guild=message.guild)
            if not vc:
                await connect_voice_channel(message.author.voice.channel)
            await message.channel.send("🎶 Yumi đã vào voice channel! (Sẽ giữ kết nối cho tới lệnh !leave)")
        else:
            await message.channel.send("❌ Bạn phải ở trong voice channel để mời Yumi vô.")
        return

    # leave
    if user_input.lower() in ["!leave", "!disconnect"]:
        guild_id = message.guild.id
        vc = voice_clients.get(guild_id) or discord.utils.get(client.voice_clients, guild=message.guild)
        if vc:
            task = player_tasks.get(guild_id)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except:
                    pass
            try:
                await vc.disconnect(force=True)
            except:
                pass
            voice_clients.pop(guild_id, None)
            voice_queues.pop(guild_id, None)
            player_tasks.pop(guild_id, None)
            await message.channel.send("👋 Yumi đã rời voice channel!")
        else:
            await message.channel.send("❌ Yumi không ở channel nào cả.")
        return

    # help
    if user_input.lower() in ["!yumi", "!yumi help", "!help"]:
        help_text = (
            "✨ **Yumi command menu** ✨\n"
            "`!join` → Mời Yumi vào voice (giữ kết nối).\n"
            "`!leave` → Cho Yumi rời voice.\n"
            "`!reset` → Xoá context ngắn hạn.\n"
            "`!recall` → Đọc vài ký ức ngẫu nhiên.\n"
            "`!recall_today` → Nhớ lại mấy thứ học hôm nay.\n"
            "`!stats` → Xem báo cáo.\n"
        )
        await message.channel.send(safe_send(help_text))
        return

    if user_input.lower() == "!reset":
        # Reset conversation (xóa lịch sử ngắn hạn)
        try:
            yumi_core.user_histories[user_id] = [{"role": "system", "content": yumi_core.SYSTEM_PROMPT}]
        except:
            pass
        await message.channel.send("🧹 Yumi đã reset context cho Bố rồi đó!")
        return

    if user_input.lower() == "!recall":
        try:
            with open(LONG_MEMORY_FILE, "r", encoding="utf-8") as f:
                memory_data = json.load(f)
            if memory_data:
                sample = random.sample(memory_data, min(3, len(memory_data)))
                recall_text = "📖 Đây là vài ký ức Yumi nhớ được nè:\n" + "\n".join(
                    f"— {m}" for m in sample
                )
            else:
                recall_text = "😿 Bộ nhớ Yumi đang trống trơn..."
        except Exception as e:
            recall_text = f"⚠️ Không đọc được long_memory: {e}"
        await message.channel.send(safe_send(recall_text))
        return

    if user_input.lower() == "!recall_today":
        today = datetime.date.today().strftime("%Y-%m-%d")
        recall_lines = []
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if today in line and "🧠 Lưu vào memory:" in line:
                        match = re.search(r"🧠 Lưu vào memory: (.+)", line)
                        if match:
                            recall_lines.append(match.group(1))
            if recall_lines:
                sample = random.sample(recall_lines, min(3, len(recall_lines)))
                recall_text = f"📅 Hôm nay ({today}) Yumi đã học được:\n" + "\n".join(
                    f"— {m}" for m in sample
                )
            else:
                recall_text = "😿 Hôm nay Yumi chưa học được gì mới..."
        except Exception as e:
            recall_text = f"⚠️ Không đọc được log hôm nay: {e}"
        await message.channel.send(safe_send(recall_text))
        return

    if user_input.lower() == "!stats":
        today = datetime.date.today().strftime("%Y-%m-%d")
        en_count = vn_count = total_count = 0
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if today in line and "🧠 Lưu vào memory:" in line:
                        if "[EN]" in line:
                            en_count += 1
                        elif "[VN]" in line:
                            vn_count += 1
                        total_count += 1
            stats_text = (
                f"📊 Stats hôm nay ({today}):\n"
                f"  ❯ EN notes: {en_count}\n"
                f"  ❯ VN notes: {vn_count}\n"
                f"  ❯ Tổng: {total_count}\n"
            )
        except Exception as e:
            stats_text = f"⚠️ Không đọc được log hôm nay: {e}"
        await message.channel.send(safe_send(stats_text))
        return

    # normal chat
    try:
        response = yumi_core.chat(user_input, user_id=user_id, user_name=user_name)
        await message.channel.send(safe_send(response, user_id=user_id, user_name=user_name))

        if message.author.voice and message.author.voice.channel:
            guild_id = message.guild.id
            vc = voice_clients.get(guild_id) or discord.utils.get(client.voice_clients, guild=message.guild)
            if not vc:
                try:
                    vc = await connect_voice_channel(message.author.voice.channel)
                except Exception as e:
                    print("⚠️ Could not connect to voice:", e)
                    vc = None

            audio_file = text_to_speech(response)
            if audio_file:
                await enqueue_audio(message.guild.id, audio_file)

    except Exception as e:
        await message.channel.send(f"⚠️ Lỗi: {e}")

if __name__ == "__main__":
    if TOKEN:
        client.run(TOKEN)
    else:
        print("❌ DISCORD_TOKEN_YUMI không được thiết lập")