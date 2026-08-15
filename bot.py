import os, re, asyncio, logging
from aiohttp import web
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
import db, server
try:
    import jadval
except Exception:
    jadval = None

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


def _ish_qisqa(ish):
    """'9s 35daq' -> '9s35'."""
    if not ish:
        return "—"
    return ish.replace(" ", "").replace("daq", "")


def _xulosa_matn(sana=None):
    lst = db.kunlik_xulosa(sana)
    if not lst:
        return "📋 Bugun hech kim qayd etilmadi."
    d = str(sana or db.today_tk())[:10]
    # Monospace jadval (ustunlar tekis)
    satlar = []
    satlar.append(f"{'Ism':<13}{'Keldi':<7}{'Ketdi':<7}{'Ish':<6}")
    satlar.append("─" * 32)
    for o in lst:
        ism = (o["ism"] or "")[:12]
        kir = o["kirish"] or "—"
        chiq = o["chiqish"] or "—"
        ish = _ish_qisqa(o["ish"])
        satlar.append(f"{ism:<13}{kir:<7}{chiq:<7}{ish:<6}")
    keldi = sum(1 for o in lst if o["kirish"])
    ketdi = sum(1 for o in lst if o["chiqish"])
    jadval = "\n".join(satlar)
    return (f"📋 *Kunlik davomat* — {d}\n"
            f"```\n{jadval}\n```\n"
            f"🟢 {keldi} keldi · 🔴 {ketdi} ketdi")


async def _yubor(app, matn):
    """Hisobotni owner + barcha boshliqlarga yuboradi."""
    idlar = _qabul_royxati()
    for uid in idlar:
        try:
            for i in range(0, len(matn), 3500):
                await app.bot.send_message(uid, matn[i:i+3500], parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass


def _qabul_royxati():
    idlar = set()
    if OWNER_ID:
        idlar.add(OWNER_ID)
    for b in db.boshliqlar():
        idlar.add(int(b["tg_id"]))
    return idlar


def _ruxsat(uid):
    return uid in _qabul_royxati()


# ---------- Buyruqlar ----------
async def start_cmd(update, ctx):
    uid = update.effective_user.id
    if not _ruxsat(uid):
        # Boshqa odam — o'z ID sini ko'rsatamiz (egaga berish uchun)
        await update.message.reply_text(
            f"👋 Salom! Sizning ID: `{uid}`\n\n"
            "Bu ID ni rahbaringizga bering — u sizni davomat xabarlariga qo'shadi.",
            parse_mode=ParseMode.MARKDOWN)
        return
    await update.message.reply_text(
        "👋 *TEMIRCHI — Davomat*\n\n"
        "• /kelish — bugun kim nechada keldi\n"
        "• /ketish — kim nechada ketdi\n"
        "• /hisobot — to'liq: keldi–ketdi (+ ish soati)\n"
        "• /jadval — chiroyli rasm jadval 📊\n"
        "• /odam Umar — bir odamning 7 kunlik tarixi\n"
        "• /oy Umar — bir odamning 30 kunlik tarixi\n"
        "• /davomat 18:30 22:30 — oraliq\n"
        "• /bugun — barcha kirish/chiqishlar\n\n"
        "👤 *Boshliq qo'shish (faqat ega):*\n"
        "• /idlar — kimlar xabar oladi\n"
        "• /idqosh 123456789 Xusan aka — qo'shish\n"
        "• /idochir 123456789 — o'chirish\n\n"
        "🔔 Avtomat: 11:00 kelish · 21:00 ketish · 22:00 umumiy jadval.",
        parse_mode=ParseMode.MARKDOWN)


async def idlar_cmd(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return
    bs = db.boshliqlar()
    q = [f"👤 *Xabar oladiganlar*\n\n• Ega (siz): `{OWNER_ID}`"]
    for b in bs:
        q.append(f"• {b['ism'] or 'Boshliq'}: `{b['tg_id']}`")
    q.append("\n_Qo'shish:_ `/idqosh 123456789 Ism`\n_O'chirish:_ `/idochir 123456789`")
    q.append("\n_ID ni bilish: o'sha odam botga /start yozsa, ID chiqadi._")
    await update.message.reply_text("\n".join(q), parse_mode=ParseMode.MARKDOWN)


async def idqosh_cmd(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await update.message.reply_text(
            "👤 Qo'shish: `/idqosh 123456789 Xusan aka`\n"
            "_(ID ni bilish: o'sha odam botga /start yozsin.)_", parse_mode=ParseMode.MARKDOWN)
        return
    tg = int(args[0])
    ism = " ".join(args[1:]).strip() or None
    db.boshliq_qosh(tg, ism)
    await update.message.reply_text(f"✅ Qo'shildi: {ism or 'Boshliq'} (`{tg}`)\nEndi unga ham davomat xabarlari boradi.",
                                    parse_mode=ParseMode.MARKDOWN)


async def idochir_cmd(update, ctx):
    if update.effective_user.id != OWNER_ID:
        return
    args = ctx.args or []
    if not args or not args[0].lstrip("-").isdigit():
        await update.message.reply_text("O'chirish: `/idochir 123456789`", parse_mode=ParseMode.MARKDOWN)
        return
    n = db.boshliq_ochir(int(args[0]))
    await update.message.reply_text("✅ O'chirildi." if n else "❌ Bunday ID yo'q.")


async def kelish_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    await update.message.reply_text(_kelish_matn(), parse_mode=ParseMode.MARKDOWN)


async def ketish_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    await update.message.reply_text(_ketish_matn(), parse_mode=ParseMode.MARKDOWN)


async def hisobot_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    await update.message.reply_text(_xulosa_matn(), parse_mode=ParseMode.MARKDOWN)


def _jadval_rasmi(sana=None):
    """Kunlik davomat rasmi (BytesIO) yoki None."""
    if not jadval:
        return None
    lst = db.kunlik_xulosa(sana)
    if not lst:
        return None
    odamlar = [{"ism": o["ism"], "kirish": o["kirish"], "chiqish": o["chiqish"],
                "ish": _ish_qisqa(o["ish"])} for o in lst]
    keldi = sum(1 for o in lst if o["kirish"])
    ketdi = sum(1 for o in lst if o["chiqish"])
    try:
        return jadval.jadval_rasm(str(sana or db.today_tk()), odamlar, keldi, ketdi)
    except Exception:
        log.exception("jadval rasm")
        return None


async def jadval_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    buf = _jadval_rasmi()
    if buf:
        await update.message.reply_photo(photo=buf, caption=f"📋 Davomat — {db.today_tk()}")
    else:
        await update.message.reply_text(_xulosa_matn(), parse_mode=ParseMode.MARKDOWN)


async def davomat_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
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


def _odam_tarix_matn(ism, kunlar):
    tarix = db.odam_tarix(ism, kunlar)
    if not tarix:
        return f"📭 *{ism}* — oxirgi {kunlar} kunda qayd yo'q."
    oy = ["yan","fev","mar","apr","may","iyn","iyl","avg","sen","okt","noy","dek"]
    q = [f"👤 *{ism}* — oxirgi {kunlar} kun\n"]
    kun_soni = 0
    for t in tarix:
        try:
            y, m, dd = t["sana"].split("-")
            sana_matn = f"{int(dd)}-{oy[int(m)-1]}"
        except Exception:
            sana_matn = t["sana"]
        kir = t["kirish"] or "—"
        chiq = t["chiqish"] or "—"
        ish = f"  ·  ⏱ {t['ish']}" if t["ish"] else ""
        q.append(f"📅 {sana_matn}:  🟢 {kir}  →  🔴 {chiq}{ish}")
        if t["kirish"]:
            kun_soni += 1
    q.append(f"\n📊 Jami *{kun_soni}* kun ishlagan.")
    return "\n".join(q)


async def odam_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    ctx.chat_data["_kunlar"] = 7
    await _odam_javob(update, ctx, 7)


async def oy_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
        return
    await _odam_javob(update, ctx, 30)


async def _odam_javob(update, ctx, kunlar):
    ism = " ".join(ctx.args or []).strip()
    if not ism:
        ro = db.ismlar(30)
        matn = "👤 *Kimning davomati?*\n\nMasalan: `/odam Umar`\n\n"
        if ro:
            matn += "Ismlar: " + ", ".join(ro)
        await update.message.reply_text(matn, parse_mode=ParseMode.MARKDOWN)
        return
    mos = db.odam_topilsin(ism)
    if len(mos) > 1 and ism.lower() not in [m.lower() for m in mos]:
        await update.message.reply_text("👥 Bir nechta mos keldi: " + ", ".join(mos) + "\nAniqroq yozing.",
                                        parse_mode=ParseMode.MARKDOWN)
        return
    aniq = mos[0] if mos else ism
    await update.message.reply_text(_odam_tarix_matn(aniq, kunlar), parse_mode=ParseMode.MARKDOWN)


async def bugun_cmd(update, ctx):
    if not _ruxsat(update.effective_user.id):
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
                # rasm jadval ham
                buf = _jadval_rasmi()
                if buf:
                    data = buf.getvalue()
                    for uid in _qabul_royxati():
                        try:
                            import io as _io
                            await app.bot.send_photo(uid, photo=_io.BytesIO(data),
                                                     caption=f"📋 Kunlik davomat — {db.today_tk()}")
                        except Exception:
                            pass
        except Exception:
            log.exception("hisobot_loop")
        await asyncio.sleep(30)


async def run():
    db.init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("idlar", idlar_cmd))
    app.add_handler(CommandHandler("idqosh", idqosh_cmd))
    app.add_handler(CommandHandler("idochir", idochir_cmd))
    app.add_handler(CommandHandler("kelish", kelish_cmd))
    app.add_handler(CommandHandler("ketish", ketish_cmd))
    app.add_handler(CommandHandler("hisobot", hisobot_cmd))
    app.add_handler(CommandHandler("jadval", jadval_cmd))
    app.add_handler(CommandHandler("odam", odam_cmd))
    app.add_handler(CommandHandler("oy", oy_cmd))
    app.add_handler(CommandHandler("davomat", davomat_cmd))
    app.add_handler(CommandHandler("bugun", bugun_cmd))

    async def xabar_cb(matn):
        # Faqat kech (JONLI_SOAT dan keyin) — kunduzi spam bo'lmasin
        if db.now_tk().hour >= JONLI_SOAT:
            for uid in _qabul_royxati():
                try:
                    await app.bot.send_message(uid, matn, parse_mode=ParseMode.MARKDOWN)
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
