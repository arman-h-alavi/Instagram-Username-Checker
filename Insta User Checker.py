from telegram import Update, constants, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import instaloader
import re
from enum import Enum
import os
import logging

logging.basicConfig(filename='log', filemode='w', level=logging.DEBUG)


# Create an Instaloader instance
loader = instaloader.Instaloader()

# Instagram credentials
# Insert your personal username and password instead of 'YOUR_USERNAME' and 'YOUR_PASSWORD' respectively.
username = 'YOUR_USERNAME'
password = 'YOUR_PASSWORD'

# Get the directory where your program is located
program_dir = os.path.dirname(os.path.abspath(__file__))

# Define the session file name and path
session_file = os.path.join(program_dir, 'session_file')

# Check if the session file exists
if os.path.isfile(session_file):
    # Assign the session to Instaloader's context
    loader.load_session_from_file(username=username, filename=session_file)

else:
    try:
        # Log in with your credentials
        loader.login(username, password)
        loader.save_session_to_file(session_file)
        print("Login Successful!")
    except instaloader.exceptions.InvalidArgumentException as e:
        print(f"Invalid argument: {e}")
    except instaloader.exceptions.BadCredentialsException as e:
        print(f"Login failed: {e}")
    except Exception as e:
        print(f"failed login. error is:\n{e}")


class UserState(Enum):
    STARTED = 1


user_states = {}


# Defining Usernames to access the bot
allowed_usernames = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.username
    if user_name in allowed_usernames:
        # User is an admin, allow them to use the bot
        user_id = update.effective_user.id
        user_states[user_id] = UserState.STARTED
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="خوش آمدید! نام های کاربری مورد نظر را تایپ کنید\n یا به صورت یک فایل تکست بفرستید.")
    else:
        # User is not an admin, respond with a message
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="متاسفم! فقط ادمین ها به این ربات دسترسی دارند.")
        return


profiles = ""
usernames = []
check_sign = "✅"
cross_sign = "❌"


async def start_again(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    global profiles
    global usernames

    profiles = ""
    usernames.clear()
    user_states[user_id] = None
    await push_start(update, context)


async def push_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_button = KeyboardButton('/start')
    reply_markup = ReplyKeyboardMarkup([[start_button]], resize_keyboard=True, one_time_keyboard=True)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="برای شروع دکمه start را کلیک کنید",
                                   reply_markup=reply_markup)


async def start_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Keyboard for starting the process
    keyboard = [[
        InlineKeyboardButton("بررسی", callback_data=1),
        InlineKeyboardButton("شروع مجدد", callback_data=2)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "نامهای کاربری شما دریافت شد.\n برای شروع بررسی روی دکمه 'بررسی'\nو برای شروع مجدد دکمه 'شروع' را بزنید:",
        reply_markup=reply_markup)


def check_instagram_username_availability(username):

    global profiles

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        profiles += f"{username} : {cross_sign}\n\n"

    except instaloader.exceptions.ProfileNotExistsException:
        profiles += f"{username} : {check_sign}\n\n"


async def document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If a text file is sent, read the usernames from the file

    # Check if the user has pressed the Start button
    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id] != UserState.STARTED:
        await push_start(update, context)
        return

    global usernames

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    temp_usernames = []

    file = await update.message.document.get_file()
    if file.file_path.endswith(".txt"):
        await file.download_to_drive('usernames.txt')
        with open('usernames.txt', 'r', encoding="utf8") as f:
            doc = f.read()
            temp_usernames = re.split(r',|-|;|\s+', doc)
            temp_usernames = filter(None, temp_usernames)

        if temp_usernames:
            usernames.extend(temp_usernames)
            await start_process(update, context)

        else:
            # No usernames provided
            await update.message.reply_text("هیچ نام کاربری پیدا نشد!")

    else:
        await update.message.reply_text("فرمت فایل صحیح نمی باشد! یک فایل با فرمت txt بفرستید.")


async def check_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If usernames are directly typed in, split them by spaces

    user_id = update.effective_user.id
    if user_id not in user_states or user_states[user_id] != UserState.STARTED:
        await push_start(update, context)
        return

    global usernames

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    temp_usernames = []
    msg = update.message.text
    temp_usernames = re.split(r',|-|;|\s+', msg)
    temp_usernames = filter(None, temp_usernames)

    if temp_usernames:
        usernames.extend(temp_usernames)
        await start_process(update, context)
    else:
        # No usernames provided
        await update.message.reply_text("هیچ نام کاربری پیدا نشد!")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    global profiles
    user_id = update.effective_user.id

    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()

    num = query.data

    if num == '1':
        temp_msg = await context.bot.send_message(chat_id=update.effective_chat.id, text="در حال بررسی...")
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

        try:
            # Iterate over the usernames and check availability for each one
            for username in usernames:
                check_instagram_username_availability(username)

            await context.bot.send_message(chat_id=update.effective_chat.id, text=profiles)

        except Exception as er:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                                           text=f"فرآیند با خطای زیر مواجه شد:\n{er}")

        finally:
            await context.bot.deleteMessage(chat_id=update.effective_chat.id, message_id=temp_msg.message_id)
            await start_again(update, context, user_id)

    else:
        await start_again(update, context, user_id)


if __name__ == '__main__':
    # Insert your personal telegram token instead of 'YOUR_TOKEN' below
    application = ApplicationBuilder().token('YOUR_TOKEN').build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT, check_username))
    application.add_handler(MessageHandler(filters.ATTACHMENT, document))
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()
