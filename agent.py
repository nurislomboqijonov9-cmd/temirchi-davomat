#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TEMIRCHI davomat — mahalliy "ko'prik" (agent).

Nima qiladi:
  Ishxonadagi yuz-terminallardan (Hikvision) keldi-ketdilarni TO'G'RIDAN-TO'G'RI
  mahalliy tarmoq orqali o'qiydi (internetsiz ham ishlaydi) va bulut serverga
  yuboradi. Internet uzilgan bo'lsa — qaytganda tushib qolganlarini yuboradi.
  Shunday qilib hech bir keldi-ketdi yo'qolmaydi.

Qayerda ishlaydi:
  Terminallar bilan BIR TARMOQDA (bir WiFi/router), doimo yoniq turadigan
  kompyuterda. Kompyuter o'chmasa bo'ldi — internet o'chsa ham mayli.

Sozlash:
  1) Python o'rnating (python.org) va:  pip install requests
  2) Pastdagi SOZLAMALAR qismini to'ldiring (IP, login, parol, SERVER, SYNC_KEY).
  3) Ishga tushiring:  python agent.py
"""

import time
import json
import socket
import datetime as dt

try:
    import requests
    from requests.auth import HTTPDigestAuth
except Exception:
    raise SystemExit("Avval o'rnating:  pip install requests")

# ================== SOZLAMALAR (shu yerni to'ldiring) ==================
SERVER   = "https://web-production-07267.up.railway.app"  # davomat serveringiz manzili
SYNC_KEY = ""   # serverdagi SYNC_KEY bilan BIR XIL bo'lsin (bo'sh ham mumkin)

CAMERALAR = [
    # Har bir terminal: IP, login, parol, va u qaysi eshik (kirish/chiqish)
    {"ip": "192.168.1.10", "user": "admin", "parol": "PAROL_SHU_YERGA", "tur": "kirish"},
    {"ip": "192.168.1.11", "user": "admin", "parol": "PAROL_SHU_YERGA", "tur": "chiqish"},
]

ORQAGA_KUN = 2        # necha kun orqaga qarab tekshirsin (uzilish 1-2 kun bo'lsa ham to'lsin)
HAR_SONIYA = 120      # har necha soniyada bir marta tekshirsin (120 = 2 daqiqa)
SEEN_FAYL  = "yuborilgan.json"   # yuborilganlarni eslab turadi (takror yubormaslik uchun)
# ======================================================================

TZ = dt.timezone(dt.timedelta(hours=5))  # Toshkent


def log(*a):
    print(dt.datetime.now(TZ).strftime("%H:%M:%S"), *a, flush=True)


def _seen_yukla():
    try:
        with open(SEEN_FAYL, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def _seen_saqla(seen):
    try:
        # oxirgi ~5000 tasini saqlab qolamiz (fayl o'smasin)
        with open(SEEN_FAYL, "w", encoding="utf-8") as f:
            json.dump(list(seen)[-5000:], f)
    except Exception:
        pass


def terminal_hodisalari(cam, dan, gacha):
    """Bitta terminaldan AcsEvent (keldi-ketdi) ro'yxatini oladi (ISAPI)."""
    url = f"http://{cam['ip']}/ISAPI/AccessControl/AcsEvent?format=json"
    auth = HTTPDigestAuth(cam["user"], cam["parol"])
    out = []
    pos = 0
    for _ in range(200):  # ko'pi bilan 200*100 = 20000 yozuv
        cond = {"AcsEventCond": {
            "searchID": "temirchi",
            "searchResultPosition": pos,
            "maxResults": 100,
            "major": 5,          # 5 = voqea (event)
            "minor": 0,          # 0 = hammasi
            "startTime": dan.isoformat(),
            "endTime": gacha.isoformat(),
        }}
        try:
            r = requests.post(url, auth=auth, json=cond, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log(f"  [{cam['ip']}] o'qishda xato: {e}")
            break
        blok = data.get("AcsEvent", data)
        infolist = blok.get("InfoList") or []
        for it in infolist:
            ism = (it.get("name") or "").strip()
            emp = str(it.get("employeeNoString") or it.get("employeeNo") or "").strip() or None
            vaqt = it.get("time") or it.get("dateTime")
            if not ism and not emp:
                continue   # yuz tanilmagan / keraksiz voqea
            if not vaqt:
                continue
            out.append({
                "ism": ism or (f"ID{emp}" if emp else ""),
                "emp": emp,
                "tur": cam["tur"],
                "vaqt": str(vaqt),
                "ip": cam["ip"],
            })
        holat = str(blok.get("responseStatusStrg") or "")
        got = len(infolist)
        pos += got
        if holat.upper() != "MORE" or got == 0:
            break
    return out


def yubor(events):
    """Serverga /sync orqali yuboradi. Qaytadi: nechta yangi qo'shildi (yoki -1 xato)."""
    url = f"{SERVER.rstrip('/')}/sync"
    if SYNC_KEY:
        url += "?k=" + SYNC_KEY
    try:
        r = requests.post(url, json={"events": events}, timeout=30)
        r.raise_for_status()
        return (r.json() or {}).get("new", 0)
    except Exception as e:
        log(f"  serverga yuborishda xato (internet o'chiqmi?): {e}")
        return -1


def bir_marta(seen):
    gacha = dt.datetime.now(TZ)
    dan = gacha - dt.timedelta(days=ORQAGA_KUN)
    hammasi = []
    for cam in CAMERALAR:
        hs = terminal_hodisalari(cam, dan, gacha)
        hammasi += hs
    # faqat avval yubormaganlarimiz
    yangilar = []
    for e in hammasi:
        kalit = f"{e['tur']}|{e['vaqt'][:19]}|{e['ism']}"
        if kalit in seen:
            continue
        yangilar.append(e)
    if not yangilar:
        return 0
    n = yubor(yangilar)
    if n >= 0:
        # muvaffaqiyatli yuborildi — eslab qolamiz
        for e in yangilar:
            seen.add(f"{e['tur']}|{e['vaqt'][:19]}|{e['ism']}")
        _seen_saqla(seen)
        log(f"  {len(yangilar)} ta tekshirildi → serverga {n} ta yangi qo'shildi")
    return n


def main():
    log("TEMIRCHI davomat agenti ishga tushdi.")
    log(f"Server: {SERVER}")
    log(f"Terminallar: " + ", ".join(f"{c['ip']}({c['tur']})" for c in CAMERALAR))
    seen = _seen_yukla()
    while True:
        try:
            bir_marta(seen)
        except Exception as e:
            log("umumiy xato:", e)
        time.sleep(HAR_SONIYA)


if __name__ == "__main__":
    main()
