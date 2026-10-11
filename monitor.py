"""界タビ20's availability monitor (starter; booking-page detector is unverified).

Reads direct booking-result URLs from BOOKING_URLS_JSON. It deliberately fails closed:
unknown pages are reported as UNKNOWN, never treated as available.
"""
from __future__ import annotations
import json, os, re, smtplib, sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DATE = os.getenv("STAY_DATE", "2026-11-10")
RECIPIENT = os.getenv("NOTIFY_TO", "newyork.yuto.19980403@gmail.com")
STATE_FILE = Path("state.json")
CAMPAIGN = "https://hoshinoresorts.com/jp/sp/kaitabi20s/"
# FAQ text quoted by Hoshino Resorts for the sold-out dialog.
SOLD_OUT = ["誠に恐れ入りますが、満室となっております", "満室となっております", "空室がありません", "空室なし", "ご希望の日程ではご予約いただけません"]
# These are intentionally conservative generic signals; validate them against each page before relying on alerts.
AVAILABLE = ["空室あり", "空室がございます", "予約へ進む", "このプランを予約", "予約する", "空室検索結果"]
PLAN_TERMS = ["界タビ20s", "界タビ20’s", "界タビ20's"]

def load_urls():
    raw = os.getenv("BOOKING_URLS_JSON", "[]")
    try:
        urls = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(f"BOOKING_URLS_JSON must be a JSON array of direct booking-result URLs: {e}")
    if not isinstance(urls, list) or not urls:
        raise SystemExit("BOOKING_URLS_JSON is empty. Add direct official booking-result URLs for eligible Kanto/Chubu properties after manually setting the stay date and plan.")
    out = []
    for item in urls:
        if not isinstance(item, dict) or not item.get("name") or not item.get("url"):
            raise SystemExit("Each BOOKING_URLS_JSON item must have name and url keys")
        u = urlparse(item["url"])
        if u.scheme != "https" or not u.netloc.endswith("hoshinoresorts.com"):
            raise SystemExit(f"Only HTTPS hoshinoresorts.com URLs accepted: {item.get('url')}")
        out.append({"name": item["name"], "url": item["url"]})
    return out

def classify(text: str):
    normalized = re.sub(r"\s+", " ", text)
    if any(s in normalized for s in SOLD_OUT):
        return "UNAVAILABLE", "official sold-out wording detected"
    has_plan = any(term in normalized for term in PLAN_TERMS)
    hits = [s for s in AVAILABLE if s in normalized]
    if has_plan and hits:
        return "POSSIBLE_AVAILABLE", "plan wording and generic availability/action wording detected: " + ", ".join(hits)
    return "UNKNOWN", "no validated availability signal; page may have changed or require interaction"

def send_email(subject, body):
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ["EMAIL_FROM"]
    msg = EmailMessage(); msg["From"] = sender; msg["To"] = RECIPIENT; msg["Subject"] = subject; msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls(); server.login(user, password); server.send_message(msg)

def main():
    urls = load_urls()
    old = json.loads(STATE_FILE.read_text("utf-8")) if STATE_FILE.exists() else {}
    new = {"checked_at": datetime.now(timezone.utc).isoformat(), "stay_date": DATE, "results": {}}
    found = []
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(locale="ja-JP", timezone_id="Asia/Tokyo")
        for target in urls:
            try:
                response = page.goto(target["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2500)  # modest wait for client-side text; do not hammer the site
                text = page.locator("body").inner_text(timeout=15000)
                # 読み取り結果の調査用ログ
　　　　　　　　　　　print(f"[DEBUG] Facility: {target['name']}")
　　　　　　　　　　　print(f"[DEBUG] Page title: {page.title()}")
　　　　　　　　　　　print(f"[DEBUG] Page URL: {page.url}")
　　　　　　　　　　　print(f"[DEBUG] Text length: {len(text)}")
　　　　　　　　　　　print(f"[DEBUG] Target date: {DATE}")
　　　　　　　　　　　
　　　　　　　　　　　status, reason = classify(text)
　　　　　　　　　　　print(f"[DEBUG] Classification: {status}")
　　　　　　　　　　　print(f"[DEBUG] Reason: {reason}")

                # Keep evidence short for diagnostics; no personal/customer data is saved.
                new["results"][target["name"]] = {"status": status, "reason": reason, "url": target["url"], "http_status": response.status if response else None}
                if status == "POSSIBLE_AVAILABLE": found.append((target["name"], target["url"], reason))
            except (PlaywrightTimeoutError, Exception) as e:
                errors.append(f"{target['name']}: {type(e).__name__}: {e}")
                new["results"][target["name"]] = {"status": "ERROR", "reason": str(e)[:300], "url": target["url"]}
        browser.close()

    # Only notify on a transition to possible availability. UNKNOWN/ERROR never trigger an alert.
    prior = old.get("results", {})
    newly_available = [x for x in found if prior.get(x[0], {}).get("status") != "POSSIBLE_AVAILABLE"]
    if newly_available:
        lines = [f"界タビ20'sで空室の可能性を検知しました（宿泊日: {DATE}）", "", "※自動検知は未検証のため、必ず予約画面で確認してください。"]
        for name, url, reason in newly_available:
            lines += [f"\n施設: {name}\n予約画面: {url}\n検知理由: {reason}"]
        send_email(f"【界タビ20's】空室の可能性：{DATE}", "\n".join(lines))
        print(f"Sent notification for {len(newly_available)} newly detected candidate(s).")
    else:
        print("No new possible availability. No email sent.")
    if errors:
        print("Errors occurred (not emailed; inspect Actions log):\n" + "\n".join(errors), file=sys.stderr)
    STATE_FILE.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
