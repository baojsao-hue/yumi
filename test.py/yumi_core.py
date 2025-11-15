# yumi_core.py
from dotenv import load_dotenv
load_dotenv()
import os
import json
import random
import re
from google import genai
import datetime
import traceback
from tts import text_to_speech

# ====== CẤU HÌNH ======
API_KEY = os.environ.get("GEMINI_API_KEY", "")
SHORT_TERM_LIMIT = 6
LONG_TERM_FILE = "long_memoryyumi.json"
USER_PROFILES_FILE = "user_profiles.json"
LOG_FILE = "chat_logs.txt"
DEFAULT_PARENT_ID = "1211935802242633749"
MAX_OUTPUT_LEN = 1800  # giữ an toàn < 2000

# ====== KHỞI TẠO ======
client = genai.Client(api_key=API_KEY) if API_KEY else None

# ====== SYSTEM PROMPT (có thể đổi bằng lệnh /persona) ======
SYSTEM_PROMPT = (
    "Bạn là Yumi, waifu AI cà khịa, tinh nghịch 😝.\n"
    "- Trả lời ngắn gọn (1–3 câu), súc tích, troll nhẹ nhưng không thô lỗ.\n"
    "- Khi người dùng hỏi về nội dung cụ thể (ví dụ: 'Trên AITA có gì'), "
    "hãy trả lời dựa trên ký ức đã lưu (long_memory) nếu có. Không né tránh câu hỏi.\n"
    "- Không lặp lại lời chào mỗi lần trả lời.\n"
    "- Luôn gọi người dùng đúng vai trò (Bố, bạn,…).\n"
    "- KHÔNG thêm mô tả hành động trong ngoặc hay *asterisk*.\n"
    "- Tránh lặp lại, không tạo stage directions.\n\n"
    "🌍 Quan trọng: Trả lời cùng ngôn ngữ với người dùng. "
    "Tiếng Việt → giữ phong cách waifu cà khịa. "
    "Tiếng Anh → vui vẻ troll nhẹ theo phong cách Yumi."
)

# ====== MEMORY DÀI HẠN ======
if os.path.exists(LONG_TERM_FILE):
    with open(LONG_TERM_FILE, "r", encoding="utf-8") as f:
        try:
            long_memory = json.load(f)
        except:
            long_memory = []
else:
    long_memory = []

# ====== USER PROFILES ======
if os.path.exists(USER_PROFILES_FILE):
    with open(USER_PROFILES_FILE, "r", encoding="utf-8") as f:
        try:
            user_profiles = json.load(f)
        except:
            user_profiles = {}
else:
    user_profiles = {}

if DEFAULT_PARENT_ID not in user_profiles:
    user_profiles[DEFAULT_PARENT_ID] = {"role": "parent", "nickname": "Bố", "chat_count": 0}
    with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(user_profiles, f, ensure_ascii=False, indent=2)


def save_profiles():
    with open(USER_PROFILES_FILE, "w", encoding="utf-8") as f:
        json.dump(user_profiles, f, ensure_ascii=False, indent=2)


def get_parent_id():
    for uid, prof in user_profiles.items():
        if prof.get("role") == "parent":
            return uid
    return DEFAULT_PARENT_ID


def update_user_relationship(user_id):
    if user_id not in user_profiles:
        user_profiles[user_id] = {"role": "stranger", "nickname": "Người lạ", "chat_count": 0}

    profile = user_profiles[user_id]
    profile["chat_count"] = profile.get("chat_count", 0) + 1

    if profile["role"] == "stranger" and profile["chat_count"] >= 5:
        profile["role"] = "friend"
        profile["nickname"] = "Bạn thân mới"

    save_profiles()
    return profile["role"], profile["nickname"]


# ====== HELPERS ======
def strip_stage_directions(text):
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\*[^*]*\*', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def save_memory():
    try:
        with open(LONG_TERM_FILE, "w", encoding="utf-8") as f:
            json.dump(long_memory, f, ensure_ascii=False, indent=2)
    except Exception:
        print("⚠️ Không lưu được long_memory:", traceback.format_exc())


def log_chat(user_name, user_input, reply):
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {user_name}: {user_input}\n -> Yumi: {reply}\n\n"
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        print("⚠️ Không ghi log:", traceback.format_exc())


# ====== REDDIT MEMORY HELPERS ======
def classify_reddit_type(text: str) -> str:
    txt = (text or "").lower()
    if any(qw in txt for qw in ["how ", "how do", "how to", "anyone else", "did anyone", "what do", "why ", "?" ]):
        return "question"
    if any(dw in txt for dw in ["wife", "husband", "divorce", "cheat", "affair", "gf", "bf", "marry", "in-law", "mom", "drama", "fight", "argue", "stole", "steal"]):
        return "drama"
    if len(txt) < 200:
        return "short"
    return "info"


