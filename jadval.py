"""Davomat jadvalini chiroyli PNG rasm qilib chizadi."""
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


def _font(size, bold=False):
    yollar = [
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
    """odamlar: [{ism,kirish,chiqish,ish}]. PNG bytes qaytaradi."""
    W = 820
    bosh_h = 96
    qator_h = 46
    header_h = 44
    n = len(odamlar)
    H = bosh_h + header_h + n * qator_h + 60

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Yuqori panel (TEMIRCHI)
    d.rectangle([0, 0, W, bosh_h], fill=NAVY)
    d.rectangle([0, bosh_h - 4, W, bosh_h], fill=GOLD)
    d.text((28, 22), "TEMIRCHI", font=_font(30, True), fill=(255, 255, 255))
    d.text((30, 60), "Davomat — kelish / ketish", font=_font(15), fill=(180, 195, 215))
    d.text((W - 200, 34), str(sana), font=_font(18, True), fill=GOLD)

    # Ustun x koordinatalari
    x_ism, x_kel, x_ket, x_ish = 28, 380, 500, 630
    y = bosh_h

    # Sarlavha qatori
    d.rectangle([0, y, W, y + header_h], fill=NAVY2)
    fh = _font(16, True)
    d.text((x_ism, y + 12), "Ism", font=fh, fill=(220, 230, 245))
    d.text((x_kel, y + 12), "Keldi", font=fh, fill=(220, 230, 245))
    d.text((x_ket, y + 12), "Ketdi", font=fh, fill=(220, 230, 245))
    d.text((x_ish, y + 12), "Ish", font=fh, fill=(220, 230, 245))
    y += header_h

    fr = _font(18)
    frb = _font(18, True)
    for i, o in enumerate(odamlar):
        d.rectangle([0, y, W, y + qator_h], fill=(ROW1 if i % 2 == 0 else ROW2))
        ism = (o.get("ism") or "")[:22]
        kir = o.get("kirish") or "—"
        chiq = o.get("chiqish") or "—"
        ish = (o.get("ish") or "—")
        d.text((x_ism, y + 12), ism, font=frb, fill=TX)
        d.text((x_kel, y + 12), kir, font=fr, fill=GREEN if o.get("kirish") else MUT)
        d.text((x_ket, y + 12), chiq, font=fr, fill=RED if o.get("chiqish") else MUT)
        d.text((x_ish, y + 12), ish, font=fr, fill=TX if o.get("ish") else MUT)
        y += qator_h

    # Pastki xulosa (rangli nuqtalar bilan)
    fy = y + 20
    d.ellipse([28, fy + 2, 42, fy + 16], fill=GREEN)
    d.text((50, fy), f"{keldi} keldi", font=_font(17, True), fill=NAVY)
    d.ellipse([170, fy + 2, 184, fy + 16], fill=RED)
    d.text((192, fy), f"{ketdi} ketdi", font=_font(17, True), fill=NAVY)
    d.text((320, fy), f"Jami: {n}", font=_font(17, True), fill=MUT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf
