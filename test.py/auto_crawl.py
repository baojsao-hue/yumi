# auto_crawl.py
import praw
import yumi_core
import datetime
import time
import re

# ========= REDDIT CONFIG =========
CLIENT_ID = "tr2ytH2fI9Mw6Y5ReoDb2Q"
CLIENT_SECRET = "fE-4r4SaX96dzHhr9lqX3vZAC6EbIQ"
REFRESH_TOKEN = "196487001934098-ZmJx_JRHpigRu6u-zTmsRnyw82un4Q"
USER_AGENT = "YumiAI Learner (by u/Yumipro)"   # đổi YOUR_USERNAME

# ========= INIT REDDIT CLIENT =========
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
    user_agent=USER_AGENT,
)

print(f"✅ Auto-crawl login thành công dưới user: {reddit.user.me()}")

# ========= SUBREDDIT TARGET =========
AI_SUBS = ["ChatGPT", "OpenAI", "artificial", "MachineLearning", "genai"]
FUN_SUBS = ["AskReddit", "AITA", "funny", "ChangeMyView"]

# ========= ANTI-REPEAT =========
handled_ids = set()

# ========= DAILY STATS =========
stats = {"EN": 0, "VN": 0}
current_day = datetime.date.today()

# ========= DETECT LANGUAGE =========
def detect_language(text: str) -> str:
    if re.search(r"[àáạảãâầấậẩẫăằắặẳẵđèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]", text.lower()):
        return "VN"
    return "EN"

# ========= LOGGING =========
def log_memory(user, text, note, is_post=False):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kind = "📌 Post" if is_post else "💬 Comment"
    log_text = f"[{ts}] {kind} by {user}\n  ❯ Input: {text}\n  ❯ 🧠 Lưu vào memory: {note}\n\n"
    print(log_text)
    with open("reddit_crawl_logs.txt", "a", encoding="utf-8") as f:
        f.write(log_text)

# ========= TÓM TẮT =========
def summarize_text(text: str, max_len=400) -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    try:
        summary = yumi_core.chat(
            f"Tóm tắt ngắn gọn nội dung sau (giữ nguyên ngôn ngữ gốc): {text[:1500]}",
            user_id="system_summarizer",
            user_name="Summarizer"
        )
        return summary
    except Exception:
        return text[:max_len] + "..."

# ========= AUTO CRAWL =========
def auto_crawl_reddit(subs, ca_label, limit=5):
    global stats
    subreddits = reddit.subreddit("+".join(subs))
    print(f"🧠 Yumi đang học {ca_label} từ subreddit: {', '.join(subs)}")

    for submission in subreddits.new(limit=limit):
        if submission.id in handled_ids:
            continue
        handled_ids.add(submission.id)

        author = str(submission.author)
        if "automoderator" in author.lower():
            continue

        raw_text = submission.title + "\n" + (submission.selftext or "")
        lang = detect_language(raw_text)
        text = summarize_text(raw_text)

        note = f"[{ca_label}] [{lang}] [RedditPost] {author}: {text}"
        yumi_core.chat(f"!note {note}", user_id=author, user_name=author)
        log_memory(author, raw_text, note, is_post=True)
        stats[lang] += 1

        submission.comments.replace_more(limit=0)
        for comment in submission.comments[:3]:
            if comment.id in handled_ids:
                continue
            handled_ids.add(comment.id)

            c_author = str(comment.author)
            if "automoderator" in c_author.lower():
                continue

            raw_comment = comment.body.strip()
            lang = detect_language(raw_comment)
            c_text = summarize_text(raw_comment, max_len=200)

            note = f"[{ca_label}] [{lang}] [RedditComment] {c_author}: {c_text}"
            yumi_core.chat(f"!note {note}", user_id=c_author, user_name=c_author)
            log_memory(c_author, raw_comment, note, is_post=False)
            stats[lang] += 1

# ========= DAILY REPORT =========
def check_daily_report():
    global stats, current_day
    today = datetime.date.today()
    if today != current_day:
        # in báo cáo
        report = f"📊 Báo cáo ngày {current_day}:\n  ❯ Note EN: {stats['EN']}\n  ❯ Note VN: {stats['VN']}\n  ❯ Tổng: {stats['EN']+stats['VN']}\n"
        print(report)
        with open("reddit_crawl_logs.txt", "a", encoding="utf-8") as f:
            f.write(report + "\n")

        # reset
        stats = {"EN": 0, "VN": 0}
        current_day = today

# ========= LOOP =========
if __name__ == "__main__":
    while True:
        try:
            hour = datetime.datetime.now().hour
            if 8 <= hour < 20:
                auto_crawl_reddit(AI_SUBS, ca_label="Ca học: AI ban ngày", limit=5)
            else:
                auto_crawl_reddit(FUN_SUBS, ca_label="Ca học: Drama ban đêm", limit=5)

            check_daily_report()
            time.sleep(180)
        except Exception as e:
            print(f"⚠️ Lỗi ngoài vòng lặp chính: {e}")
            time.sleep(60)