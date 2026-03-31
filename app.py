import telebot
from telebot import types
import requests
import concurrent.futures
import re
import os
import time

# Apnar dewa Telegram Bot API Token
TOKEN = "8631817008:AAGAsL4KdAU-kegg9kGA-dwJmk5Q53jKuX0"
bot = telebot.TeleBot(TOKEN)

# User der email buffer korar jonno memory te save rakhar dictionary
user_buffers = {}

def check_email(email):
    """
    Microsoft er API endpoint theke email available kina check korbe.
    """
    availableText = "Neither"
    link = "https://odc.officeapps.live.com/odc/emailhrd/getidp?hm=0&emailAddress=" + email + "&_=1604288577990"
    header = {
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.83 Safari/537.36",
        "Connection": "close",
        "Host": "odc.officeapps.live.com",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://odc.officeapps.live.com/odc/v2.0/hrd?rs=ar-sa&Ver=16&app=23&p=6&hm=0",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "canary": "BCfKjqOECfmW44Z3Ca7vFrgp9j3V8GQHKh6NnEESrE13SEY/4jyexVZ4Yi8CjAmQtj2uPFZjPt1jjwp8O5MXQ5GelodAON4Jo11skSWTQRzz6nMVUHqa8t1kVadhXFeFk5AsckPKs8yXhk7k4Sdb5jUSpgjQtU2Ydt1wgf3HEwB1VQr+iShzRD0R6C0zHNwmHRnIatjfk0QJpOFHl2zH3uGtioL4SSusd2CO8l4XcCClKmeHJS8U3uyIMJQ8L+tb:2:3c",
        "uaid": "d06e1498e7ed4def9078bd46883f187b",
        "Cookie": "xid=d491738a-bb3d-4bd6-b6ba-f22f032d6e67&&RD00155D6F8815&354"
    }
    
    try:
        response = requests.get(link, headers=header, timeout=10).text
        if availableText in response:
            return email # Sudhu available holei email ta return korbe
    except Exception as e:
        pass
    
    return None

# Inline Keyboard UI toiri korar function
def get_control_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_process = types.InlineKeyboardButton("🚀 Process Now", callback_data="process_emails")
    btn_clear = types.InlineKeyboardButton("🗑️ Clear List", callback_data="clear_buffer")
    markup.add(btn_process, btn_clear)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 <b>Welcome to the Mail Checker Bot!</b>\n\n"
        "Send me the emails you want to check. You can send them one by one or as a bulk list.\n\n"
        "<i>When you are ready, click the 'Process Now' button below or type 'done'.</i>"
    )
    bot.reply_to(message, welcome_text, parse_mode="HTML")
    user_buffers[message.chat.id] = set()

# 'done' text er command
@bot.message_handler(func=lambda message: message.text.lower().strip() == 'done')
def trigger_process_text(message):
    execute_checking(message.chat.id)

# Inline buttons er click handle korar logic
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    chat_id = call.message.chat.id
    if call.data == "process_emails":
        bot.answer_callback_query(call.id, "Starting the check...")
        execute_checking(chat_id)
    elif call.data == "clear_buffer":
        user_buffers[chat_id] = set()
        bot.answer_callback_query(call.id, "Buffer cleared!")
        bot.edit_message_text("🗑️ <b>Your email list has been cleared.</b> Send new emails to start again.", 
                              chat_id, call.message.message_id, parse_mode="HTML")

def execute_checking(chat_id):
    if chat_id not in user_buffers or len(user_buffers[chat_id]) == 0:
        bot.send_message(chat_id, "⚠️ <b>Your list is empty.</b> Please send some emails first.", parse_mode="HTML")
        return
    
    emails_to_check = list(user_buffers[chat_id])
    status_msg = bot.send_message(chat_id, f"⏳ <b>Processing {len(emails_to_check)} emails...</b>\n<i>Please wait, this might take a while depending on the list size.</i>", parse_mode="HTML")
    
    start_time = time.time()
    available_emails = []
    
    # ThreadPoolExecutor use kore eksathe multiple mail check kora hocche
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_email, emails_to_check)
        for res in results:
            if res:
                available_emails.append(res)
                
    elapsed_time = round(time.time() - start_time, 2)
    
    # Check sesh hobar por output dewa hocche
    if available_emails:
        # Special Feature: HTML <code> tag use koray mail gulo 1-click a copy hobe
        response_text = f"✅ <b>Checking Completed!</b>\n⏱️ <b>Time Taken:</b> {elapsed_time}s\n🎯 <b>Available:</b> {len(available_emails)}/{len(emails_to_check)}\n\n"
        response_text += "👇 <b>Available Emails (Tap to copy):</b>\n\n"
        response_text += "\n".join([f"<code>{email}</code>" for email in available_emails])
        
        # Jodi email list onek boro hoy (Telegram limit er theke beshi), tahole text file e dibe
        if len(response_text) > 4000:
            filename = f"available_emails_{chat_id}.txt"
            with open(filename, "w") as f:
                f.write("\n".join(available_emails))
            with open(filename, "rb") as f:
                caption_text = f"✅ <b>Checking Completed!</b>\n⏱️ Time: {elapsed_time}s\n🎯 Available: {len(available_emails)}\n\n<i>List is too long, so I've sent it as a file.</i>"
                bot.send_document(chat_id, f, caption=caption_text, parse_mode="HTML")
            os.remove(filename) # Pathanor por file delete kore dibe
            bot.delete_message(chat_id, status_msg.message_id) # Process msg delete
        else:
            bot.edit_message_text(response_text, chat_id, status_msg.message_id, parse_mode="HTML")
    else:
        bot.edit_message_text(f"❌ <b>Checking Completed!</b>\n⏱️ <b>Time:</b> {elapsed_time}s\n\nNo available emails found out of {len(emails_to_check)} checked.", chat_id, status_msg.message_id, parse_mode="HTML")
        
    # Processing sesh, buffer clear kore dicchi
    user_buffers[chat_id] = set()

@bot.message_handler(func=lambda message: True)
def buffer_emails(message):
    chat_id = message.chat.id
    
    if chat_id not in user_buffers:
        user_buffers[chat_id] = set()
    
    # User er message theke regex diye valid email gulo ber kora hocche
    extracted_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', message.text)
    
    if extracted_emails:
        user_buffers[chat_id].update(extracted_emails)
        bot.reply_to(message, 
                     f"✅ <b>Added {len(extracted_emails)} valid emails!</b>\n"
                     f"📦 <b>Total in buffer:</b> {len(user_buffers[chat_id])}\n\n"
                     f"<i>Send more emails or use the buttons below to act.</i>", 
                     parse_mode="HTML", 
                     reply_markup=get_control_keyboard())
    else:
        bot.reply_to(message, "⚠️ No valid emails found in your message. Please send proper emails.")

if __name__ == '__main__':
    print("Bot is running with UI and special features...")
    # VPS e always run korar jonno infinity_polling() use kora hoyeche
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
