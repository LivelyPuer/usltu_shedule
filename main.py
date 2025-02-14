import asyncio
import datetime
import os
from tinydb import TinyDB, Query

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from siteParesr import Parser

# Initialize the parser
parser = Parser()

# File to store user group information
USER_GROUPS_DB = 'user_groups.json'

# Initialize TinyDB
db = TinyDB(USER_GROUPS_DB)
User = Query()

# Dictionary to store user group information in memory
user_groups = {}
stack_tasks = {}
TOKEN = os.environ.get("SECRET_TG")

string_not_valid_group = 'Неверная группа. Пожалуйста, попробуйте снова\n(Вид: <название>-<цифры>).'

if not TOKEN:
    print("Error: Telegram bot token not found. Please set the SECRET_TG environment variable.")
    exit(1)


def load_user_groups():
    global user_groups
    user_groups = {int(entry['chat_id']): entry['group_name'] for entry in db.all()}


def save_user_group(chat_id, group_name):
    if db.contains(User.chat_id == chat_id):
        db.update({'group_name': group_name}, User.chat_id == chat_id)
    else:
        db.insert({'chat_id': chat_id, 'group_name': group_name})


def delete_user_group(chat_id):
    db.remove(User.chat_id == chat_id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(update.message.chat_id)
    await update.message.reply_text('Привет! Пожалуйста, введите вашу группу\n(Вид: <название>-<цифры>).')


def validate_group(group_name: str) -> bool:
    # Check if the group exists
    return parser.get_group_links(group_name) is not None


async def group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if user_groups.get(update.message.chat_id, None) is None:
        group_name = update.message.text.strip()
        if validate_group(group_name):
            user_groups[update.message.chat_id] = group_name
            save_user_group(update.message.chat_id, group_name)  # Save the updated user group
            stack_tasks[update.message.chat_id] = []
            keyboard = [['Текущая неделя', 'Следующая неделя'], ['Сменить группу']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                f'Группа {group_name} сохранена. Вы можете запросить расписание на текущую или следующую неделю.',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(string_not_valid_group)
    else:
        if update.message.text.strip() in ('Текущая неделя', 'Следующая неделя'):
            current_week = update.message.text.strip().lower() == 'текущая неделя'
            await send_schedule(update, context, current_week)
        elif update.message.text.strip() == 'Сменить группу':
            await change_group(update, context)


async def change_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Remove the user's current group and prompt for a new one
    user_groups.pop(update.message.chat_id, None)
    delete_user_group(update.message.chat_id)  # Delete the user group from the database
    await update.message.reply_text('Пожалуйста, введите новую группу\n(Вид: <название>-<цифры>).')


async def send_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE, current_week: bool) -> None:
    chat_id = update.message.chat_id
    group_name = user_groups.get(chat_id)

    keyboard = [['Текущая неделя', 'Следующая неделя'], ['Сменить группу']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    if not group_name:
        await update.message.reply_text('Пожалуйста, сначала введите вашу группу с помощью команды /start.')
        return
    if update.message.chat_id not in stack_tasks.keys():
        stack_tasks[update.message.chat_id] = []
    stack_tasks[update.message.chat_id].append(await update.message.reply_text('Расписание генерируется⏳...'))

    output_file = f"schedule_{group_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    success, titles = parser.get_schedule_image(group_name, current_week, output_file)

    if success:
        caption = f"""Расписание группы {group_name.capitalize()}
{titles[2].strip()}"""
        await update.message.reply_photo(photo=open(output_file, 'rb'), reply_markup=reply_markup, caption=caption)
    else:
        await update.message.reply_text('Не удалось получить расписание.😕')

    os.remove(output_file)

    for task in stack_tasks.get(chat_id, []):
        await context.bot.deleteMessage(message_id=task.message_id,
                                        chat_id=update.message.chat_id)
        stack_tasks[chat_id].remove(task)


async def next_weekF(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_schedule(update, context, current_week=False)


async def current_weekF(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_schedule(update, context, current_week=True)


async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Extract the group number from the command arguments
    if context.args:
        group_name = ' '.join(context.args).strip()
        if validate_group(group_name):
            user_groups[update.message.chat_id] = group_name
            save_user_group(update.message.chat_id, group_name)  # Save the updated user group
            stack_tasks[update.message.chat_id] = []
            keyboard = [['Текущая неделя', 'Следующая неделя'], ['Сменить группу']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                f'Группа {group_name} сохранена. Вы можете запросить расписание на текущую или следующую неделю.',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(string_not_valid_group)
    else:
        await change_group(update, context)


def main() -> None:
    print("Initializing Telegram bot application...")
    load_user_groups()  # Load user groups at startup
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("next_week", next_weekF))
    application.add_handler(CommandHandler("current_week", current_weekF))
    application.add_handler(CommandHandler("changegroup", set_group))  # Add the new command handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_handler))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
