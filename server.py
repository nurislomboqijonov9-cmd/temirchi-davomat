import os
import json, re
from aiohttp import web
import db


def _matndan_json(matn):
    """Matn ichidan JSON obyektlarini topib qaytaradi."""
    out = []
    for m in re.finditer(r'\{.*?\}', matn, re.DOTALL):
        try:
            out.append(json.loads(m.group(0)))
        except Exception:
            pass
    # to'liq matnni ham sinaymiz
    try:
        out.append(json.loads(matn))
    except Exception:
        pass
    return out


def _qidir(obj, kalitlar):
    """Ichma-ich dict/list ichidan berilgan kalitlardan birini topadi."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in kalitlar and isinstance(v, (str, int)) and str(v).strip():
                return str(v).strip()
        for v in obj.values():
            r = _qidir(v, kalitlar)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _qidir(v, kalitlar)
            if r:
                return r
    return None


async def _extract(request):
    """Hikvision eventidan ism, emp, vaqt, xom matnni ajratadi."""
    ctype = request.headers.get("Content-Type", "")
    xom = ""
    objs = []
    try:
        if "multipart" in ctype:
            reader = await request.multipart()
            while True:
                part = await reader.next()
                if part is None:
                    break
                try:
                    data = await part.text()
                except Exception:
                    data = ""
                if data:
                    xom += data[:1500] + "\n"
                    objs += _matndan_json(data)
        else:
            body = await request.text()
            xom = body[:2000]
            objs += _matndan_json(body)
    except Exception as e:
        xom = f"(parse xato: {e})"
    # barcha obyektlardan ism/emp/vaqt qidiramiz
    ism = emp = vaqt = None
    for o in objs:
        ism = ism or _qidir(o, {"name", "employeeName", "personName"})
        emp = emp or _qidir(o, {"employeeNoString", "employeeNo", "employeeID", "cardNo"})
        vaqt = vaqt or _qidir(o, {"dateTime", "time", "eventTime"})
    # XML/matn zaxira (JSON topilmasa)
    if not ism:
        m = re.search(r'<(?:name|personName|employeeName)>([^<]+)</', xom)
        if m:
            ism = m.group(1).strip()
    if not emp:
        m = re.search(r'<(?:employeeNoString|employeeNo|cardNo)>([^<]+)</', xom)
        if m:
            emp = m.group(1).strip()
    if not vaqt:
        m = re.search(r'<(?:dateTime|time|eventTime)>([^<]+)</', xom)
        if m:
            vaqt = m.group(1).strip()
    return ism, emp, vaqt, xom.strip(), objs


def _vaqt_tk(iso):
    """ISO (masalan 2026-08-11T09:31:00+05:00) -> Toshkent naive 'YYYY-MM-DDTHH:MM:SS'."""
    if not iso:
        return db.now_tk().replace(tzinfo=None).isoformat()[:19]
    try:
        import datetime as dt
        s = str(iso).strip()
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo:
            d = d.astimezone(db.TZ).replace(tzinfo=None)
        return d.isoformat()[:19]
    except Exception:
        return db.now_tk().replace(tzinfo=None).isoformat()[:19]


def make_web_app(xabar_cb=None):
    """xabar_cb(matn) -> egaga Telegram xabar yuborish uchun (ixtiyoriy)."""
    app = web.Application(client_max_size=20 * 1024 * 1024)

    async def health(request):
        return web.Response(text="TEMIRCHI davomat serveri ishlayapti ✅")

    async def event(request):
        tur = request.query.get("tur", "")
        if not tur:
            if request.path.endswith("chiqish"):
                tur = "chiqish"
            elif request.path.endswith("kirish"):
                tur = "kirish"
        aniq = bool(tur)
        tur = "chiqish" if str(tur).startswith("chiq") else "kirish"
        # GET = qurilma/brauzer sinovi
        if request.method == "GET":
            return web.Response(text=f"OK ({tur}) — qurilma shu manzilga event yuborsa bo'ladi")
        ism, emp, vaqt, xom, objs = await _extract(request)
        ip = None
        for o in objs:
            ip = ip or _qidir(o, {"ipAddress", "srcAddress", "ip"})
        ip = ip or (request.remote or "")
        # tur query/path bilan berilmagan bo'lsa — ip oxiridan aniqlaymiz
        if not aniq and ip:
            if ip.endswith(".11"):
                tur = "chiqish"
            elif ip.endswith(".10"):
                tur = "kirish"
        # ism topilmasa — heartbeat/keraksiz event, faqat raw saqlaymiz (xabarsiz)
        if not ism and not emp:
            return web.Response(text="ok (bo'sh/heartbeat)")
        v = _vaqt_tk(vaqt)
        res = db.hodisa_qosh(ism or f"ID{emp}", emp, tur, v, ip, xom)
        if res and xabar_cb:
            belgi = "🟢 keldi" if tur == "kirish" else "🔴 ketdi"
            try:
                await xabar_cb(f"{belgi}  *{res['ism']}*\n🕐 {res['vaqt'][11:16]}  ·  {tur}")
            except Exception:
                pass
        return web.Response(text="ok")

    async def raw(request):
        """Diagnostika: oxirgi hodisalar (xom event bilan)."""
        rows = db.oxirgi_raw(15)
        return web.json_response(rows, headers={"Content-Type": "application/json; charset=utf-8"})

    async def api_tv(request):
        """TV dashboard uchun — bugungi davomat (kim keldi/ketdi). CORS ochiq."""
        cors = {"Access-Control-Allow-Origin": "*"}
        kalit = os.environ.get("TV_KEY")
        if kalit and request.query.get("k") != kalit:
            return web.json_response({"xato": "ruxsat yo'q"}, status=403, headers=cors)
        lst = db.kunlik_xulosa()
        keldi = sum(1 for o in lst if o["kirish"])
        ketdi = sum(1 for o in lst if o["chiqish"])
        ichkarida = sum(1 for o in lst if o["kirish"] and not o["chiqish"])
        return web.json_response({
            "sana": str(db.today_tk()),
            "keldi": keldi, "ketdi": ketdi, "ichkarida": ichkarida,
            "odamlar": lst,
        }, headers=cors)

    app.router.add_get("/", health)
    app.router.add_get("/event", event)
    app.router.add_post("/event", event)
    app.router.add_get("/kirish", event)   # muqobil: alohida path
    app.router.add_post("/kirish", event)
    app.router.add_get("/chiqish", event)
    app.router.add_post("/chiqish", event)
    app.router.add_get("/raw", raw)
    app.router.add_get("/api/tv", api_tv)
    return app
