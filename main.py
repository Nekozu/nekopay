import telebot
from telebot import types
from pymongo import MongoClient
import logging
from datetime import datetime, timedelta
import sqlite3
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=os.getenv('LOG_LEVEL', 'INFO')
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
ADMIN_CHAT_ID = int(os.getenv('ADMIN_USER_ID'))
MONGO_URI = os.getenv('MONGODB_URI')
BOT_TOKEN = os.getenv('BOT_TOKEN')
PAYMENT_PROVIDER_KEY = os.getenv('PAYMENT_PROVIDER_KEY')
SQLITE_PATH = os.getenv('SQLITE_PATH', '/tmp/support_bot.db')

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client['redeem_db']
one_week_prem = db['1week_prem']
one_month_prem = db['1month_prem']
users_collection = db['users']

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

def check_user_id(user_id):
    # Convert user_id to string before checking
    user = users_collection.find_one({'user_id': str(user_id)})
    if user is None:
        return False
        
    # Check if premium has expired
    if 'expiry' in user and user['expiry']:
        if user['expiry'] < datetime.now():
            # Remove expired user
            users_collection.delete_one({'user_id': str(user_id)})
            one_week_prem.delete_one({'user_id': str(user_id)})
            one_month_prem.delete_one({'user_id': str(user_id)})
            return False
            
    return True

# Function to create the premium keyboard
def create_premium_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Add buy premium button
    buy_premium = types.InlineKeyboardButton(
        text="Buy Premium",
        callback_data="buy_premium"
    )
    
    # Add other buttons
    report_button = types.InlineKeyboardButton(
        text="Report Problem or Suggestion",
        callback_data="report_problem"
    )
    link_button = types.InlineKeyboardButton(
        text="Visit our Telegram",
        url="https://t.me/nekozuX"
    )
    
    keyboard.add(buy_premium, report_button, link_button)
    return keyboard

def payment_methods_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Add premium options
    stars_button = types.InlineKeyboardButton(
        text="Telegram Stars Payment",
        callback_data="stars_payment"
    )
    tranzzo_button = types.InlineKeyboardButton(
        text="Tranzzo Payment", 
        callback_data="tranzzo_payment"
    )
    backs = types.InlineKeyboardButton(
        text="Back",
        callback_data="back"
    )
    
    keyboard.add(stars_button, tranzzo_button, backs)
    return keyboard

def paynow(payment_type):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    # Add premium options with appropriate callback data
    week_button = types.InlineKeyboardButton(
        text="1 Week Premium" + (" (46 Stars)" if payment_type == "stars" else " (€1/1$)"),
        callback_data=f"{payment_type}_week"
    )
    month_button = types.InlineKeyboardButton(
        text="1 Month Premium" + (" (276 Stars)" if payment_type == "stars" else " (€6/6$)"),
        callback_data=f"{payment_type}_month"
    )
    backs = types.InlineKeyboardButton(
        text="Back",
        callback_data="back"
    )
    
    keyboard.add(week_button, month_button, backs)
    return keyboard

