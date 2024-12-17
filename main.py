import telebot
from telebot import types
from pymongo import MongoClient
import logging
from datetime import datetime, timedelta
import sqlite3
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get environment variables
ADMIN_CHAT_ID = int(os.getenv('ADMIN_CHAT_ID'))
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URL = os.getenv('MONGO_URL')
TRANZZO_TOKEN = os.getenv('TRANZZO_TOKEN')
PAYPAL_WEEK_INVOICE = os.getenv('PAYPAL_WEEK_INVOICE')
PAYPAL_MONTH_INVOICE = os.getenv('PAYPAL_MONTH_INVOICE')
CRYPTOCLOUD_TOKEN = os.getenv('CRYPTOCLOUD_TOKEN')
CRYPTOCLOUD_SHOP_ID = os.getenv('CRYPTOCLOUD_SHOP_ID')

# MongoDB setup
client = MongoClient(MONGO_URL)
db = client['redeem_db']
one_week_prem = db['1week_prem']
one_month_prem = db['1month_prem']
users_collection = db['users']
transactionsCollection = db['transactions']

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
        text="Card Payment", 
        callback_data="tranzzo_payment"
    )
    paypal_button = types.InlineKeyboardButton(
        text="Paypal Payment", 
        callback_data="paypal_payment"
    )
    crypto_button = types.InlineKeyboardButton(
        text="Crypto Payment", 
        callback_data="crypto_payment"
    )
    backs = types.InlineKeyboardButton(
        text="Back",
        callback_data="back"
    )
    
    keyboard.add(stars_button, tranzzo_button, paypal_button, crypto_button, backs)
    return keyboard

def paypal_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    week_button = types.InlineKeyboardButton(
        text="1 Week Premium (€1/1$)", 
        url=PAYPAL_WEEK_INVOICE
    )
    month_button = types.InlineKeyboardButton(
        text="1 Month Premium (€6/6$)", 
        url=PAYPAL_MONTH_INVOICE
    )
    photo_button = types.InlineKeyboardButton(
        text="Send Payment Screenshot",
        callback_data="send_payment_screenshot"
    )
    backs = types.InlineKeyboardButton(
        text="Back",
        callback_data="back"
    )
    keyboard.add(week_button, month_button, photo_button, backs)
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
        # Use /tmp directory for SQLite database on Vercel
        db_path = '/tmp/support_bot.db'
        with sqlite3.connect(db_path) as conn:
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

# Handler for the '/start' command
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        # Create the inline keyboard with all the buttons
        keyboard = create_premium_keyboard()

        # Send the message with the inline keyboard
        bot.send_message(
            message.chat.id,
            "🌟 Welcome to Nekozu Support And Payment! Choose an option below:",
            reply_markup=keyboard
        )
    except Exception as e:
        bot.reply_to(message, "Sorry, there was an error. Please try again later.")
        print(f"Error in start handler: {e}")
      
@bot.callback_query_handler(func=lambda call: call.data == "buy_premium")
def handleprem(call):
    keyboard = payment_methods_keyboard()
    bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        
@bot.callback_query_handler(func=lambda call: call.data in ["stars_payment", "ammer_payment", "tranzzo_payment"])
def handlepay(call):
    payment_type = "stars" if call.data == "stars_payment" else "ammer" if call.data == "ammer_payment" else "tranzzo"
    keyboard = paynow(payment_type)
    bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
    
@bot.callback_query_handler(func=lambda call: call.data == "back")    
def handleback(call):
    keyboard = create_premium_keyboard()
    bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
    
