import os, re, asyncio, logging
from aiohttp import web
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
import db, server

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("davomat")

BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)
PORT = int(os.environ.get("PORT", "8080"))
# Real vaqt xabar faqat shu soatdan keyin (kech kelgan/ketganlar)
JONLI_SOAT = int(os.environ.get("JONLI_SOAT", "21"))


# ---------- Matn tayyorlash ----------
def _kelish_matn(sana=None):
    lst = [o for o in db.kunlik_xulosa(sana) if o["kirish"]]
    lst.sort(key=lambda x: x["kirish"])
    if not lst:
        return "🌅 *Kelish* — hali hech kim kelmadi."
    d = str(sana or db.today_tk())[:10]
    q = [f"🌅 *Kelish jadvali* — {d}\n"]
    for o in lst:
        q.append(f"• *{o['ism']}* — 🟢 {o['kirish']}")
    return "\n".join(q)


def _ketish_matn(sana=None):
    lst = [o for o in db.kunlik_xulosa(sana) if o["chiqish"]]
    lst.sort(key=lambda x: x["chiqish"])
    if not lst:
        return "🌆 *Ketish* — hali hech kim ketmadi."
    d = str(sana or db.today_tk())[:10]
    q = [f"🌆 *Ketish jadvali* — {d}\n"]
    for o in lst:
        q.append(f"• *{o['ism']}* — 🔴 {o['chiqish']}")
    return "\n".join(q)


def _xulosa_matn(sana=None):
    lst = db.kunlik_xulosa(sana)
    if not lst:
        return "📋 Bugun hech kim qayd etilmadi."
    d = str(sana or db.today_tk())[:10]
    q = [f"📋 *Kunlik davomat* — {d}\n"]
    for o in lst:
        kir = o["kirish"] or "—"
        chiq = o["chiqish"] or "—"
        ish = f"  ·  ⏱ {o['ish']}" if o["ish"] else ""
        q.append(f"• *{o['ism']}*:  🟢 {kir}  →  🔴 {chiq}{ish}")
    return "\n".join(q)


async def _yubor(app, matn):
    if OWNER_ID:
        for i in range(0, len(matn), 3500):
            await app.bot.send_message(OWNER_ID, matn[i:i+3500], parse_mode=ParseMode.MARKDOWN)


# ---------- Buyruqlar ----------
async def start_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        "👋 *TEMIRCHI — Davomat*\n\n"
        "• /kelish — bugun kim nechada keldi\n"
        "• /ketish — kim nechada ketdi\n"
        "• /hisobot — to'liq: keldi–ketdi (+ ish soati)\n"
        "• /davomat 18:30 22:30 — oraliq (shu vaqtdagi kirdi/chiqdi)\n"
        "• /bugun — barcha kirish/chiqishlar\n\n"
        "🔔 Avtomat: 11:00 kelish · 21:00 ketish · 22:00 umumiy jadval.",
        parse_mode=ParseMode.MARKDOWN)


async def kelish_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(_kelish_matn(), parse_mode=ParseMode.MARKDOWN)


async def ketish_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(_ketish_matn(), parse_mode=ParseMode.MARKDOWN)


async def hisobot_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(_xulosa_matn(), parse_mode=ParseMode.MARKDOWN)


async def davomat_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    args = ctx.args or []
    vaqtlar = [a for a in args if re.match(r'^\d{1,2}:\d{2}$', a)]
    if len(vaqtlar) >= 2:
        t1, t2 = vaqtlar[0], vaqtlar[1]
        if len(t1) == 4: t1 = "0" + t1
        if len(t2) == 4: t2 = "0" + t2
        hs = db.oraliq(db.today_tk(), t1, t2)
        if not hs:
            await update.message.reply_text(f"🕐 {t1}–{t2} oralig'ida hech kim qayd etilmadi.")
            return
        q = [f"🕐 *Davomat* {t1}–{t2}\n"]
        for h in hs:
            belgi = "🟢 keldi" if h["tur"] == "kirish" else "🔴 ketdi"
            q.append(f"• {h['vaqt'][11:16]}  *{h['ism']}* — {belgi}")
        await update.message.reply_text("\n".join(q), parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(_xulosa_matn(), parse_mode=ParseMode.MARKDOWN)


async def bugun_cmd(update, ctx):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    hs = db.bugungi()
    if not hs:
        await update.message.reply_text("Bugun hodisa yo'q.")
        return
    q = ["📥 *Bugungi kirish/chiqishlar*\n"]
    for h in hs:
        belgi = "🟢" if h["tur"] == "kirish" else "🔴"
        q.append(f"{belgi} {h['vaqt'][11:16]}  *{h['ism']}*  ({h['tur']})")
    matn = "\n".join(q)
    for i in range(0, len(matn), 3500):
        await update.message.reply_text(matn[i:i+3500], parse_mode=ParseMode.MARKDOWN)


# ---------- Avtomat hisobotlar ----------
async def hisobot_loop(app):
    yubor = {"kel": None, "ket": None, "umum": None}
    while True:
        try:
            n = db.now_tk()
            kun = n.strftime("%Y-%m-%d")
            if n.hour == 11 and n.minute == 0 and yubor["kel"] != kun:
                await _yubor(app, _kelish_matn()); yubor["kel"] = kun
            if n.hour == 21 and n.minute == 0 and yubor["ket"] != kun:
                await _yubor(app, _ketish_matn()); yubor["ket"] = kun
            if n.hour == 22 and n.minute == 0 and yubor["umum"] != kun:
                await _yubor(app, "🌙 " + _xulosa_matn()); yubor["umum"] = kun
        except Exception:
            log.exception("hisobot_loop")
        await asyncio.sleep(30)


async def run():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("kelish", kelish_cmd))
    app.add_handler(CommandHandler("ketish", ketish_cmd))
    app.add_handler(CommandHandler("hisobot", hisobot_cmd))
    app.add_handler(CommandHandler("davomat", davomat_cmd))
    app.add_handler(CommandHandler("bugun", bugun_cmd))

    async def xabar_cb(matn):
        # Faqat kech (JONLI_SOAT dan keyin) — kunduzi spam bo'lmasin
        if OWNER_ID and db.now_tk().hour >= JONLI_SOAT:
            try:
                await app.bot.send_message(OWNER_ID, matn, parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass

    webapp = server.make_web_app(xabar_cb)
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await site.start()
    asyncio.create_task(hisobot_loop(app))
    log.info("Davomat ishga tushdi (port %s)", PORT)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(run())
