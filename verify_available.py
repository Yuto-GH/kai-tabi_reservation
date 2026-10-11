
import re
import sys

from playwright.sync_api import sync_playwright
from monitor import classify

URL = (
    "https://hoshinoresorts.com/JA/hotels/0000000131/plans/"
    "0000000083?checkIn=2026%2F10%2F27&stay=1&a=2&b=0&c=0&d=0"
)

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            response = page.goto(
                URL,
                wait_until="domcontentloaded",
                timeout=45000,
            )
            page.wait_for_timeout(5000)

            print("URL:", page.url)
            print("HTTP status:", response.status if response else None)

            text = page.locator("body").inner_text(timeout=15000)
            normalized = re.sub(r"\s+", " ", text)

            print("Text length:", len(text))

            for keyword in ["検索結果", "残り2室", "満室"]:
                pos = normalized.find(keyword)
                if pos >= 0:
                    print(
                        f"Context for {keyword}:",
                        normalized[max(0, pos - 80):pos + 180],
                    )

            status, reason = classify(text)
            print("Classification:", status)
            print("Reason:", reason)

            if status != "POSSIBLE_AVAILABLE":
                print(
                    "Verification failed: the page was not classified "
                    "as POSSIBLE_AVAILABLE."
                )
                sys.exit(1)

            print("Verification passed!")

        finally:
            browser.close()

if __name__ == "__main__":
    main()
