#!/usr/bin/env python3
"""
把 explanations.json（explain.py 產生的進度）合併進 bank.json 與 bank.js。
可以在解析還沒全部跑完時就先執行一次，之後隨時可以重跑套用最新進度。
"""
import json, os

BANK_FILE = "bank.json"
BANK_JS_FILE = "bank.js"
OUT_FILE = "explanations.json"

def main():
    with open(BANK_FILE, encoding="utf-8") as f:
        bank = json.load(f)
    if not os.path.exists(OUT_FILE):
        print(f"找不到 {OUT_FILE}，請先執行 explain.py 產生解析")
        return
    with open(OUT_FILE, encoding="utf-8") as f:
        expl = json.load(f)

    applied = 0
    for q in bank:
        if q["id"] in expl:
            if q.get("expl") != expl[q["id"]]:
                applied += 1
            q["expl"] = expl[q["id"]]

    with open(BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False)

    with open(BANK_JS_FILE, "w", encoding="utf-8") as f:
        f.write("window.BANK_DATA=")
        json.dump(bank, f, ensure_ascii=False)
        f.write(";")

    with_expl = sum(1 for q in bank if q.get("expl"))
    print(f"合併完成：新套用/更新 {applied} 題，bank.json 目前共有 {with_expl} 題含解析（共 {len(bank)} 題）")
    print("bank.json 與 bank.js 已更新，重新部署（拖 zip 到 Netlify）即可上線。")

if __name__ == "__main__":
    main()
