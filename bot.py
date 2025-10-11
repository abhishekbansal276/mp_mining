import os
import asyncio
import shutil
from glob import glob

from telegram import Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    ConversationHandler,
)

from fetch_emm11_data import fetch_emm11_data
from pdf_gen import pdf_gen  # Generates PDFs and (expected) merged PDF

BOT_TOKEN = '7997144945:AAHuIcNSGHXhc3iW3gfWs6wn20-2XmvwG7A'

ASK_START, ASK_END, ASK_DISTRICT = range(3)
user_sessions = {}

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Welcome! Enter the start number:")
    return ASK_START

def ask_start(update: Update, context: CallbackContext):
    try:
        context.user_data['start'] = int(update.message.text)
        update.message.reply_text("Enter the end number:")
        return ASK_END
    except ValueError:
        update.message.reply_text("⚠️ Enter a valid number.")
        return ASK_START

def ask_end(update: Update, context: CallbackContext):
    try:
        context.user_data['end'] = int(update.message.text)
        update.message.reply_text("Enter the district name:")
        return ASK_DISTRICT
    except ValueError:
        update.message.reply_text("⚠️ Enter a valid number.")
        return ASK_END

def ask_district(update: Update, context: CallbackContext):
    district = update.message.text
    start = context.user_data['start']
    end = context.user_data['end']
    user_id = update.effective_user.id

    update.message.reply_text(f"Fetching data for district: {district}...")

    # store session
    user_sessions[user_id] = {"start": start, "end": end, "district": district, "data": []}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def send_entry(entry):
        if not entry:
            return
        istp = entry.get("istp")
        ostp = entry.get("ostp")
        dest = entry.get("destination_district")
        valid = entry.get("valid_upto")
        generated = entry.get("generated_on")
        qty = entry.get("qty")
        msg = f"ISTP: {istp}\nOSTP: {ostp}\nDistrict: {dest}\nValid Up To: {valid}\nGenerated On: {generated}\nQty: {qty}"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
        user_sessions[user_id]["data"].append(entry)

    async def run_fetch():
        await fetch_emm11_data(start, end, district, data_callback=send_entry, log=print)

    loop.run_until_complete(run_fetch())

    entries = user_sessions[user_id]["data"]
    if not entries:
        update.message.reply_text("No data found.")
        return ConversationHandler.END

    # build TP list (all ISTP values)
    tp_num_list = [e.get("istp") for e in entries if e.get("istp")]
    if not tp_num_list:
        update.message.reply_text("No TP numbers found in fetched data.")
        return ConversationHandler.END

    update.message.reply_text(f"Generating PDFs for {len(tp_num_list)} TP(s)... This may take a while.")

    async def run_pdf_gen():
        # send logs back to user
        def log_cb(m):
            context.bot.send_message(chat_id=update.effective_chat.id, text=m)
        # call pdf_gen (expected to create merged PDF and return its path or similar)
        return await pdf_gen(tp_num_list, template_path="mp_format.pdf", log_callback=log_cb, send_pdf_callback=None)

    result = loop.run_until_complete(run_pdf_gen())

    # Try to locate merged PDF
    merged_candidates = []
    if isinstance(result, str):
        merged_candidates.append(result)
    elif isinstance(result, (list, tuple)):
        # if pdf_gen returned list of generated files, look for a merged file in pdf dir
        merged_candidates.extend(result)
    # common fallback names
    merged_candidates.extend([
        "pdf/merged_tp.pdf",
        "pdf/All_TP.pdf",
        "pdf/merged.pdf",
        "pdf/AllTP.pdf"
    ])
    # also search for any file in pdf dir with "merged" or "All"
    merged_candidates.extend(glob("pdf/*merged*.pdf"))
    merged_candidates.extend(glob("pdf/*All*.pdf"))

    merged_path = None
    for p in merged_candidates:
        if p and os.path.exists(p):
            merged_path = p
            break

    if merged_path:
        with open(merged_path, "rb") as f:
            context.bot.send_document(chat_id=update.effective_chat.id,
                                      document=f,
                                      filename=os.path.basename(merged_path),
                                      caption="Merged PDF with all generated TP PDFs")
        update.message.reply_text("✅ Merged PDF sent.")
    else:
        update.message.reply_text("❌ Merged PDF not found on server. Check pdf_gen output or merged filename.")

    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("🚫 Operation cancelled.")
    return ConversationHandler.END

def main():
    try:
        shutil.rmtree("pdf")
    except Exception:
        pass

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_START: [MessageHandler(Filters.text & ~Filters.command, ask_start)],
            ASK_END: [MessageHandler(Filters.text & ~Filters.command, ask_end)],
            ASK_DISTRICT: [MessageHandler(Filters.text & ~Filters.command, ask_district)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    dp.add_handler(conv_handler)

    print("🤖 Bot running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
