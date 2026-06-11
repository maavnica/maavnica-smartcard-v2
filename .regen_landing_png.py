from playwright.sync_api import sync_playwright
import time
import os

out = r"C:\Users\arnau\Documents\maavnica-smartcard-v0.2-quotes\maavnica-smartcard\backend\static\landing-v2"
hero_copy = r"C:\Users\arnau\Documents\maavnica-smartcard-v0.2-quotes\maavnica-smartcard\backend\static\hero-smartcard-premium.png"

shots = [
    ("hero-maavnica.png", "https://smartcard.maavnica.com/c/arnaud-huard"),
    ("demo-artisan.png", "https://smartcard.maavnica.com/c/demo"),
    ("demo-bienetre.png", "https://smartcard.maavnica.com/c/demo2"),
    ("demo-immobilier.png", "https://smartcard.maavnica.com/c/demo3"),
    ("demo-maavnica.png", "https://smartcard.maavnica.com/c/arnaud-huard"),
]

init = "localStorage.setItem('maavnica_consent', 'all');"

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, url in shots:
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.add_init_script(init)
        page.goto(url, wait_until="networkidle", timeout=60000)
        time.sleep(1.5)
        page.evaluate(
            "document.getElementById('maavnica-consent-banner')?.remove()"
        )
        el = page.locator(".phone-shell").first
        el.wait_for(state="visible", timeout=15000)
        path = os.path.join(out, name)
        el.screenshot(path=path)
        print("ok", name)
        page.close()
    browser.close()

import shutil
shutil.copy2(os.path.join(out, "hero-maavnica.png"), hero_copy)
print("ok hero-smartcard-premium.png")
