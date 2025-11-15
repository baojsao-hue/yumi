# adapter_reddit.py
import praw
import yumi_core
import datetime
import time
import random

# ========= REDDIT CONFIG =========
CLIENT_ID = ""
CLIENT_SECRET = ""
REFRESH_TOKEN = ""
USER_AGENT = ""   # nhớ thay username thật của bạn

# ========= INIT REDDIT CLIENT =========
reddit = praw.Reddit(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    refresh_token=REFRESH_TOKEN,
    user_agent=USER_AGENT,
)

# ========= SUBREDDIT TARGET =========
TARGET_SUBREDDITS = [
    "ChatGPT",
    "OpenAI",
    "artificial",
    "MachineLearning",
    "AskReddit",
    "AITA",
    "funny"
]

# ========= ANTI-REPEAT =========
handled_ids = set()
last_reply_time = {}

# ========= LOGGING =========
def log_dialogue(user, text, reply, subreddit, is_post=False, learn_only=False):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    kind = "📌 Post" if is_post else "💬 Comment"
    action = "🧠 Học thêm" if learn_only else "↩️ Trả lời"
    log_text = (
        f"[{ts}] {kind} in r/{subreddit} by {user}\n"
        f"  ❯ Input: {text}\n"
        f"  ❯ {action}: {reply}\n\n"
    )
    print(log_text)
    with open("reddit_logs.txt", "a", encoding="utf-8") as f:
        f.write(log_text)

# ========= EMOJI FLAVOR =========
EMOJIS = ["😝", "✨", "💀", "👀", "🔥", "🤖", "💖"]

def random_emoji():
    return random.choice(EMOJIS)

# ========= RÚT GỌN =========
def format_reply(reply: str, author: str, max_len=400) -> str:
    if not reply:
        return ""

    now = time.time()
    if author in last_reply_time and now - last_reply_time[author] < 120:
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

# ========= MAIN LOOP =========
def run_reddit_bot():
    print(f"✅ Đăng nhập Reddit thành công dưới user: {reddit.user.me()}")
    print(f"👀 Đang theo dõi subreddit: {', '.join(TARGET_SUBREDDITS)}")

    while True:
        try:
            for sub in TARGET_SUBREDDITS:
                subreddit = reddit.subreddit(sub)

                for submission in subreddit.new(limit=3):
                    if submission.id in handled_ids:
                        continue
                    handled_ids.add(submission.id)

                    text = submission.title + "\n" + (submission.selftext[:500] or "")
                    mode = "learn"
                    if sub.lower() in ["askreddit", "aita", "funny"]:
                        mode = "reply"

                    # gọi Yumi xử lý
                    raw_reply = yumi_core.chat(
                        f"[Reddit/{sub}] {text}",
                        user_id="reddit",
                        user_name="Reddit"
                    )

                    # luôn lưu vào long_memory với metadata
                    yumi_core.long_memory.append({
                        "role": "reddit",
                        "subreddit": sub,
                        "type": "post",
                        "content": text,
                        "reply": raw_reply,
                        "ts": datetime.datetime.utcnow().isoformat()
                    })
                    yumi_core.save_memory()

                    if mode == "reply":
                        reply = format_reply(raw_reply, str(submission.author))
                        if reply:
                            try:
                                submission.reply(reply)
                                log_dialogue(
                                    str(submission.author),
                                    text,
                                    reply,
                                    subreddit=sub,
                                    is_post=True,
                                    learn_only=False
                                )
                            except Exception as e:
                                print(f"⚠️ Không thể reply: {e}")
                                log_dialogue(
                                    str(submission.author),
                                    text,
                                    raw_reply,
                                    subreddit=sub,
                                    is_post=True,
                                    learn_only=True
                                )
                        else:
                            log_dialogue(
                                str(submission.author),
                                text,
                                raw_reply,
                                subreddit=sub,
                                is_post=True,
                                learn_only=True
                            )
                    else:
                        log_dialogue(
                            str(submission.author),
                            text,
                            raw_reply,
                            subreddit=sub,
                            is_post=True,
                            learn_only=True
                        )

                    # học từ comment top
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments[:2]:
                        if comment.id in handled_ids:
                            continue
                        handled_ids.add(comment.id)

                        c_text = comment.body[:400]
                        c_reply = yumi_core.chat(
                            f"[Reddit/{sub}] Bình luận: {c_text}",
                            user_id="reddit",
                            user_name="Reddit"
                        )

                        yumi_core.long_memory.append({
                            "role": "reddit",
                            "subreddit": sub,
                            "type": "comment",
                            "content": c_text,
                            "reply": c_reply,
                            "ts": datetime.datetime.utcnow().isoformat()
                        })
                        yumi_core.save_memory()

                        log_dialogue(str(comment.author), c_text, c_reply, subreddit=sub)

            time.sleep(60)

        except Exception as e:
            print(f"⚠️ Lỗi ngoài vòng lặp chính: {e}")
            time.sleep(30)

if __name__ == "__main__":

    run_reddit_bot()
