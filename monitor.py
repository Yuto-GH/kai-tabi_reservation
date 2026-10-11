
"""界タビ20's availability monitor (starter; booking-page detector is unverified).

Reads direct booking-result URLs from BOOKING_URLS_JSON. It deliberately fails closed:
unknown pages are reported as UNKNOWN, never treated as available.
"""
from __future__ import annotations

import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DATE = os.getenv("STAY_DATE", "2026-11-10")
RECIPIENT = os.getenv("NOTIFY_TO", "newyork.yuto.19980403@gmail.com")
STATE_FILE = Path("state.json")
CAMPAIGN = "https://hoshinoresorts.com/jp/sp/kaitabi20s/"

SOLD_OUT = [
    "誠に恐れ入りますが、満室となっております",
    "満室となっております",
    "空室がありません",
    "空室なし",
    "ご希望の日程ではご予約いただけません",
]

AVAILABLE = [
    "空室あり",
    "空室がございます",
    "予約へ進む",
    "このプランを予約",
    "予約する",
    "空室検索結果",
]

PLAN_TERMS = ["界タビ20s", "界タビ20’s", "界タビ20's"]


def load_urls():
    raw = os.getenv("BOOKING_URLS_JSON", "[]")

    try:
        urls = json.loads(raw)
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"BOOKING_URLS_JSON must be a JSON array of direct booking-result URLs: {e}"
        )

    if not isinstance(urls, list) or not urls:
        raise SystemExit(
            "BOOKING_URLS_JSON is empty. Add direct official booking-result URLs "
            "for eligible Kanto/Chubu properties after manually setting the stay date and plan."
        )

    out = []

    for item in urls:
        if not isinstance(item, dict) or not item.get("name") or not item.get("url"):
            raise SystemExit(
                "Each BOOKING_URLS_JSON item must have name and url keys"
            )

        u = urlparse(item["url"])

        if u.scheme != "https" or not (
            u.hostname == "hoshinoresorts.com"
            or (
                u.hostname is not None
                and u.hostname.endswith(".hoshinoresorts.com")
            )
        ):
            raise SystemExit(
                f"Only HTTPS hoshinoresorts.com URLs accepted: {item.get('url')}"
            )

        out.append({"name": item["name"], "url": item["url"]})

    return out


def classify(text: str):
    normalized = re.sub(r"\s+", " ", text)

    # 検索結果が0件で、客室が満室と表示されている
    if (
        re.search(r"検索結果\s*0/1件", normalized)
        and re.search(r"検索結果\s*0/1件.{0,300}満室", normalized)
    ):
        return "UNAVAILABLE", "selected room result indicates sold out"

    if any(s in normalized for s in SOLD_OUT):
        return "UNAVAILABLE", "official sold-out wording detected"

    # 検索結果に客室があり、残室数が明示されている
    if re.search(
        r"検索結果\s*1/1件.{0,250}残り\s*\d+\s*室",
        normalized,
    ):
        return (
            "POSSIBLE_AVAILABLE",
            "room search result explicitly shows remaining rooms",
        )

    # カレンダーの凡例や一般的な予約ボタンだけでは空室と判定しない
    return (
        "UNKNOWN",
        "no confirmed room-level availability signal",
    )

def send_email(subject, body):
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ["EMAIL_FROM"]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def main():
    urls = load_urls()

    old = (
        json.loads(STATE_FILE.read_text("utf-8"))
        if STATE_FILE.exists()
        else {}
    )

    new = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "stay_date": DATE,
        "results": {},
    }

    found = []
    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )

        for target in urls:
            try:
                response = page.goto(
                    target["url"],
                    wait_until="domcontentloaded",
                    timeout=45000,
                )

                # JavaScriptによる描画を少し待つ
                page.wait_for_timeout(5000)

                # ページの取得状況を診断
                print("[DEBUG] Facility:", target["name"])
                print("[DEBUG] Requested URL:", target["url"])
                print("[DEBUG] Final URL:", page.url)
                print("[DEBUG] HTTP status:",
                      response.status if response else None)
                print("[DEBUG] Content-Type:",
                      response.headers.get("content-type")
                      if response else None)
                print("[DEBUG] Page title:", repr(page.title()))

                html = page.content()
                print("[DEBUG] HTML length:", len(html))
                print("[DEBUG] HTML preview:", repr(html[:1000]))

                text = page.locator("body").inner_text(timeout=15000)
                print("[DEBUG] Text length:", len(text))
                print("[DEBUG] Page text:", repr(text[:1000]))
                print("[DEBUG] Target date:", DATE)

                if not text.strip():
                    raise RuntimeError(
                        "Page body is empty; availability cannot be checked"
                    )

                status, reason = classify(text)
                
                normalized = re.sub(r"\s+", " ", text)

                print("[DEBUG] Classification:", status)
                print("[DEBUG] Reason:", reason)

                for keyword in ["検索結果0/1件", "満室", "空室あり", "残りわずか"]:
                    pos = normalized.find(keyword)
                    if pos >= 0:
                        print(
                            f"[DEBUG] Context for {keyword}:",
                            normalized[max(0, pos - 150):pos + 250]
                        )
                
                # Keep evidence short for diagnostics; no personal/customer data is saved.
                new["results"][target["name"]] = {
                    "status": status,
                    "reason": reason,
                    "url": target["url"],
                    "http_status": response.status if response else None,
                }

                if status == "POSSIBLE_AVAILABLE":
                    found.append(
                        (target["name"], target["url"], reason)
                    )

            except Exception as e:
                errors.append(
                    f"{target['name']}: {type(e).__name__}: {e}"
                )

                new["results"][target["name"]] = {
                    "status": "ERROR",
                    "reason": str(e)[:300],
                    "url": target["url"],
                }

        browser.close()

    # Only notify on a transition to possible availability.
    # UNKNOWN/ERROR never trigger an alert.
    prior = old.get("results", {})

    newly_available = [
        x for x in found
        if prior.get(x[0], {}).get("status") != "POSSIBLE_AVAILABLE"
    ]

    if newly_available:
        lines = [
            f"界タビ20'sで空室の可能性を検知しました（宿泊日: {DATE}）",
            "",
            "※自動検知は未検証のため、必ず予約画面で確認してください。",
        ]

        for name, url, reason in newly_available:
            lines += [
                f"\n施設: {name}\n予約画面: {url}\n検知理由: {reason}"
            ]

        send_email(
            f"【界タビ20's】空室の可能性：{DATE}",
            "\n".join(lines),
        )

        print(
            f"Sent notification for {len(newly_available)} newly detected candidate(s)."
        )
    else:
        print("No new possible availability. No email sent.")

    if errors:
        print(
            "Errors occurred (not emailed; inspect Actions log):\n"
            + "\n".join(errors),
            file=sys.stderr,
        )

    STATE_FILE.write_text(
        json.dumps(new, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
