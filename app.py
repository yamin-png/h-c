import telebot
from telebot import types
import requests
import concurrent.futures
import re
import time
import io

# Apnar dewa Telegram Bot API Token
TOKEN = "8631817008:AAGAsL4KdAU-kegg9kGA-dwJmk5Q53jKuX0"
bot = telebot.TeleBot(TOKEN)

# User session data store korar dictionary
# Format: {chat_id: {'emails': set(), 'is_processing': False}}
user_sessions = {}

def get_session(chat_id):
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {'emails': set(), 'is_processing': False}
    return user_sessions[chat_id]

def check_email(email, session):
    """
    Microsoft er API endpoint theke email available kina check korbe.
    Uses requests.Session() for connection pooling (faster requests).
    """
    availableText = "Neither"
    link = f"https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=0&emailAddress={email}&_=1604288577990"
    header = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36",
        "Connection": "keep-alive",
        "Host": "odc.officeapps.live.com",
        "Accept-Encoding": "gzip, deflate",
    }
    
    try:
        response = session.get(link, headers=header, timeout=10).text
        if availableText in response:
            return email 
    except requests.exceptions.RequestException:
        pass # Ignore network errors
    
    return None

def generate_progress_bar(current, total, length=15):
    """Progress bar toiri korar jonno helper function"""
    percent = current / total
    filled = int(length * percent)
    bar = '█' * filled + '░' * (length - filled)
    return f"[{bar}] {int(percent * 100)}%"

# Inline Keyboard UI
def get_control_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_process = types.InlineKeyboardButton("🚀 Process Now", callback_data="process_emails")
    btn_clear = types.InlineKeyboardButton("🗑️ Clear List", callback_data="clear_buffer")
    markup.add(btn_process, btn_clear)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 <b>Welcome to the Pro Mail Checker Bot!</b>\n\n"
        "Send me the emails you want to check. You can send them one by one or as a bulk list.\n\n"
        "<i>When you are ready, click the 'Process Now' button below or type 'done'.</i>"
    )
    bot.reply_to(message, welcome_text, parse_mode="HTML")
    get_session(message.chat.id) # Initialize session

@bot.message_handler(func=lambda message: message.text.lower().strip() == 'done')
def trigger_process_text(message):
    execute_checking(message.chat.id)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    user_data = get_session(chat_id)
    
    if call.data == "process_emails":
        if user_data['is_processing']:
            bot.answer_callback_query(call.id, "⚠️ Already processing your previous request!", show_alert=True)
            return
        bot.answer_callback_query(call.id, "Starting the check...")
        execute_checking(chat_id)
        
    elif call.data == "clear_buffer":
        if user_data['is_processing']:
            bot.answer_callback_query(call.id, "⚠️ Cannot clear while processing!", show_alert=True)
            return
        user_data['emails'].clear()
        bot.answer_callback_query(call.id, "Buffer cleared!")
        try:
            bot.edit_message_text("🗑️ <b>Your email list has been cleared.</b> Send new emails to start again.", 
                                  chat_id, call.message.message_id, parse_mode="HTML")
        except:
            pass # Ignore if message is exactly the same

