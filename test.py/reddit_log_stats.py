# reddit_log_stats.py
import re
import datetime
import matplotlib.pyplot as plt
from collections import defaultdict

def parse_log_file(filename="reddit_learn_logs.txt"):
    stats = defaultdict(lambda: {"EN": 0, "VN": 0})
    pattern = re.compile(r"^\[(.*?)\].*\[(EN|VN)\]")

    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            match = pattern.search(line)
            if match:
                ts_str, lang = match.groups()
                try:
                    ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                    date = ts.date()
                    stats[date][lang] += 1
                except Exception:
                    continue
    return stats

def plot_stats(stats):
    dates = sorted(stats.keys())
    en_counts = [stats[d]["EN"] for d in dates]
    vn_counts = [stats[d]["VN"] for d in dates]

    plt.figure(figsize=(10,5))
    plt.plot(dates, en_counts, marker="o", label="EN notes")
    plt.plot(dates, vn_counts, marker="s", label="VN notes")
    plt.title("📊 Yumi học trên Reddit (EN vs VN theo ngày)")
    plt.xlabel("Ngày")
    plt.ylabel("Số lượng notes")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    stats = parse_log_file()
    if not stats:
        print("⚠️ Chưa có dữ liệu trong reddit_learn_logs.txt")
    else:
        plot_stats(stats)