import os
import re

from telegram import ReplyKeyboardRemove, ReplyParameters, Update
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

# (kalit, admin uchun nomi, savol matni)
SAVOLLAR = [
    ("ism", "Ism", "Ismingiz?"),
    ("hudud", "Qayerdan", "Qayerdansiz?"),
    ("kerak_hudud", "Qayerlik kerak", "Qayerlik kerak?"),
    ("yosh", "Yosh", "Yoshingiz nechida?"),
    ("sm", "Sm (o'zi / kerak)", "Necha sm 👦 yoki necha sm kerak 👩?"),
    ("rasm", "Rasm", "Rasmingizni yuboring. U faqat adminga ko'rinadi."),
]

SAVOL = 0


async def savol_ber(update: Update, i: int):
    await update.message.reply_text(
        SAVOLLAR[i][2], reply_markup=ReplyKeyboardRemove()
    )


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

    if key == "yosh":
        # Har qanday matn qabul qilinadi ("25", "25 yosh"...), bot qotib qolmaydi.
        # Faqat aniq 18 dan kichik son yozilsa to'xtaydi.
        son = re.search(r"\d+", text)
        if son and 0 < int(son.group()) < 18:
            await msg.reply_text(
                "Kechirasiz, anketa faqat 18 yoshdan oshganlar uchun."
            )
            return ConversationHandler.END

    context.user_data[key] = text
    i += 1
    context.user_data["i"] = i

    if i < len(SAVOLLAR):
        await savol_ber(update, i)
        return SAVOL

    # Anketa tugadi: adminga yuboramiz
    u = update.effective_user
    qatorlar = ["📝 Yangi anketa", f"ID: {u.id}"]
    if u.username:
        qatorlar.append(f"Username: @{u.username}")
    for k, nom, _ in SAVOLLAR:
        if k != "rasm":
            qatorlar.append(f"{nom}: {context.user_data.get(k)}")
    matn = "\n".join(qatorlar)
    await context.bot.send_photo(
        ADMIN_ID, context.user_data["rasm_id"], caption=matn
    )

    await msg.reply_text("Sizga juft izlanmoqda 🔎")
    await msg.reply_text("Yuborildi ❤️")
    return ConversationHandler.END


async def savolda_boshqa_tur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Iltimos, savolga matn bilan (yoki so'ralsa, rasm bilan) javob bering."
    )
    return SAVOL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bekor qilindi. Qayta boshlash: /start", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin istalgan turdagi xabar bilan reply qilsa, foydalanuvchiga boradi."""
    msg = update.message
    quoted = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    m = re.search(r"ID: (\d+)", quoted)
    if m:
        uid = int(m.group(1))
    else:
        uid = context.bot_data.get("map", {}).get(msg.reply_to_message.message_id)
    if not uid:
        await msg.reply_text(
            "Bu xabar egasini topa olmadim. 'ID: ...' yozilgan xabarga reply qiling."
        )
        return

    if msg.text:
        await context.bot.send_message(uid, f"Admin javobi:\n{msg.text}")
    else:
        await context.bot.send_message(uid, "Admin javobi:")
        await context.bot.copy_message(
            chat_id=uid, from_chat_id=msg.chat_id, message_id=msg.message_id
        )
    await msg.reply_text("✅ Yuborildi")


async def foydalanuvchi_xabari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anketadan keyingi xabarlar (matn, rasm, video, ovoz...) adminga boradi."""
    msg = update.message
    u = update.effective_user
    bosh = f"💬 Yangi xabar\nID: {u.id}"
    if u.username:
        bosh += f"\nUsername: @{u.username}"

    if msg.text:
        await context.bot.send_message(ADMIN_ID, bosh + "\n\n" + msg.text)
    elif (
        msg.photo or msg.video or msg.voice or msg.audio or msg.document or msg.animation
    ):
        # Ma'lumot fayl ostiga yoziladi: hammasi bitta xabar bo'lib keladi
        sarlavha = (bosh + "\n\n" + (msg.caption or ""))[:1000]
        await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
            caption=sarlavha,
        )
    else:
        # Dumaloq video va stiker ostiga matn yozib bo'lmaydi: ikkita xabar
        sarlavha = await context.bot.send_message(ADMIN_ID, bosh)
        nusxa = await context.bot.copy_message(
            chat_id=ADMIN_ID,
            from_chat_id=msg.chat_id,
            message_id=msg.message_id,
            reply_parameters=ReplyParameters(message_id=sarlavha.message_id),
        )
        context.bot_data.setdefault("map", {})[nusxa.message_id] = u.id
    await msg.reply_text("Yuborildi ❤️")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        MessageHandler(
            filters.REPLY & filters.User(ADMIN_ID) & ~filters.COMMAND, admin_reply
        )
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SAVOL: [
                MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, javob),
                MessageHandler(
                    ~filters.COMMAND & ~filters.TEXT & ~filters.PHOTO, savolda_boshqa_tur
                ),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)

    # Anketadan keyin foydalanuvchi yozgan hamma narsa adminga boradi
    app.add_handler(
        MessageHandler(~filters.COMMAND & ~filters.User(ADMIN_ID), foydalanuvchi_xabari)
    )

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
