# reddit_adapter_unified.py
import praw
import yumi_core
import datetime
import time
import random
import re
import os
from dotenv import load_dotenv
load_dotenv()

# ========= CONFIG =========
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USERNAME = os.getenv("REDDIT_USERNAME")
REDDIT_PASSWORD = os.getenv("REDDIT_PASSWORD")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) YumiUnified/0.3"

reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    username=REDDIT_USERNAME,
    password=REDDIT_PASSWORD,
    user_agent=USER_AGENT,
)

print(f"✅ Login Reddit thành công dưới user: {reddit.user.me()}")

# ========= SUBREDDIT TARGET =========
AI_SUBS = ["ChatGPT", "OpenAI", "artificial", "MachineLearning", "genai"]
FUN_SUBS = ["AskReddit", "AITA", "funny", "ChangeMyView"]

handled_ids = set()
last_reply_time = {}
stats = {"EN": 0, "VN": 0}
current_day = datetime.date.today()

EMOJIS = ["😝", "✨", "💀", "👀", "🔥", "🤖", "💖"]

def random_emoji():
    return random.choice(EMOJIS)

# ========= HELPERS =========
def detect_language(text: str) -> str:
    if re.search(r"[àáạảãâầấậẩẫăằắặẳẵđèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]", text.lower()):
        return "VN"
    return "EN"

def log_reply(user, text, reply, subreddit, lang, kind="Post"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_text = (
        f"[{ts}] 📌 {kind} reply [{lang}] in r/{subreddit} by {user}\n"
        f"  ❯ Input: {text}\n"
        f"  ❯ ↩️ Trả lời: {reply}\n\n"
    )
    print(log_text)
    with open("reddit_reply_logs.txt", "a", encoding="utf-8") as f:
        f.write(log_text)

def log_learn(user, text, reply, subreddit, lang, kind="Post"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_text = (
        f"[{ts}] 📌 {kind} learn [{lang}] in r/{subreddit} by {user}\n"
        f"  ❯ Input: {text}\n"
        f"  ❯ 🧠 Học thêm: {reply}\n\n"
    )
    print(log_text)
    with open("reddit_learn_logs.txt", "a", encoding="utf-8") as f:
        f.write(log_text)

def format_reply(reply: str, author: str, max_len=400) -> str:
    """Rút gọn + tránh spam cùng user"""
    if not reply:
        return ""

    now = time.time()
    if author in last_reply_time and now - last_reply_time[author] < 300:
        return ""
    last_reply_time[author] = now

    style_roll = random.random()
    public_reply = reply

    if style_roll < 0.7:
        sentences = reply.split(".")
        if sentences:
            public_reply = sentences[0][:max_len] + f" {random_emoji()}"
    else:
        if len(reply) > max_len:
            public_reply = reply[:max_len] + "… (Yumi log full 😉)"

    if random.random() < 0.2:
        public_reply += " —Yumi 💖"

    return public_reply

def summarize_text(text: str, max_len=400) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    try:
        summary = yumi_core.chat(
            f"Tóm tắt ngắn gọn nội dung sau (giữ nguyên ngôn ngữ gốc): {text[:1200]}",
            user_id="system_summarizer",
            user_name="Summarizer"
        )
        return summary
    except Exception:
        return text[:max_len] + "..."

def check_daily_report():
    global stats, current_day
    today = datetime.date.today()
    if today != current_day:
        report = f"📊 Báo cáo ngày {current_day}:\n  ❯ EN notes: {stats['EN']}\n  ❯ VN notes: {stats['VN']}\n  ❯ Tổng: {stats['EN']+stats['VN']}\n"
        print(report)
        with open("reddit_learn_logs.txt", "a", encoding="utf-8") as f:
            f.write(report + "\n")
        stats = {"EN": 0, "VN": 0}
        current_day = today

# ========= MAIN LOOP =========
def run_unified_bot():
    print("👀 Bắt đầu hợp thể: vừa học vừa reply (log riêng + flag ngôn ngữ)")

    while True:
        try:
            hour = datetime.datetime.now().hour
            subs = AI_SUBS if (8 <= hour < 20) else FUN_SUBS
            sub_mode = "AI ban ngày" if (8 <= hour < 20) else "Drama ban đêm"

            subreddits = reddit.subreddit("+".join(subs))
            print(f"🧠 Yumi đang học {sub_mode} từ: {', '.join(subs)}")

            for submission in subreddits.new(limit=3):
                if submission.id in handled_ids:
                    continue
                handled_ids.add(submission.id)

                text = submission.title + "\n" + (submission.selftext[:500] or "")
                lang = detect_language(text)

                raw_reply = yumi_core.chat(f"[Reddit/{submission.subreddit}] {text}",
                                           user_id="reddit", user_name="Reddit")

                yumi_core.long_memory.append({
                    "role": "reddit",
                    "subreddit": str(submission.subreddit),
                    "type": "post",
                    "content": text,
                    "reply": raw_reply,
                    "ts": datetime.datetime.utcnow().isoformat()
                })
                yumi_core.save_memory()
                stats[lang] += 1

                # FUN_SUBS → reply
                if submission.subreddit.display_name.lower() in ["askreddit", "aita", "funny"]:
                    reply = format_reply(raw_reply, str(submission.author))
                    if reply:
                        try:
                            submission.reply(reply)
                            log_reply(str(submission.author), text, reply, str(submission.subreddit), lang, kind="Post")
                            time.sleep(60)
                        except Exception as e:
                            print(f"⚠️ Không thể reply: {e}")
                            log_learn(str(submission.author), text, raw_reply, str(submission.subreddit), lang, kind="Post")
                    else:
                        log_learn(str(submission.author), text, raw_reply, str(submission.subreddit), lang, kind="Post")
                else:
                    log_learn(str(submission.author), text, raw_reply, str(submission.subreddit), lang, kind="Post")

                # Học từ top comment
                submission.comments.replace_more(limit=0)
                for comment in submission.comments[:2]:
                    if comment.id in handled_ids:
                        continue
                    handled_ids.add(comment.id)

                    c_text = comment.body[:400]
                    lang = detect_language(c_text)
                    c_reply = yumi_core.chat(f"[Reddit/{submission.subreddit}] Bình luận: {c_text}",
                                             user_id="reddit", user_name="Reddit")

                    yumi_core.long_memory.append({
                        "role": "reddit",
                        "subreddit": str(submission.subreddit),
                        "type": "comment",
                        "content": c_text,
                        "reply": c_reply,
                        "ts": datetime.datetime.utcnow().isoformat()
                    })
                    yumi_core.save_memory()
                    stats[lang] += 1
                    log_learn(str(comment.author), c_text, c_reply, str(submission.subreddit), lang, kind="Comment")

                    time.sleep(10)

            check_daily_report()
            time.sleep(180)

        except Exception as e:
            err = str(e).lower()
            if "429" in err or "ratelimit" in err:
                print("🛑 Reddit bóp cổ (429/RATELIMIT)! Nghỉ 15 phút...")
                time.sleep(900)
            else:
                print(f"⚠️ Lỗi ngoài vòng lặp chính: {e}")
                time.sleep(60)

if __name__ == "__main__":
    run_unified_bot()