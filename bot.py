import os
import asyncio
import shutil

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    CallbackContext,
    ConversationHandler,
)
from fetch_emm11_data import fetch_emm11_data
from login_to_website import login_to_website
from pdf_gen import pdf_gen  # Generates single merged PDF

BOT_TOKEN = '7906139442:AAFxv2ZHapH4nvmkkL87Jd9eZ7OAXxNg4hw'

ASK_START, ASK_END, ASK_DISTRICT = range(3)
user_sessions = {}

# ---------------- Conversation Handlers ----------------

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

    # Store session
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

    if user_sessions[user_id]["data"]:
        keyboard = [
            [InlineKeyboardButton("Start Again", callback_data="start_again")],
            [InlineKeyboardButton("Login & Process", callback_data="login_process")],
            [InlineKeyboardButton("Exit", callback_data="exit_process")],
        ]
        update.message.reply_text("Data fetched. Choose an option:", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        update.message.reply_text("No data found.")

    return ConversationHandler.END

# ---------------- Callback Button Handler ----------------

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id

    if user_id not in user_sessions:
        query.edit_message_text("⚠️ Session expired. Please type /start.")
        return

    session = user_sessions[user_id]

    if query.data == "start_again":
        query.edit_message_text("🔁 Restarting...")
        context.bot.send_message(chat_id=query.message.chat.id, text="/start")
        user_sessions.pop(user_id, None)
        return

    elif query.data == "exit_process":
        query.edit_message_text("❌ Exiting process.")
        user_sessions.pop(user_id, None)
        return

    elif query.data == "login_process":
        query.edit_message_text("Processing entries...")

        async def process_and_prompt():
            def log_callback(msg):
                context.bot.send_message(chat_id=query.message.chat.id, text=msg)

            # Run login and mark unused TP pairs
            processed_entries = await login_to_website(session["data"], log_callback=log_callback)

            if not processed_entries:
                context.bot.send_message(chat_id=query.message.chat.id,
                                         text="❌ Failed to process entries.")
                return

            session["data"] = processed_entries

            # Extract TP numbers that are unused
            tp_num_list = [entry['istp'] for entry in processed_entries if entry.get("unused")]

            if not tp_num_list:
                context.bot.send_message(chat_id=query.message.chat.id,
                                         text="⚠️ No unused TP pairs found. PDF cannot be generated.")
                return

            context.user_data["tp_num_list"] = tp_num_list

            keyboard = [
                [InlineKeyboardButton("📄 Generate PDF", callback_data="generate_pdf")],
                [InlineKeyboardButton("❌ Exit", callback_data="exit_process")]
            ]
            context.bot.send_message(chat_id=query.message.chat.id,
                                     text="✅ Generate PDF for unused TP pairs:",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_and_prompt())

    elif query.data == "generate_pdf":
        tp_num_list = context.user_data.get("tp_num_list", [])
        if not tp_num_list:
            query.edit_message_text("⚠️ No TP numbers. Process again.")
            return

        async def generate_and_store():
            merged_pdf_path = await pdf_gen(
                tp_num_list,
                log_callback=lambda msg: context.bot.send_message(chat_id=query.message.chat.id, text=msg),
                send_pdf_callback=None
            )
            return merged_pdf_path

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        merged_pdf_path = loop.run_until_complete(generate_and_store())

        if merged_pdf_path and os.path.exists(merged_pdf_path):
            keyboard = [[InlineKeyboardButton("📄 Download All TP PDF", callback_data="download_merged_pdf")]]
            keyboard.append([InlineKeyboardButton("❌ Exit", callback_data="exit_process")])
            context.bot.send_message(chat_id=query.message.chat.id,
                                     text="✅ Click below to download the merged PDF for all unused TP pairs:",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            context.bot.send_message(chat_id=query.message.chat.id,
                                     text="❌ Failed to generate merged PDF.")

    elif query.data == "download_merged_pdf":
        merged_pdf_path = "pdf/All_TP.pdf"
        if os.path.exists(merged_pdf_path):
            with open(merged_pdf_path, "rb") as f:
                context.bot.send_document(chat_id=query.message.chat.id,
                                          document=f,
                                          filename="All_TP.pdf",
                                          caption="PDF containing all unused TP pairs")
        else:
            context.bot.send_message(chat_id=query.message.chat.id,
                                     text="❌ Merged PDF not found. Please generate again.")

# ---------------- Cancel Handler ----------------

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("🚫 Operation cancelled.")
    return ConversationHandler.END

# ---------------- Main ----------------

def main():
    try:
        shutil.rmtree("pdf")
    except:
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
    dp.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot running...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()