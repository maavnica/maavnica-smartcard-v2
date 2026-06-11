from playwright.sync_api import sync_playwright
import time

out = r"C:\Users\arnau\Documents\maavnica-smartcard-v0.2-quotes\maavnica-smartcard\preview-hero-fixed.png"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.add_init_script("localStorage.setItem('maavnica_consent', 'all');")
    page.goto("http://127.0.0.1:8765/", wait_until="networkidle", timeout=30000)
    time.sleep(1)
    page.locator("#hero").screenshot(path=out)
    browser.close()
print("ok", out)
