#!/usr/bin/env python3
"""
批次為保險考古題產生 AI 解析（explanations）。

用法：
  1. 設定環境變數 OPENROUTER_API_KEY（或直接編輯下面 API_KEY 變數）
  2. 執行： python3 explain.py
     - 只處理 bank.json 裡 year in TARGET_YEARS 且尚未有 expl 的題目
     - 每完成 CHECKPOINT_EVERY 題會存一次進度到 explanations.json
     - 中斷後重新執行會自動跳過已完成的題目（斷點續跑）
  3. 全部跑完（或跑到一半想先套用）後執行： python3 merge.py
     - 會把 explanations.json 合併進 bank.json / bank.js

注意：此腳本需要能連上 https://openrouter.ai，
      請在有正常網路的電腦/終端機上執行（不要在受限沙盒環境跑）。
"""
import json, os, sys, time, threading
import urllib.request, urllib.error

API_KEY = os.environ.get("OPENROUTER_API_KEY", "REPLACE_WITH_YOUR_KEY")
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-3.5-flash-lite")
TARGET_YEARS = {"113", "114", "115"}   # 先跑最近三年；跑完可以改成全部年份重跑
CONCURRENCY = 12
CHECKPOINT_EVERY = 20
MAX_RETRIES = 4

BANK_FILE = "bank.json"
OUT_FILE = "explanations.json"

lock = threading.Lock()

def load_bank():
    with open(BANK_FILE, encoding="utf-8") as f:
        return json.load(f)

def load_progress():
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_progress(progress):
    tmp = OUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=0)
    os.replace(tmp, OUT_FILE)

def build_prompt(q):
    opts = "\n".join(q["options"])
    return (
        f"題目：{q['q']}\n選項：\n{opts}\n正確答案：{q['ans']}。\n"
        "你是保險證照考試名師。直接用繁體中文輸出80-150字解析："
        "說明正確答案依據（若能引用法規條號請引用），"
        "並一句話點出最主要錯誤選項的問題所在。不要輸出思考過程、不要開場白、不要條列。"
    )

def call_openrouter(prompt):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 350,
        "reasoning": {"enabled": False},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()

def worker(q, progress, counter, total):
    qid = q["id"]
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            text = call_openrouter(build_prompt(q))
            if not text or len(text) < 10:
                raise ValueError(f"empty/too-short output: {text!r}")
            with lock:
                progress[qid] = text
                counter[0] += 1
                if counter[0] % CHECKPOINT_EVERY == 0:
                    save_progress(progress)
                print(f"[{counter[0]}/{total}] {qid} ok", flush=True)
            return
        except urllib.error.HTTPError as e:
            wait = min(30, 2 ** attempt)
            print(f"[retry {attempt}] {qid} HTTP {e.code}, wait {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            wait = min(30, 2 ** attempt)
            print(f"[retry {attempt}] {qid} error: {e}, wait {wait}s", flush=True)
            time.sleep(wait)
    with lock:
        print(f"[FAILED] {qid} gave up after {MAX_RETRIES} retries", flush=True)

def main():
    if API_KEY == "REPLACE_WITH_YOUR_KEY":
        print("請先設定 OPENROUTER_API_KEY 環境變數，或編輯本檔案內的 API_KEY", file=sys.stderr)
        sys.exit(1)

    bank = load_bank()
    progress = load_progress()

    todo = [q for q in bank if q["year"] in TARGET_YEARS and q["id"] not in progress]
    total_target = len([q for q in bank if q["year"] in TARGET_YEARS])
    print(f"目標年度共 {total_target} 題，已完成 {len(progress)} 題，本次待處理 {len(todo)} 題")
    if not todo:
        print("全部完成！可以執行 python3 merge.py 套用進 bank.json / bank.js")
        return

    counter = [len(progress)]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futures = [ex.submit(worker, q, progress, counter, total_target) for q in todo]
        for f in futures:
            f.result()

    save_progress(progress)
    print(f"本輪結束，共完成 {len(progress)} / {total_target} 題")
    print("執行 python3 merge.py 套用進 bank.json / bank.js")

if __name__ == "__main__":
    main()