@bot.callback_query_handler(func=lambda call: call.data.startswith(("stars_", "tranzzo_")))
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
                provider_token = TRANZZO_TOKEN
            else:
                amount = 600 if currency == "EUR" else 600  # €6 or $6
                title = "1 Month Premium Access"
                description = "30 days of premium features"
                provider_token = TRANZZO_TOKEN

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
        
    except telebot.apihelper.ApiTelegramException as telegram_error:
        logger.error(f"Telegram API error: {telegram_error}")
        error_message = "There was an error processing your payment request. Please try again later."
        if "STARS_INVOICE_INVALID" in str(telegram_error):
            error_message = "Invalid Stars payment configuration. Please contact support."
        bot.answer_callback_query(call.id, error_message, show_alert=True)
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
        duration = "1week" if payment_info.total_amount == 46 else "1month"
        expiry = datetime.now() + timedelta(weeks=1 if duration == "1week" else 4)

        # Prepare payment data
        payment_data = {
            'user_id': str(message.from_user.id),
            'username': message.from_user.username,
            'payment_id': payment_info.provider_payment_charge_id,
            'amount': payment_info.total_amount,
            'currency': payment_info.currency,
            'timestamp': message.date,
            'expiry_date': expiry
        }

        # Store payment in appropriate collection
        if duration == "1week":
            one_week_prem.insert_one(payment_data)
        else:
            one_month_prem.insert_one(payment_data)

        # Update user's premium status
        users_collection.update_one(
            {'user_id': str(message.from_user.id)},
            {
                '$set': {
                    'is_premium': True,
                    'premium_start': datetime.now(),
                    'premium_duration': duration,
                    'expiry': expiry
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

@bot.callback_query_handler(func=lambda call: call.data == "paypal_payment")
def handle_paypal(call):
    keyboard = paypal_keyboard()
    text = "Pay using paypal using this link. after payment send you payment screenshot with clicking this button"
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.id, text=text, reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data == "send_payment_screenshot")
def handle_send_payment_screenshot(call):
    msg = bot.send_message(call.message.chat.id, "Please send your payment screenshot.")
    bot.register_next_step_handler(msg, process_payment_screenshot)

@bot.message_handler(content_types=['photo'])
def process_payment_screenshot(message):
    # Check if this is a response to send_payment_screenshot
    if not hasattr(message, 'reply_to_message') or not message.reply_to_message or \
       not hasattr(message.reply_to_message, 'text') or \
       message.reply_to_message.text != "Please send your payment screenshot. Make sure to send correct screenshot and replying to this message":
        return

    try:
        # Create admin verification keyboard
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        week_accept = types.InlineKeyboardButton("Accept 1 Week", callback_data=f"accept_week_{message.from_user.id}")
        month_accept = types.InlineKeyboardButton("Accept 1 Month", callback_data=f"accept_month_{message.from_user.id}")
        reject = types.InlineKeyboardButton("Reject", callback_data=f"reject_{message.from_user.id}")
        keyboard.add(week_accept, month_accept, reject)

        # Forward screenshot to admin with verification buttons
        bot.forward_message(ADMIN_CHAT_ID, message.chat.id, message.message_id)
        admin_msg = f"Payment screenshot from:\nUser ID: {message.from_user.id}\nUsername: @{message.from_user.username}\n\nPlease verify:"
        bot.send_message(ADMIN_CHAT_ID, admin_msg, reply_markup=keyboard)
        
        # Send confirmation to user
        bot.reply_to(message, "Thank you! Your payment screenshot has been received and is being reviewed. Please wait for confirmation.")
        
    except Exception as e:
        logger.error(f"Error processing payment screenshot: {e}")
        bot.reply_to(message, "Sorry, there was an error processing your screenshot. Please try again or contact support.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('accept_week_', 'accept_month_', 'reject_')))
def handle_admin_verification(call):
    try:
        action, user_id = call.data.rsplit('_', 1)  # Split from right to handle underscores in user_id
        
        if action == 'reject':
            # Send rejection message to user
            bot.send_message(int(user_id), "❌ Your payment screenshot was rejected. Please ensure you sent the correct screenshot and try again.")
            bot.answer_callback_query(call.id, "Rejection sent to user")
            
        elif action in ['accept_week', 'accept_month']:
            duration = "1week" if action == 'accept_week' else "1month"
            expiry = datetime.now() + timedelta(weeks=1 if duration == "1week" else 4)
            
            # Add user to appropriate collection
            payment_data = {
                'user_id': str(user_id),  # Convert to string to match check_user_id format
                'expiry_date': expiry
            }
            
            if duration == "1week":
                one_week_prem.insert_one(payment_data)
            else:
                one_month_prem.insert_one(payment_data)

            # Update user's premium status in users collection
            users_collection.update_one(
                {'user_id': str(user_id)},  # Convert to string to match check_user_id format
                {
                    '$set': {
                        'is_premium': True,
                        'premium_start': datetime.now(),
                        'premium_duration': duration,
                        'expiry': expiry
                    }
                },
                upsert=True
            )

            # Send confirmation to user
            bot.send_message(
                int(user_id),
                f"✨ Your payment has been verified!\n\n▶️ Your {duration} premium subscription is now active.\n\n"
                "You can check it using /info command!\n🎉 Enjoy your premium features!"
            )
            bot.answer_callback_query(call.id, f"Premium {duration} activated for user")

        # Update admin message
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )

        # Update admin message text
        action_text = "rejected" if action == "reject" else f"accepted ({duration})"
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"{call.message.text}\n\nStatus: {action_text}"
        )

    except Exception as e:
        logger.error(f"Error in admin verification: {e}")
        bot.answer_callback_query(call.id, f"Error processing verification: {str(e)}", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data == "crypto_payment")
def handle_premium_purchase(call):
    try:
        # Create keyboard with duration options
        keyboard = types.InlineKeyboardMarkup()
        keyboard.row(
            types.InlineKeyboardButton("1 Week ($1)", callback_data="duration_1week"),
            types.InlineKeyboardButton("1 Month ($6)", callback_data="duration_1month")
        )

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="Please select your premium subscription duration:",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error creating payment: {e}")
        bot.answer_callback_query(call.id, "Error creating payment. Please try again later.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("duration_"))
def handle_duration_selection(call):
    try:
        duration = call.data.split("_")[1]
        amount = 1 if duration == "1week" else 6

        # Create payment invoice
        create_url = "https://api.cryptocloud.plus/v2/invoice/create"
        create_data = {
            "amount": amount,
            "shop_id": CRYPTOCLOUD_SHOP_ID,
            "currency": "USD"
        }

        headers = {
            "Authorization": f"Token {CRYPTOCLOUD_TOKEN}"
        }

        create_response = requests.post(create_url, headers=headers, json=create_data)

        if create_response.status_code == 200:
            invoice_data = create_response.json()
            if invoice_data["status"] == "success":
                invoice_uuid = invoice_data["result"]["uuid"]
                pay_url = invoice_data["result"]["link"]

                # Create keyboard with payment URL
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton("Pay Now", url=pay_url),
                    types.InlineKeyboardButton("Check Payment", callback_data=f"check_{invoice_uuid}")
                )

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"Please complete your payment for {duration} premium subscription.\nAmount: ${amount}",
                    reply_markup=keyboard
                )
            else:
                bot.answer_callback_query(call.id, "Failed to create payment invoice", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "Error creating payment", show_alert=True)

    except Exception as e:
        logger.error(f"Error processing duration selection: {e}")
        bot.answer_callback_query(call.id, "Error processing selection. Please try again.", show_alert=True)

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment_status(call):
    try:
        invoice_uuid = call.data.split("_")[1]
        info_url = "https://api.cryptocloud.plus/v2/invoice/merchant/info"
        headers = {
            "Authorization": f"Token {CRYPTOCLOUD_TOKEN}"
        }

        check_data = {
            "uuids": [invoice_uuid]
        }

        response = requests.post(info_url, headers=headers, json=check_data)

        if response.status_code == 200:
            data = response.json()
            if data["status"] == "success":
                for invoice in data["result"]:
                    if invoice["status"] == "overpaid":
                        bot.answer_callback_query(call.id, "Payment confirmed! Processing your premium activation...", show_alert=True)
                        
                        # Get duration from invoice amount
                        duration = "1week" if invoice["amount"] == 1 else "1month"
                        expiry = datetime.now() + timedelta(weeks=1 if duration == "1week" else 4)
                        
                        # Add user to appropriate collection
                        payment_data = {
                            'user_id': str(call.from_user.id),
                            'expiry_date': expiry
                        }
                        
                        if duration == "1week":
                            one_week_prem.insert_one(payment_data)
                        else:
                            one_month_prem.insert_one(payment_data)

                        # Update user's premium status in users collection
                        users_collection.update_one(
                            {'user_id': str(call.from_user.id)},
                            {
                                '$set': {
                                    'is_premium': True,
                                    'premium_start': datetime.now(),
                                    'premium_duration': duration,
                                    'expiry': expiry
                                }
                            },
                            upsert=True
                        )

                        # Send confirmation to user
                        bot.edit_message_text(
                            chat_id=call.message.chat.id,
                            message_id=call.message.message_id,
                            text=f"✨ Your payment has been verified!\n\n▶️ Your {duration} premium subscription is now active.\n\n"
                                "You can check it using /info command!\n🎉 Enjoy your premium features!"
                        )
                        return
                    elif invoice["status"] == "created":
                        bot.answer_callback_query(call.id, "Payment pending. Please complete the payment.", show_alert=True)
                        return
            
        bot.answer_callback_query(call.id, "Payment not found or error checking status", show_alert=True)

    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        bot.answer_callback_query(call.id, "Error checking payment status", show_alert=True)

@bot.message_handler(commands=['info'])
def user_info(message):
    try:
        # Get user info
        user = message.from_user
        dc = user.id or "Unknown"
        is_premium = check_user_id(str(user.id))
        is_premium = check_user_id(str(user.id))
        premium_status = "Premium User" if is_premium else "Free User"
    
        # Calculate remaining premium duration
        if is_premium:
            user_data = users_collection.find_one({'user_id': str(user.id)})
            if user_data:
                expiry_date = user_data.get('expiry')
                if expiry_date:
                    remaining_time = expiry_date - datetime.now()
                    if remaining_time.total_seconds() > 0:
                        days = remaining_time.days
                        hours = remaining_time.seconds // 3600
                        minutes = (remaining_time.seconds % 3600) // 60
                        premium_duration = f"{days} days, {hours} hours, {minutes} minutes"
                    else:
                        premium_duration = "Expired"
                else:
                    premium_duration = "Lifetime Premium"
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
            reply_markup=keyboard,
            parse_mode='Markdown'
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
