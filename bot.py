import os, asyncio, logging
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
REPORT_HOUR = int(os.environ.get("REPORT_HOUR", "19"))
REPORT_MIN = int(os.environ.get("REPORT_MIN", "30"))


def _xulosa_matn(sana=None):
    lst = db.kunlik_xulosa(sana)
    if not lst:
        return "📋 Bugun hech kim qayd etilmadi."
    d = str(sana or db.today_tk())[:10]
    qatorlar = [f"📋 *Kunlik davomat* — {d}\n"]
    for o in lst:
        kir = o["kirish"] or "—"
        chiq = o["chiqish"] or "—"
        ish = f"  ·  ⏱ {o['ish']}" if o["ish"] else ""
        qatorlar.append(f"• *{o['ism']}*:  🟢 {kir}  →  🔴 {chiq}{ish}")
    return "\n".join(qatorlar)


async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text(
        "👋 TEMIRCHI — Davomat\n\n"
        "• /davomat — bugungi davomat\n"
        "• /davomat 18:30 22:30 — oraliq (shu vaqt ichidagi kirdi/chiqdi)\n"
        "• /bugun — bugungi barcha kirish/chiqishlar\n\n"
        f"Har kuni {REPORT_HOUR:02d}:{REPORT_MIN:02d} da yakuniy davomat keladi.")


async def davomat_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    args = ctx.args or []
    import re
    vaqtlar = [a for a in args if re.match(r'^\d{1,2}:\d{2}$', a)]
    if len(vaqtlar) >= 2:
        t1, t2 = vaqtlar[0], vaqtlar[1]
        if len(t1) == 4:
            t1 = "0" + t1
        if len(t2) == 4:
            t2 = "0" + t2
        hs = db.oraliq(db.today_tk(), t1, t2)
        if not hs:
            await update.message.reply_text(f"🕐 {t1}–{t2} oralig'ida hech kim qayd etilmadi.")
            return
        qatorlar = [f"🕐 *Davomat* {t1}–{t2}\n"]
        for h in hs:
            belgi = "🟢 keldi" if h["tur"] == "kirish" else "🔴 ketdi"
            qatorlar.append(f"• {h['vaqt'][11:16]}  *{h['ism']}*  — {belgi}")
        await update.message.reply_text("\n".join(qatorlar), parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(_xulosa_matn(), parse_mode=ParseMode.MARKDOWN)


async def bugun_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if OWNER_ID and update.effective_user.id != OWNER_ID:
        return
    hs = db.bugungi()
    if not hs:
        await update.message.reply_text("Bugun hodisa yo'q.")
        return
    qatorlar = ["📥 *Bugungi kirish/chiqishlar*\n"]
    for h in hs:
        belgi = "🟢" if h["tur"] == "kirish" else "🔴"
        qatorlar.append(f"{belgi} {h['vaqt'][11:16]}  *{h['ism']}*  ({h['tur']})")
    matn = "\n".join(qatorlar)
    for i in range(0, len(matn), 3500):
        await update.message.reply_text(matn[i:i+3500], parse_mode=ParseMode.MARKDOWN)


async def hisobot_loop(app):
    yuborilgan = None
    while True:
        try:
            n = db.now_tk()
            kalit = n.strftime("%Y-%m-%d")
            if n.hour == REPORT_HOUR and n.minute == REPORT_MIN and yuborilgan != kalit and OWNER_ID:
                await app.bot.send_message(OWNER_ID, "🌆 " + _xulosa_matn(), parse_mode=ParseMode.MARKDOWN)
                yuborilgan = kalit
        except Exception:
            log.exception("hisobot_loop")
        await asyncio.sleep(30)


async def run():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("davomat", davomat_cmd))
    app.add_handler(CommandHandler("bugun", bugun_cmd))

    async def xabar_cb(matn):
        if OWNER_ID:
            await app.bot.send_message(OWNER_ID, matn, parse_mode=ParseMode.MARKDOWN)

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