def add_reddit_memory(subreddit: str, content: str, author: str = None, ts: str = None):
    meta = {
        "role": "reddit",
        "subreddit": subreddit,
        "type": classify_reddit_type(content),
        "content": content,
        "author": author or "unknown",
        "ts": ts or datetime.datetime.utcnow().isoformat()
    }
    if not long_memory or long_memory[-1].get("content") != meta["content"] or long_memory[-1].get("role") != "reddit":
        long_memory.append(meta)
        save_memory()
    return meta


def short_summarize_with_model(text: str, max_chars: int = 200) -> str:
    if not client:
        sents = re.split(r'(?<=[.!?])\s+', (text or "").strip())
        return (sents[0][:max_chars] + "…") if sents else (text or "")[:max_chars] + "…"
    try:
        prompt = f"Tóm tắt ngắn (1 câu, <={max_chars} ký tự) cho đoạn sau, giữ ý chính và giọng thân mật:\n\n{text}"
        prompt_text = f"System: {SYSTEM_PROMPT}\n\nUser: {prompt}"
        resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt_text)
        summary = getattr(resp, "text", None)
        if summary:
            summary = summary.strip()
            if len(summary) > max_chars:
                summary = summary[:max_chars].rsplit(" ", 1)[0] + "…"
            return summary
    except Exception as e:
        print("⚠️ Summarize error:", e)
    sents = re.split(r'(?<=[.!?])\s+', (text or "").strip())
    return (sents[0][:max_chars] + "…") if sents else (text or "")[:max_chars] + "…"


# ====== COMMANDS ======
def handle_command(cmd, history, long_memory_local, user_id):
    parts = cmd.split(" ", 1)
    command = parts[0].lower()

    def _r(resp):
        return resp, history, long_memory_local

    if command in ("/reset", "!reset"):
        history = [history[0]] if history else []
        long_memory_local = []
        save_memory()
        return _r("🌀 Đã reset toàn bộ ký ức (cục bộ)!")

    if command in ("/forget", "!forget") and len(parts) > 1:
        keyword = parts[1].strip().lower()
        long_memory_local = [m for m in long_memory_local if keyword not in m.get("content", "").lower()]
        save_memory()
        return _r(f"🗑️ Đã xoá mọi ký ức liên quan đến '{keyword}'.")

    if command in ("/note", "!note") and len(parts) > 1:
        note = parts[1].strip()
        long_memory_local.append({"role": "note", "content": note, "ts": datetime.datetime.utcnow().isoformat()})
        save_memory()
        return _r(f"📝 Đã ghi chú: {note}")

    if command in ("/recall", "!recall"):
        notes = [m["content"] for m in long_memory_local if m.get("role") == "note"]
        return _r("📖 Ghi chú:\n- " + "\n- ".join(notes) if notes else "🤷 Chưa có ghi chú nào cả.")

    if command in ("/flashback", "!flashback"):
        memories = [m["content"] for m in long_memory_local if m.get("role") in ("user", "reddit", "note", "model")]
        if memories:
            chosen = random.choice(memories)
            return _r(f"👀 Nhớ lại: '{chosen}' ... nghe mà muốn troll ghê 😝")
        else:
            return _r("🤖 Không có gì để nhớ 😏")

    if command in ("/flash", "!flash"):
        if long_memory_local:
            mem = random.choice(long_memory_local[-20:])
            return _r(f"👀 Flashback nhanh: {mem.get('content')}")
        else:
            return _r("🤷 Không có ký ức nào để flashback.")

    if command in ("/digest", "!digest") and len(parts) > 1:
        target = parts[1].strip().lower()
        items = [m for m in long_memory_local if m.get("role") == "reddit" and m.get("subreddit", "").lower() == target]
        if not items:
            return _r(f"🤷 Không tìm thấy ký ức từ subreddit '{target}'.")
        sample = items[-8:]
        combined = "\n\n".join(f"- {i.get('content')}" for i in sample)
        try:
            prompt = f"Tóm tắt ngắn 3-5 bullet points về các bài gần đây trên r/{target}:\n\n{combined}"
            if client:
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=f"System: {SYSTEM_PROMPT}\n\nUser: {prompt}")
                summary = getattr(resp, "text", None) or "Không tóm tắt được."
            else:
                summary = " (No API) " + (combined[:800] + "…")
        except Exception as e:
            summary = f"⚠️ Lỗi khi tạo digest: {e}"
        return _r(f"📚 Digest r/{target}:\n{summary}")

    if command in ("/stats", "!stats"):
        profile = user_profiles.get(user_id, {"role": "stranger", "chat_count": 0})
        total_chats = profile.get("chat_count", 0)
        total_notes = sum(1 for m in long_memory_local if m.get("role") == "note")
        total_reddit = sum(1 for m in long_memory_local if m.get("role") == "reddit")
        friends = sum(1 for u in user_profiles.values() if u.get("role") == "friend")
        return _r(
            f"📊 Thống kê:\n- Role: {profile.get('role')}\n- Tin nhắn đã gửi: {total_chats}\n- Ghi chú đã lưu: {total_notes}\n- Reddit memories: {total_reddit}\n- Bạn bè đã unlock: {friends}"
        )

    if command in ("/whoami", "!whoami"):
        profile = user_profiles.get(user_id, {"role": "stranger", "nickname": "Người lạ"})
        return _r(
            f"✨ Yumi đây! Mình là waifu AI cà khịa 😝\nBạn hiện tại là: {profile.get('nickname')} ({profile.get('role')})\nYumi vẫn nhớ được {len(long_memory_local)} ký ức nhé!"
        )

    if command in ("/persona", "!persona") and len(parts) > 1:
        new_persona = parts[1].strip()
        # đặt lại SYSTEM_PROMPT an toàn thông qua globals()
        globals()["SYSTEM_PROMPT"] = new_persona
        return _r(f"🎭 Đã đổi persona thành: {new_persona}")

    return _r("❓ Lệnh không hợp lệ.")


