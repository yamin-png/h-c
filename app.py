import telebot
import requests
import concurrent.futures
import re
import os

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

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Welcome! Send me the emails you want to check. You can send them one by one or as a bulk list.\n\nType 'done' when you are finished sending emails.")
    user_buffers[message.chat.id] = set()

@bot.message_handler(func=lambda message: message.text.lower().strip() == 'done')
def process_emails(message):
    chat_id = message.chat.id
    
    if chat_id not in user_buffers or len(user_buffers[chat_id]) == 0:
        bot.reply_to(message, "Your buffer is empty. Please send some emails first.")
        return
    
    emails_to_check = list(user_buffers[chat_id])
    bot.reply_to(message, f"Processing {len(emails_to_check)} emails. Please wait, this might take a while...")
    
    available_emails = []
    
    # ThreadPoolExecutor use kore eksathe multiple mail check kora hocche
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_email, emails_to_check)
        for res in results:
            if res:
                available_emails.append(res)
    
    # Check sesh hobar por output dewa hocche
    if available_emails:
        response_text = "Available Emails:\n" + "\n".join(available_emails)
        
        # Jodi email list onek boro hoy (Telegram limit er theke beshi), tahole text file e dibe
        if len(response_text) > 4000:
            filename = f"available_emails_{chat_id}.txt"
            with open(filename, "w") as f:
                f.write(response_text)
            with open(filename, "rb") as f:
                bot.send_document(chat_id, f)
            os.remove(filename) # Pathanor por file delete kore dibe
        else:
            bot.send_message(chat_id, response_text)
    else:
        bot.send_message(chat_id, "Checking completed. No available emails found.")
        
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
        user_buffers[chat_id].update(extracted_emails) # Duplicate remove korar jonno set use kora hoyeche
        bot.reply_to(message, f"Added {len(extracted_emails)} valid emails. Total in buffer: {len(user_buffers[chat_id])}.\n\nSend more emails or type 'done' to start checking.")
    else:
        bot.reply_to(message, "No valid emails found in your message. Please send proper emails or type 'done' to start.")

if __name__ == '__main__':
    print("Bot is running...")
    # VPS e always run korar jonno infinity_polling() use kora hoyeche
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
