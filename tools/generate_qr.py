import qrcode

SLUG = "arnaud-huard"
URL = f"https://maavnica-smartcard-v2.onrender.com/c/{SLUG}"

qr = qrcode.QRCode(
    version=None,
    error_correction=qrcode.constants.ERROR_CORRECT_H,  # robuste
    box_size=20,  # HD
    border=4
)
qr.add_data(URL)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")
out = f"qr-{SLUG}.png"
img.save(out)

print("OK ->", out, "->", URL)