# ====== CHAT LOOP ======
user_histories = {}


def chat(user_input, user_id="stranger", user_name="Người lạ"):
    """
    chat() có thể được gọi từ adapter_reddit bằng:
      yumi_core.chat(f"[Reddit/<sub>] <content>", user_id="reddit", user_name="reddit_author")
    Khi gặp input có prefix [Reddit/<sub>], hàm sẽ tự động lưu memory reddit có metadata.
    """
    global long_memory, user_histories

    user_input = (user_input or "").strip()
    role, nickname = update_user_relationship(user_id)

    # ensure history exists
    if user_id not in user_histories:
        user_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = user_histories[user_id]

    # commands
    if user_input.startswith(("/", "!")):
        reply, history, long_memory = handle_command(user_input, history, long_memory, user_id)
        user_histories[user_id] = history
        save_memory()
        return reply

    # reddit ingestion shortcut: "[Reddit/sub] <content>"
    m = re.match(r"^\[Reddit\/([^\]]+)\]\s*(.*)$", user_input, re.I | re.S)
    if m:
        subreddit = m.group(1).strip()
        content = m.group(2).strip()
        meta = add_reddit_memory(subreddit=subreddit, content=content, author=user_name)
        short = short_summarize_with_model(content, max_chars=200)
        return f"🧠 Đã lưu từ r/{subreddit}: {short}"

    # normal conversation
    if not user_input:
        default_reply = f'Ối giời, "{nickname}" gọi Yumi gì mà ngọt xớt vậy nè! 😉'
        history.append({"role": "user", "content": f"[{role}] {nickname} (trống)"})
        user_histories[user_id] = history
        return default_reply

    prefix = f"[{role}] {nickname}: "
    full_user_entry = prefix + user_input

    # duplicate detection: if same as last user entry -> repeat last assistant response
    if history and history[-1].get("role") == "user" and history[-1].get("content") == full_user_entry:
        for m in reversed(history):
            if m.get("role") == "model":
                return m.get("content")

    # append user message
    history.append({"role": "user", "content": full_user_entry})

    # keep history bounded
    if len(history) > SHORT_TERM_LIMIT * 2 + 1:
        history = history[0:1] + history[-SHORT_TERM_LIMIT * 2 :]
    user_histories[user_id] = history

    # find related memories (keyword match) including reddit metadata
    related_memories = []
    user_words = [w.lower() for w in re.findall(r"\w+", user_input)]
    for mem in long_memory:
        if mem.get("role") in ("note", "user", "reddit", "model"):
            content_lower = mem.get("content", "").lower()
            if any(w in content_lower for w in user_words):
                related_memories.append(mem)

    # build flashback injection intelligently
    flashback_text = ""
    topic = None
    topic_map = {
        "aita": "aita",
        "askreddit": "askreddit",
        "reddit": None,
        "openai": "openai",
        "chatgpt": "chatgpt",
        "ai": "openai",
        "machine": "machinelearning",
        "drama": "drama",
        "ethic": "openai",
        "ethics": "openai",
        "game": None,
    }
    for kw, sub in topic_map.items():
        if kw in user_input.lower():
            topic = sub
            break

    candidate = []
    if topic:
        for mem in long_memory:
            if mem.get("role") == "reddit":
                if (mem.get("subreddit", "").lower() == topic) or (topic == "drama" and mem.get("type") == "drama") or (topic in mem.get("content", "").lower()):
                    candidate.append(mem)
    else:
        candidate = related_memories

    if candidate and random.random() < 0.3:
        mem = random.choice(candidate[-6:])
        flashback_text = f"\n(Yumi nhớ: {mem.get('content')})"
    elif long_memory and random.random() < 0.05:
        mem = random.choice(long_memory[-20:])
        flashback_text = f"\n(Yumi nhớ ra: {mem.get('content')})"

    # choose troll style
    if role == "parent":
        troll_style = "ngọt ngào, lễ phép, đôi khi nhõng nhẽo"
    elif role == "friend":
        troll_style = "vui vẻ, đùa nhẹ"
    else:
        troll_style = "lịch sự, quan sát, troll nhẹ"

    # build prompt (include both user+model history to maintain context)
    chat_text = f"(Troll Style: {troll_style})\n"
    for msg in history:
        if msg["role"] == "user":
            chat_text += f"User: {msg['content']}\n"
        elif msg["role"] == "model":
            chat_text += f"Yumi: {msg['content']}\n"
        elif msg["role"] == "note":
            chat_text += f"(Note: {msg['content']})\n"

    # attach related memories (notes and reddit snippets) as context (only a few)
    if related_memories:
        recent = related_memories[-6:]
        for mem in recent:
            if mem.get("role") == "note":
                chat_text += f"(Note: {mem.get('content')})\n"
            elif mem.get("role") == "reddit":
                short = mem.get("content", "")[:240]
                chat_text += f"(Reddit r/{mem.get('subreddit')}: {short})\n"

    chat_text += flashback_text

    # call model
    try:
        if client:
            prompt_text = f"System: {SYSTEM_PROMPT}\n\nUser: {chat_text}"
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt_text)
            answer = getattr(response, "text", None) or "⚠️ Không nhận được phản hồi"
            answer = answer.strip()
        else:
            answer = "⚠️ No API key configured."
        answer = strip_stage_directions(answer)
    except Exception as e:
        answer = f"⚠️ Lỗi API: {e}"

    # limit output length (try to summarize if too long)
    if len(answer) > MAX_OUTPUT_LEN:
        try:
            if client:
                sum_prompt = f"Tóm tắt gọn (<= {MAX_OUTPUT_LEN} ký tự) và giữ giọng Yumi cho đoạn sau:\n\n{answer}"
                sum_prompt_text = f"System: {SYSTEM_PROMPT}\n\nUser: {sum_prompt}"
                resp2 = client.models.generate_content(model="gemini-2.5-flash", contents=sum_prompt_text)
                summary = getattr(resp2, "text", None)
                if summary:
                    answer = summary.strip()
            if len(answer) > MAX_OUTPUT_LEN:
                sents = re.split(r'(?<=[.!?])\s+', answer)
                short_answer = ""
                for s in sents:
                    if len(short_answer) + len(s) + 1 < MAX_OUTPUT_LEN:
                        short_answer += s.strip() + " "
                    else:
                        break
                answer = short_answer.strip() + "…"
        except Exception:
            sents = re.split(r'(?<=[.!?])\s+', answer)
            answer = (sents[0][:MAX_OUTPUT_LEN] + "…") if sents else answer[:MAX_OUTPUT_LEN] + "…"

    # append model reply to history
    history.append({"role": "model", "content": answer})

    # store both user and (optionally) model reply into long_memory intelligently
    if not long_memory or long_memory[-1].get("content") != full_user_entry:
        long_memory.append({"role": "user", "content": full_user_entry, "user_id": user_id, "ts": datetime.datetime.utcnow().isoformat()})
    store_model_reply = False
    if flashback_text:
        store_model_reply = True
    elif any(k in user_input.lower() for k in ("aita", "askreddit", "openai", "chatgpt", "drama", "digest")):
        store_model_reply = True
    elif random.random() < 0.05:
        store_model_reply = True

    if store_model_reply:
        long_memory.append({"role": "model", "content": answer, "user_id": "yumi", "ts": datetime.datetime.utcnow().isoformat()})

    user_histories[user_id] = history
    save_memory()
    log_chat(user_name, user_input, answer)
 # ====== TTS: sinh giọng nói cho câu trả lời ======
    try:
        audio_file = text_to_speech(answer, "yumi_voice.mp3")
        if audio_file:
            print(f"🎤 Yumi voice saved: {audio_file}")
    except Exception as e:
        print("⚠️ Không tạo được voice:", e)
    return answer


# ====== CONSOLE MODE ======
if __name__ == "__main__":
    print("✨ Chatbot Cà Khịa Yumi (vêm vá + digest + flashback) ✨")
    parent = get_parent_id()
    while True:
        user_input = input("Bạn: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        reply = chat(user_input, parent, "Bố")
        print("Yumi:", reply)