def execute_checking(chat_id):
    user_data = get_session(chat_id)
    
    if not user_data['emails']:
        bot.send_message(chat_id, "⚠️ <b>Your list is empty.</b> Please send some emails first.", parse_mode="HTML")
        return
        
    if user_data['is_processing']:
        bot.send_message(chat_id, "⚠️ <b>A checking process is already running.</b> Please wait.", parse_mode="HTML")
        return
    
    user_data['is_processing'] = True
    emails_to_check = list(user_data['emails'])
    total_emails = len(emails_to_check)
    
    status_msg = bot.send_message(chat_id, f"⏳ <b>Initializing scan for {total_emails} emails...</b>", parse_mode="HTML")
    
    start_time = time.time()
    available_emails = []
    checked_count = 0
    last_update_time = time.time()
    
    # Using requests.Session() to make connections faster
    http_session = requests.Session()
    
    # ThreadPoolExecutor for concurrent checking
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        # Submit all tasks
        futures = {executor.submit(check_email, email, http_session): email for email in emails_to_check}
        
        # Process them as they complete to update the progress bar
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            checked_count += 1
            if res:
                available_emails.append(res)
            
            # Update UI every 2 seconds to avoid Telegram API rate limits
            current_time = time.time()
            if current_time - last_update_time > 2.0 or checked_count == total_emails:
                progress_bar = generate_progress_bar(checked_count, total_emails)
                time_elapsed = int(current_time - start_time)
                
                update_text = (
                    f"⚙️ <b>Processing Emails...</b>\n\n"
                    f"{progress_bar}\n"
                    f"🔍 Checked: {checked_count}/{total_emails}\n"
                    f"🎯 Found: {len(available_emails)}\n"
                    f"⏱️ Elapsed Time: {time_elapsed}s"
                )
                try:
                    bot.edit_message_text(update_text, chat_id, status_msg.message_id, parse_mode="HTML")
                    last_update_time = current_time
                except Exception:
                    pass # Telegram raises error if message content is exactly the same
                
    elapsed_time = round(time.time() - start_time, 2)
    user_data['is_processing'] = False
    user_data['emails'].clear() # Auto clear buffer after process
    
    # Formatting the final result
    if available_emails:
        final_text = (
            f"✅ <b>Checking Completed Successfully!</b>\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"├ Total Checked: {total_emails}\n"
            f"├ Available (Hits): {len(available_emails)}\n"
            f"└ Time Taken: {elapsed_time}s\n\n"
        )
        
        emails_formatted = "\n".join([f"<code>{email}</code>" for email in available_emails])
        
        # If output is too long, send as an in-memory file instead of writing to disk
        if len(final_text + emails_formatted) > 4000:
            file_buffer = io.BytesIO("\n".join(available_emails).encode('utf-8'))
            file_buffer.name = f"Hits_{chat_id}.txt"
            
            caption_text = final_text + "<i>⚠️ Too many hits! I've sent them as a file instead.</i>"
            bot.send_document(chat_id, file_buffer, caption=caption_text, parse_mode="HTML")
            bot.delete_message(chat_id, status_msg.message_id)
        else:
            final_text += "👇 <b>Available Emails (Tap to copy):</b>\n\n" + emails_formatted
            bot.edit_message_text(final_text, chat_id, status_msg.message_id, parse_mode="HTML")
    else:
        fail_text = (
            f"❌ <b>Checking Completed!</b>\n\n"
            f"📊 <b>Statistics:</b>\n"
            f"├ Total Checked: {total_emails}\n"
            f"├ Available (Hits): 0\n"
            f"└ Time Taken: {elapsed_time}s\n\n"
            f"<i>No available emails found in this batch. Better luck next time!</i>"
        )
        bot.edit_message_text(fail_text, chat_id, status_msg.message_id, parse_mode="HTML")

@bot.message_handler(func=lambda message: True)
def buffer_emails(message):
    chat_id = message.chat.id
    user_data = get_session(chat_id)
    
    if user_data['is_processing']:
        bot.reply_to(message, "⚠️ <b>Please wait!</b> I am currently processing your previous list.", parse_mode="HTML")
        return
    
    extracted_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message.text)
    
    if extracted_emails:
        user_data['emails'].update(extracted_emails)
        bot.reply_to(message, 
                     f"✅ <b>Added {len(extracted_emails)} valid emails!</b>\n"
                     f"📦 <b>Total in buffer:</b> {len(user_data['emails'])}\n\n"
                     f"<i>Send more emails or use the buttons below to act.</i>", 
                     parse_mode="HTML", 
                     reply_markup=get_control_keyboard())
    else:
        bot.reply_to(message, "⚠️ No valid emails found in your message. Please send proper emails.")

if __name__ == '__main__':
    print("🚀 Pro Bot is running with Live Progress, Memory Files, and Session Pooling...")
    bot.infinity_polling(timeout=20, long_polling_timeout=15)
