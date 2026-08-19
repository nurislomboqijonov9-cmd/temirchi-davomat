"""Davomat jadvalini chiroyli PNG rasm qilib chizadi (katta shrift)."""
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
    """odamlar: [{ism,kirish,chiqish,ish}]. PNG bytes qaytaradi. KATTA shrift."""
    W = 960
    bosh_h = 118
    qator_h = 60
    header_h = 56
    n = len(odamlar)
    H = bosh_h + header_h + max(1, n) * qator_h + 74

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Yuqori panel
    d.rectangle([0, 0, W, bosh_h], fill=NAVY)
    d.rectangle([0, bosh_h - 5, W, bosh_h], fill=GOLD)
    d.text((32, 26), "TEMIRCHI", font=_font(40, True), fill=(255, 255, 255))
    d.text((34, 76), "Davomat — kelish / ketish", font=_font(20), fill=(185, 200, 220))
    d.text((W - 240, 42), str(sana), font=_font(24, True), fill=GOLD)

    # Ustunlar
    x_ism, x_kel, x_ket, x_ish = 34, 470, 630, 800
    y = bosh_h
    d.rectangle([0, y, W, y + header_h], fill=NAVY2)
    fh = _font(22, True)
    d.text((x_ism, y + 15), "Ism", font=fh, fill=(220, 230, 245))
    d.text((x_kel, y + 15), "Keldi", font=fh, fill=(220, 230, 245))
    d.text((x_ket, y + 15), "Ketdi", font=fh, fill=(220, 230, 245))
    d.text((x_ish, y + 15), "Ish", font=fh, fill=(220, 230, 245))
    y += header_h

    fr = _font(24)
    frb = _font(24, True)
    for i, o in enumerate(odamlar):
        d.rectangle([0, y, W, y + qator_h], fill=(ROW1 if i % 2 == 0 else ROW2))
        ism = (o.get("ism") or "")[:26]
        kir = o.get("kirish") or "—"
        chiq = o.get("chiqish") or "—"
        ish = (o.get("ish") or "—")
        d.text((x_ism, y + 16), ism, font=frb, fill=TX)
        d.text((x_kel, y + 16), kir, font=fr, fill=GREEN if o.get("kirish") else MUT)
        d.text((x_ket, y + 16), chiq, font=fr, fill=RED if o.get("chiqish") else MUT)
        d.text((x_ish, y + 16), ish, font=fr, fill=TX if o.get("ish") else MUT)
        y += qator_h

    # Pastki xulosa (rangli nuqtalar)
    fy = y + 22
    d.ellipse([34, fy + 3, 52, fy + 21], fill=GREEN)
    d.text((60, fy), f"{keldi} keldi", font=_font(22, True), fill=NAVY)
    d.ellipse([210, fy + 3, 228, fy + 21], fill=RED)
    d.text((236, fy), f"{ketdi} ketdi", font=_font(22, True), fill=NAVY)
    d.text((390, fy), f"Jami: {n}", font=_font(22, True), fill=MUT)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def jadval_odam_rasm(ism, satlar, kun_soni):
    """Bitta xodimning kunma-kun davomati. satlar: [{sana,kirish,chiqish,ish}]. KATTA shrift."""
    W = 880
    bosh_h = 118
    qator_h = 60
    header_h = 56
    n = len(satlar)
    H = bosh_h + header_h + max(1, n) * qator_h + 74

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, bosh_h], fill=NAVY)
    d.rectangle([0, bosh_h - 5, W, bosh_h], fill=GOLD)
    d.text((32, 24), ism[:26], font=_font(36, True), fill=(255, 255, 255))
    d.text((34, 74), "TEMIRCHI — shaxsiy davomat", font=_font(19), fill=(185, 200, 220))

    x_sana, x_kel, x_ket, x_ish = 34, 360, 520, 690
    y = bosh_h
    d.rectangle([0, y, W, y + header_h], fill=NAVY2)
    fh = _font(22, True)
    d.text((x_sana, y + 15), "Sana", font=fh, fill=(220, 230, 245))
    d.text((x_kel, y + 15), "Keldi", font=fh, fill=(220, 230, 245))
    d.text((x_ket, y + 15), "Ketdi", font=fh, fill=(220, 230, 245))
    d.text((x_ish, y + 15), "Ish", font=fh, fill=(220, 230, 245))
    y += header_h

    fr = _font(24)
    frb = _font(24, True)
    if not satlar:
        d.text((x_sana, y + 16), "Ma'lumot yo'q", font=fr, fill=MUT)
        y += qator_h
    for i, o in enumerate(satlar):
        d.rectangle([0, y, W, y + qator_h], fill=(ROW1 if i % 2 == 0 else ROW2))
        d.text((x_sana, y + 16), str(o.get("sana", ""))[:16], font=frb, fill=TX)
        kir = o.get("kirish") or "—"
        chiq = o.get("chiqish") or "—"
        ish = o.get("ish") or "—"
        d.text((x_kel, y + 16), kir, font=fr, fill=GREEN if o.get("kirish") else MUT)
        d.text((x_ket, y + 16), chiq, font=fr, fill=RED if o.get("chiqish") else MUT)
        d.text((x_ish, y + 16), ish, font=fr, fill=TX if o.get("ish") else MUT)
        y += qator_h

    d.text((34, y + 22), f"Jami {kun_soni} kun ishlagan", font=_font(22, True), fill=NAVY)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf
