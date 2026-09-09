"""
Optional browser-assist module.

This does not bypass CAPTCHA, login screens, anti-bot systems,
or answer sensitive application questions automatically.
"""

from playwright.sync_api import sync_playwright

def open_application(url: str):
    if not url:
        raise ValueError("No application URL supplied.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        print("Application page opened.")
        print("Complete login/CAPTCHA/sensitive questions manually.")
        input("Press Enter here when finished to close the browser...")
        browser.close()

if __name__ == "__main__":
    import sys
    open_application(sys.argv[1])