def setup_database():
    try:
        with sqlite3.connect(SQLITE_PATH) as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS conversations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            status TEXT NOT NULL,
                            created_at TIMESTAMP NOT NULL,
                            closed_at TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            conversation_id INTEGER NOT NULL,
                            from_user BOOLEAN NOT NULL,
                            message_text TEXT NOT NULL,
                            timestamp TIMESTAMP NOT NULL,
                            FOREIGN KEY (conversation_id) REFERENCES conversations (id))''')
            conn.commit()
        logger.info("Database setup completed successfully")
    except Exception as e:
        logger.error(f"Error setting up database: {e}")

setup_database()

# [Rest of your existing code remains the same...]

@bot.callback_query_handler(func=lambda call: call.data.startswith(("stars_", "ammer_", "tranzzo_")))
def handle_premium_selection(call):
    try:
        chat_id = call.message.chat.id
        payment_type, duration = call.data.split("_")
        
        # Detect user's region based on DC
        dc_id = str(chat_id)[0:3]
        is_europe = dc_id == "234"
        currency = "EUR" if is_europe else "USD"
        
        # Set up prices based on selection and payment type
        if payment_type == "stars":
            if duration == "week":
                amount = 46
                title = "1 Week Premium Access"
                description = "7 days of premium features"
                currency = "XTR"
                provider_token = ""  # Leave empty for Stars payment
            else:
                amount = 276
                title = "1 Month Premium Access"
                description = "30 days of premium features"
                currency = "XTR"
                provider_token = ""  # Leave empty for Stars payment
        else:  # Tranzzo payment
            if duration == "week":
                amount = 100 if currency == "EUR" else 100  # €1 or $1
                title = "1 Week Premium Access"
                description = "7 days of premium features"
                provider_token = PAYMENT_PROVIDER_KEY
            else:
                amount = 600 if currency == "EUR" else 600  # €6 or $6
                title = "1 Month Premium Access"
                description = "30 days of premium features"
                provider_token = PAYMENT_PROVIDER_KEY

        # Create prices array with single price
        prices = [
            types.LabeledPrice(label=title, amount=amount)
        ]

        # Send invoice
        bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            invoice_payload=f"premium_{duration}_{payment_type}",
            provider_token=provider_token,
            currency=currency,
            prices=prices,
            start_parameter="premium-subscription",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False
        )
        
    except Exception as e:
        logger.error(f"Error in premium selection handler: {e}")
        bot.answer_callback_query(call.id, "An unexpected error occurred. Please try again later.", show_alert=True)

@bot.pre_checkout_query_handler(func=lambda query: True)
def handle_pre_checkout_query(pre_checkout_query):
    try:
        bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
    except Exception as e:
        logger.error(f"Error in pre-checkout handler: {e}")
        bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Sorry, there was an error processing your payment. Please try again later."
        )

@bot.message_handler(content_types=['successful_payment'])
def handle_successful_payment(message):
    try:
        payment_info = message.successful_payment

        # Prepare payment data
        payment_data = {
            'user_id': message.from_user.id,
            'username': message.from_user.username,
            'payment_id': payment_info.provider_payment_charge_id,
            'amount': payment_info.total_amount,
            'currency': payment_info.currency,
            'timestamp': message.date
        }

        # Determine subscription duration and store payment
        if payment_info.total_amount == 46:
            one_week_prem.insert_one(payment_data)
            duration = "1 week"
        else:
            one_month_prem.insert_one(payment_data)
            duration = "1 month"

        # Update user's premium status
        users_collection.update_one(
            {'user_id': message.from_user.id},
            {
                '$set': {
                    'is_premium': True,
                    'premium_start': message.date,
                    'premium_duration': duration,
                    'expiry': datetime.now() + timedelta(weeks=1) if duration == "1 week" else datetime.now() + timedelta(weeks=4)
                }
            },
            upsert=True
        )

        # Send success message
        bot.send_message(
            message.chat.id,
            f"✨ Thank you! Your payment of {payment_info.total_amount} Amount has been received!\n\n"
            f"▶️ Your {duration} premium subscription is now active\n\nYou can check it using /info command!"
            "🎉 Enjoy your premium features!"
        )
        bot.send_message(
            ADMIN_CHAT_ID,
            f"Someone just bought premium with amount {payment_info.total_amount}"
        )

    except Exception as e:
        logger.error(f"Error in payment success handler: {e}")
        bot.reply_to(
            message,
            "Your payment was received, but there was an error updating your premium status. "
            "Please contact support using /start and select report with your screenshot the error."
        )

@bot.message_handler(commands=['info'])
def user_info(message):
    try:
        # Get user info
        user = message.from_user
        dc = user.id or "Unknown"
        is_premium = check_user_id(str(user.id))
        premium_status = "Premium User" if is_premium else "Free User"
        
        # Calculate remaining premium duration
        if is_premium:
            user_data = users_collection.find_one({'user_id': str(user.id)})
            if user_data:
                expiry_date = user_data['expiry']
                remaining_time = expiry_date - datetime.now()
                if remaining_time.total_seconds() > 0:
                    days, seconds = divmod(remaining_time.total_seconds(), 86400)
                    hours, _ = divmod(seconds, 3600)
                    premium_duration = f"{int(days)} days, {int(hours)} hours"
                else:
                    premium_duration = "Expired"
            else:
                premium_duration = "Unknown"
        else:
            premium_duration = "N/A"

        # Create keyboard markup
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Upgrade to Premium", callback_data="buy_premium"))

        # Build info text
        info_text = f"👤 First Name: {user.first_name}\n"
        info_text += f"🆔 User ID: `{user.id}`\n"
        info_text += f"🔗 Username: @{user.username}\n" if user.username else ""
        info_text += f"🌐 Data Center: {dc}\n"
        info_text += f"🔰 User Type: {premium_status}\n"
        info_text += f"⏳ Premium Duration: {premium_duration}"

        # Send response as text message
        bot.send_message(
            chat_id=message.chat.id,
            text=info_text,
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error in user info handler: {e}")
        bot.reply_to(message, "Error getting user info. Please try again later.")

# Premium duration checker
def check_premium_duration():
    try:
        # Get all premium users
        premium_users = users_collection.find({})
        current_time = datetime.now()
        
        for user in premium_users:
            user_id = user.get('user_id')
            expiry = user.get('expiry')
            
            if expiry:
                # Calculate remaining days
                remaining_time = expiry - current_time
                remaining_days = remaining_time.days
                
                # If 2 days remaining, send alert
                if remaining_days == 2:
                    try:
                        # Create premium keyboard
                        keyboard = paynow()
                        
                        # Send alert message
                        bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ Premium Alert!\n\n"
                                f"Your premium subscription will expire in 2 days!\n"
                                f"Renew now to keep enjoying premium features:\n"
                                f"• Unlimited translations\n"
                                f"• Larger file size support\n"
                                f"• Priority support\n\n"
                                f"Don't miss out! 🌟",
                            reply_markup=keyboard
                        )
                        
                        # Send alert in English and Indonesian
                        bot.send_message(
                            chat_id=user_id,
                            text="Alert: Your premium will expire soon! Please renew to continue enjoying premium features"
                        )
                        
                    except Exception as e:
                        logger.error(f"Error sending alert to user {user_id}: {e}")
                        
    except Exception as e:
        logger.error(f"Error checking premium duration: {e}")

import time
from apscheduler.schedulers.background import BackgroundScheduler

# Initialize scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(check_premium_duration, 'interval', hours=24)
scheduler.start()

def create_conversation(user_id):
    try:
        # Use /tmp directory for SQLite database
        db_path = '/tmp/support_bot.db'
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO conversations (user_id, status, created_at) 
                        VALUES (?, ?, ?)''', (user_id, 'active', datetime.now().isoformat()))
            conversation_id = c.lastrowid
            return conversation_id
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return None

