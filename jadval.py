"""Davomat jadvalini chiroyli PNG rasm qilib chizadi (KATTA shrift, tor rasm)."""
import io
from PIL import Image, ImageDraw, ImageFont

NAVY = (22, 41, 74)
NAVY2 = (28, 51, 90)
GOLD = (200, 162, 74)
GREEN = (47, 158, 107)
RED = (200, 90, 90)
BG = (245, 247, 250)
ROW1 = (255, 255, 255)
ROW2 = (238, 242, 247)
TX = (30, 41, 59)
MUT = (120, 135, 155)


import os as _os
_BU = _os.path.dirname(_os.path.abspath(__file__))

def _font(size, bold=False):
    yollar = [
        _os.path.join(_BU, "DejaVuSans-Bold.ttf") if bold else _os.path.join(_BU, "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for y in yollar:
        try:
            return ImageFont.truetype(y, size)
        except Exception:
            continue
    return ImageFont.load_default()


def jadval_rasm(sana, odamlar, keldi, ketdi):
    """odamlar: [{ism,kirish,chiqish,ish}]. Katta shrift, tor rasm (chatda katta ko'rinadi)."""
    W = 720
    bosh_h = 128
    qator_h = 72
    header_h = 62
    n = len(odamlar)
    H = bosh_h + header_h + max(1, n) * qator_h + 84

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, bosh_h], fill=NAVY)
    d.rectangle([0, bosh_h - 5, W, bosh_h], fill=GOLD)
    d.text((30, 30), "TEMIRCHI", font=_font(46, True), fill=(255, 255, 255))
    d.text((32, 88), "Davomat — kelish / ketish", font=_font(21), fill=(185, 200, 220))
    d.text((W - 210, 48), str(sana), font=_font(26, True), fill=GOLD)

    x_ism, x_kel, x_ket, x_ish = 30, 320, 470, 600
    y = bosh_h
    d.rectangle([0, y, W, y + header_h], fill=NAVY2)
    fh = _font(27, True)
    d.text((x_ism, y + 17), "Ism", font=fh, fill=(220, 230, 245))
    d.text((x_kel, y + 17), "Keldi", font=fh, fill=(220, 230, 245))
    d.text((x_ket, y + 17), "Ketdi", font=fh, fill=(220, 230, 245))
    d.text((x_ish, y + 17), "Ish", font=fh, fill=(220, 230, 245))
    y += header_h

    fr = _font(30)
    frb = _font(30, True)
    for i, o in enumerate(odamlar):
        d.rectangle([0, y, W, y + qator_h], fill=(ROW1 if i % 2 == 0 else ROW2))
        ism = (o.get("ism") or "")[:16]
        kir = o.get("kirish") or "—"
        chiq = o.get("chiqish") or "—"
        ish = (o.get("ish") or "—")
        d.text((x_ism, y + 19), ism, font=frb, fill=TX)
        d.text((x_kel, y + 19), kir, font=fr, fill=GREEN if o.get("kirish") else MUT)
        d.text((x_ket, y + 19), chiq, font=fr, fill=RED if o.get("chiqish") else MUT)
        d.text((x_ish, y + 19), ish, font=fr, fill=TX if o.get("ish") else MUT)
        y += qator_h

    fy = y + 26
    d.ellipse([30, fy + 4, 50, fy + 24], fill=GREEN)
    d.text((58, fy), f"{keldi} keldi", font=_font(26, True), fill=NAVY)
    d.ellipse([220, fy + 4, 240, fy + 24], fill=RED)
    d.text((248, fy), f"{ketdi} ketdi", font=_font(26, True), fill=NAVY)
    d.text((430, fy), f"Jami: {n}", font=_font(26, True), fill=MUT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def jadval_odam_rasm(ism, satlar, kun_soni):
    """Bitta xodimning kunma-kun davomati. Katta shrift, tor rasm."""
    W = 680
    bosh_h = 128
    qator_h = 72
    header_h = 62
    n = len(satlar)
    H = bosh_h + header_h + max(1, n) * qator_h + 84

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, bosh_h], fill=NAVY)
    d.rectangle([0, bosh_h - 5, W, bosh_h], fill=GOLD)
    d.text((30, 30), ism[:20], font=_font(42, True), fill=(255, 255, 255))
    d.text((32, 88), "TEMIRCHI — shaxsiy davomat", font=_font(20), fill=(185, 200, 220))

    x_sana, x_kel, x_ket, x_ish = 30, 280, 430, 560
    y = bosh_h
    d.rectangle([0, y, W, y + header_h], fill=NAVY2)
    fh = _font(27, True)
    d.text((x_sana, y + 17), "Sana", font=fh, fill=(220, 230, 245))
    d.text((x_kel, y + 17), "Keldi", font=fh, fill=(220, 230, 245))
    d.text((x_ket, y + 17), "Ketdi", font=fh, fill=(220, 230, 245))
    d.text((x_ish, y + 17), "Ish", font=fh, fill=(220, 230, 245))
    y += header_h

    fr = _font(30)
    frb = _font(30, True)
    if not satlar:
        d.text((x_sana, y + 19), "Ma'lumot yo'q", font=fr, fill=MUT)
        y += qator_h
    for i, o in enumerate(satlar):
        d.rectangle([0, y, W, y + qator_h], fill=(ROW1 if i % 2 == 0 else ROW2))
        d.text((x_sana, y + 19), str(o.get("sana", ""))[:16], font=frb, fill=TX)
        kir = o.get("kirish") or "—"
        chiq = o.get("chiqish") or "—"
        ish = o.get("ish") or "—"
        d.text((x_kel, y + 19), kir, font=fr, fill=GREEN if o.get("kirish") else MUT)
        d.text((x_ket, y + 19), chiq, font=fr, fill=RED if o.get("chiqish") else MUT)
        d.text((x_ish, y + 19), ish, font=fr, fill=TX if o.get("ish") else MUT)
        y += qator_h

    d.text((30, y + 26), f"Jami {kun_soni} kun ishlagan", font=_font(26, True), fill=NAVY)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf
