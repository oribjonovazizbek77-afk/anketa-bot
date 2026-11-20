import os
import re

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")  # Render o'zi beradi
PORT = int(os.environ.get("PORT", 10000))

HA = "Ha, roziman"
YOQ = "Yo'q"

# (kalit, admin uchun nomi, savol matni)
SAVOLLAR = [
    ("ism", "Ism", "Ismingiz?"),
    ("hudud", "Qayerdan", "Qayerdansiz?"),
    ("yosh", "Yosh", "Yoshingiz nechida?"),
    ("boy", "Sm", "Necha sm?"),
    ("rasm", "Rasm", "Rasmingizni yuboring (1 ta rasm):"),
    (
        "rozilik",
        "18+ roziligi",
        "Siz 18 yoshdan oshganmisiz va anketa ma'lumotlaringiz "
        "ko'rib chiqilishiga rozimisiz?",
    ),
]

SAVOL = 0


async def savol_ber(update: Update, i: int):
    key, _, matn = SAVOLLAR[i]
    if key == "rozilik":
        kb = ReplyKeyboardMarkup([[HA, YOQ]], one_time_keyboard=True, resize_keyboard=True)
    else:
        kb = ReplyKeyboardRemove()
    await update.message.reply_text(matn, reply_markup=kb)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["i"] = 0
    await update.message.reply_text("Assalomu alaykum! Anketani to'ldiring.")
    await savol_ber(update, 0)
    return SAVOL


async def javob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    i = context.user_data.get("i", 0)
    key = SAVOLLAR[i][0]
    msg = update.message
    text = (msg.text or "").strip()

    if key == "rasm":
        if not msg.photo:
            await msg.reply_text("Iltimos, rasm yuboring.")
            return SAVOL
        context.user_data["rasm_id"] = msg.photo[-1].file_id
        text = "yuborildi"
    elif not text:
        await msg.reply_text("Iltimos, matn bilan yozing.")
        return SAVOL

    if key in ("yosh", "boy") and not text.isdigit():
        await update.message.reply_text("Iltimos, faqat raqam bilan yozing.")
        return SAVOL

    if key == "yosh" and int(text) < 18:
        await update.message.reply_text(
            "Kechirasiz, anketa faqat 18 yoshdan oshganlar uchun.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    if key == "rozilik" and text != HA:
        await update.message.reply_text(
            "Rozilik bo'lmasa, anketani qabul qila olmaymiz.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END

    context.user_data[key] = text
    i += 1
    context.user_data["i"] = i

    if i < len(SAVOLLAR):
        await savol_ber(update, i)
        return SAVOL

    # Anketa tugadi, adminga yuboramiz
    u = update.effective_user
    qatorlar = ["📝 Yangi anketa", f"ID: {u.id}"]
    if u.username:
        qatorlar.append(f"Username: @{u.username}")
    for k, nom, _ in SAVOLLAR:
        qatorlar.append(f"{nom}: {context.user_data.get(k)}")
    matn = "\n".join(qatorlar)
    rasm_id = context.user_data.get("rasm_id")
    if rasm_id:
        await context.bot.send_photo(ADMIN_ID, rasm_id, caption=matn)
    else:
        await context.bot.send_message(ADMIN_ID, matn)
    await update.message.reply_text(
        "Rahmat! Anketangiz yuborildi. Tez orada javob beramiz.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bekor qilindi. Qayta boshlash: /start", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    quoted = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    m = re.search(r"ID: (\d+)", quoted)
    if not m:
        return
    await context.bot.send_message(int(m.group(1)), f"Admin javobi:\n{msg.text}")
    await msg.reply_text("✅ Yuborildi")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.REPLY & filters.User(ADMIN_ID), admin_reply
        )
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SAVOL: [
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, javob)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)

    if BASE_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=f"{BASE_URL}/{TOKEN}",
        )
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