@bot.callback_query_handler(func=lambda call: call.data == "report_problem")
def handle_report_problem(call):
    try:
        # Check if the user already has an active conversation
        existing_conversation_id = get_active_conversation(call.message.chat.id)
        
        if existing_conversation_id:
            bot.send_message(call.message.chat.id, "You already have an active conversation. Please wait for a response or use /close to end it.")
            return
        
        conversation_id = create_conversation(call.message.chat.id)
        
        if conversation_id:
            bot.send_message(
                call.message.chat.id,
                "Please describe your problem or suggestion. Your message will be sent to our admin team.\n"
                "Use /close when you want to end the conversation."
            )
            bot.register_next_step_handler(call.message, process_report, conversation_id)
        else:
            bot.send_message(call.message.chat.id, "Error starting conversation. Please try again.")
    except Exception as e:
        logger.error(f"Error in report problem handler: {e}")
        bot.send_message(call.message.chat.id, "Error processing your request. Please try again.")

def store_message(conversation_id, from_user, message_text):
    try:
        # Use /tmp directory for SQLite database
        db_path = '/tmp/support_bot.db'
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO messages (conversation_id, from_user, message_text, timestamp)
                        VALUES (?, ?, ?, ?)''', (conversation_id, from_user, message_text, datetime.now().isoformat()))
            return True
    except Exception as e:
        logger.error(f"Error storing message: {e}")
        return False

def process_report(message, conversation_id):
    try:
        if message.text.startswith('/'):
            return  # Ignore commands
        
        report_text = message.text
        
        if store_message(conversation_id, True, report_text):
            admin_message = f"New report from User ID: {message.chat.id}\n" \
                            f"Conversation ID: {conversation_id}\n" \
                            f"Message: {report_text}\n\n" \
                            f"Reply to this message to respond to the user."
            bot.send_message(ADMIN_CHAT_ID, admin_message)
            
            bot.reply_to(
                message,
                "Your message has been sent to our admin team. We'll respond shortly.\n"
                "You can continue sending messages here, or use /close to end the conversation."
            )
            bot.register_next_step_handler(message, process_report, conversation_id)
        else:
            bot.reply_to(message, "Error saving your message. Please try again.")
    except Exception as e:
        logger.error(f"Error processing report: {e}")
        bot.reply_to(message, "Error processing your message. Please try again.")

def get_active_conversation(user_id):
    try:
        # Use /tmp directory for SQLite database
        db_path = '/tmp/support_bot.db'
        with sqlite3.connect(db_path) as conn:
            c = conn.cursor()
            c.execute('''SELECT id FROM conversations WHERE user_id = ? AND status = 'active'
                         ORDER BY created_at DESC LIMIT 1''', (user_id,))
            result = c.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting active conversation: {e}")
        return None

@bot.message_handler(commands=['close'])
def close_conversation(message):
    try:
        # Get the active conversation for the user
        conversation_id = get_active_conversation(message.chat.id)
        
        if conversation_id:
            # Use /tmp directory for SQLite database
            db_path = '/tmp/support_bot.db'
            with sqlite3.connect(db_path) as conn:
                c = conn.cursor()
                
                # Update conversation status to 'closed'
                c.execute('''UPDATE conversations 
                             SET status = 'closed', closed_at = ? 
                             WHERE id = ?''', 
                          (datetime.now().isoformat(), conversation_id))
                conn.commit()  # Commit changes immediately
                
                # After commit, fetch the updated status to ensure correctness
                c.execute('''SELECT status FROM conversations WHERE id = ?''', (conversation_id,))
                status = c.fetchone()
                
                if status and status[0] == 'closed':
                    # Send confirmation to the user
                    bot.send_message(
                        message.chat.id,
                        "Conversation closed. Thank you for contacting us! You can start a new conversation anytime."
                    )
                    
                    # Notify the admin that the conversation has been closed
                    bot.send_message(
                        ADMIN_CHAT_ID,
                        f"Conversation {conversation_id} with User {message.chat.id} has been closed."
                    )
                else:
                    bot.reply_to(message, "Error closing the conversation. Please try again.")
        else:
            bot.reply_to(message, "No active conversation found.")
    
    except Exception as e:
        logger.error(f"Error closing conversation: {e}")
        bot.reply_to(message, "Error closing conversation. Please try again.")

@bot.message_handler(func=lambda message: message.chat.id == int(ADMIN_CHAT_ID) and message.reply_to_message is not None)
def handle_admin_response(message):
    try:
        # Extract conversation context from the original message
        original_message = message.reply_to_message.text
        conversation_lines = original_message.split('\n')
        user_id = None
        conversation_id = None
        
        # Parse the User ID and Conversation ID from the original message
        for line in conversation_lines:
            if "User ID:" in line:
                user_id = int(line.split(": ")[1])
            elif "Conversation ID:" in line:
                conversation_id = int(line.split(": ")[1])
        
        if user_id and conversation_id:
            # Check if conversation is still active
            # Use /tmp directory for SQLite database
            db_path = '/tmp/support_bot.db'
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            c.execute('''SELECT id FROM conversations
                         WHERE id = ? AND status = 'active' ''', (conversation_id,))
            if c.fetchone():
                # Store admin's response
                store_message(conversation_id, False, message.text)
                
                # Forward response to user
                bot.send_message(
                    user_id,
                    f"Admin response: {message.text}\n\n"
                    "You can continue sending messages or use /close to end the conversation."
                )
                
                # Confirm to admin
                bot.reply_to(message, "Response sent to user.")
            else:
                bot.reply_to(message, "This conversation has been closed.")
            
            conn.close()
        else:
            bot.reply_to(message, "Could not determine user ID or conversation ID from the message context.")
    
    except Exception as e:
        logger.error(f"Error handling admin response: {e}")
        bot.reply_to(message, "Error sending response. Please try again.")

if __name__ == '__main__':
    bot.infinity_polling()
