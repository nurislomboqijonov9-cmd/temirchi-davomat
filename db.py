import os, sqlite3, json
from datetime import datetime, timedelta, timezone

DATA_DIR = os.environ.get("DATA_DIR", ".")
DB = os.path.join(DATA_DIR, "davomat.db")
TZ = timezone(timedelta(hours=5))  # Toshkent
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)


def now_tk():
    return datetime.now(TZ)


def today_tk():
    return now_tk().date()


def _con():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = _con()
    con.execute("""CREATE TABLE IF NOT EXISTS hodisalar(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT, emp TEXT, tur TEXT,           -- tur: 'kirish' | 'chiqish'
        vaqt TEXT,                               -- Toshkent ISO (naive)
        ip TEXT, raw TEXT, created TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS ix_hod ON hodisalar(vaqt)")
    con.execute("""CREATE TABLE IF NOT EXISTS boshliqlar(
        tg_id INTEGER PRIMARY KEY, ism TEXT, created TEXT)""")
    con.commit()
    con.close()


def boshliq_qosh(tg_id, ism=None):
    con = _con()
    con.execute("INSERT OR REPLACE INTO boshliqlar(tg_id,ism,created) VALUES(?,?,?)",
                (int(tg_id), (ism or "").strip() or None, now_tk().isoformat()))
    con.commit()
    con.close()


def boshliq_ochir(tg_id):
    con = _con()
    cur = con.execute("DELETE FROM boshliqlar WHERE tg_id=?", (int(tg_id),))
    con.commit()
    n = cur.rowcount
    con.close()
    return n


def boshliqlar():
    con = _con()
    rows = con.execute("SELECT tg_id, ism FROM boshliqlar ORDER BY created").fetchall()
    con.close()
    return [dict(r) for r in rows]


def _oxirgi_shu(ism, tur, yangi_vaqt, soniya=90):
    """Dedup: shu ism+tur oxirgi hodisasi yangi_vaqtdan 90s ichidami?"""
    con = _con()
    r = con.execute("SELECT vaqt FROM hodisalar WHERE ism=? AND tur=? ORDER BY id DESC LIMIT 1",
                    (ism, tur)).fetchone()
    con.close()
    if not r:
        return False
    try:
        oxirgi = datetime.fromisoformat(r["vaqt"])
        yv = datetime.fromisoformat(str(yangi_vaqt)[:19])
        return abs((yv - oxirgi).total_seconds()) < soniya
    except Exception:
        return False


def hodisa_qosh(ism, emp, tur, vaqt=None, ip=None, raw=None):
    """Yangi hodisa. Dedup bo'lsa None qaytaradi (xabar yuborilmaydi)."""
    ism = (ism or "Noma'lum").strip()
    tur = tur if tur in ("kirish", "chiqish") else "kirish"
    v = vaqt or now_tk().replace(tzinfo=None).isoformat()[:19]
    if _oxirgi_shu(ism, tur, v):
        return None
    con = _con()
    cur = con.execute("INSERT INTO hodisalar(ism,emp,tur,vaqt,ip,raw,created) VALUES(?,?,?,?,?,?,?)",
                      (ism, emp, tur, v, ip, (raw or "")[:2000], now_tk().isoformat()))
    con.commit()
    rid = cur.lastrowid
    con.close()
    return {"id": rid, "ism": ism, "tur": tur, "vaqt": v}


def bugungi(sana=None):
    d = str(sana or today_tk())[:10]
    con = _con()
    rows = con.execute("SELECT * FROM hodisalar WHERE substr(vaqt,1,10)=? ORDER BY vaqt",
                       (d,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def oraliq(sana, t1, t2):
    """t1,t2 = 'HH:MM'. Shu sana va shu vaqt oralig'idagi hodisalar."""
    d = str(sana or today_tk())[:10]
    b = f"{d}T{t1}"
    e = f"{d}T{t2}"
    con = _con()
    rows = con.execute(
        "SELECT * FROM hodisalar WHERE vaqt>=? AND vaqt<=? ORDER BY vaqt", (b, e)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def kunlik_xulosa(sana=None):
    """Har odam: birinchi kirish + oxirgi chiqish + ishlagan soati."""
    hs = bugungi(sana)
    odam = {}
    for h in hs:
        o = odam.setdefault(h["ism"], {"ism": h["ism"], "kir": None, "chiq": None})
        if h["tur"] == "kirish":
            if o["kir"] is None or h["vaqt"] < o["kir"]:   # eng erta kirish
                o["kir"] = h["vaqt"]
        else:
            if o["chiq"] is None or h["vaqt"] > o["chiq"]:  # eng kech chiqish
                o["chiq"] = h["vaqt"]
    res = []
    for o in odam.values():
        soat = None
        if o["kir"] and o["chiq"]:
            try:
                mins = (datetime.fromisoformat(o["chiq"]) - datetime.fromisoformat(o["kir"])).total_seconds() / 60
                if mins > 0:
                    soat = f"{int(mins//60)}s {int(mins%60)}daq"
            except Exception:
                pass
        res.append({"ism": o["ism"],
                    "kirish": (o["kir"][11:16] if o["kir"] else None),
                    "chiqish": (o["chiq"][11:16] if o["chiq"] else None),
                    "ish": soat})
    res.sort(key=lambda x: (x["kirish"] or "99"))
    return res


def oxirgi_raw(n=10):
    con = _con()
    rows = con.execute("SELECT id,ism,tur,vaqt,ip,raw FROM hodisalar ORDER BY id DESC LIMIT ?",
                       (n,)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def ismlar(kunlar=30):
    """Oxirgi N kunda uchragan ismlar ro'yxati."""
    from datetime import timedelta
    b = (today_tk() - timedelta(days=kunlar)).isoformat()
    con = _con()
    rows = con.execute("SELECT DISTINCT ism FROM hodisalar WHERE vaqt>=? ORDER BY ism", (b,)).fetchall()
    con.close()
    return [r["ism"] for r in rows]


def odam_topilsin(qism):
    """Ismning bir qismi bo'yicha mos ismlarni topadi."""
    q = (qism or "").strip().lower()
    if not q:
        return []
    return [i for i in ismlar(60) if q in i.lower()]


def odam_tarix(ism, kunlar=7, sana=None):
    """Bitta odamning oxirgi N kunlik keldi-ketdi tarixi (har kun bo'yicha)."""
    from datetime import timedelta
    oxir = sana or today_tk()
    res = []
    for i in range(kunlar):
        d = oxir - timedelta(days=i)
        hs = [h for h in bugungi(d) if h["ism"].strip().lower() == ism.strip().lower()]
        if not hs:
            continue
        kirs = [h["vaqt"] for h in hs if h["tur"] == "kirish"]
        chiqs = [h["vaqt"] for h in hs if h["tur"] == "chiqish"]
        kir = min(kirs) if kirs else None
        chiq = max(chiqs) if chiqs else None
        ish = None
        if kir and chiq:
            try:
                mins = (datetime.fromisoformat(chiq) - datetime.fromisoformat(kir)).total_seconds() / 60
                if mins > 0:
                    ish = f"{int(mins//60)}s {int(mins%60)}daq"
            except Exception:
                pass
        res.append({"sana": str(d), "kirish": (kir[11:16] if kir else None),
                    "chiqish": (chiq[11:16] if chiq else None), "ish": ish})
    return res
