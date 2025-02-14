import asyncio
import datetime
import os

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from siteParesr import Parser

# Initialize the parser
parser = Parser()

# Dictionary to store user group information
user_groups = {}
stack_tasks = {}
TOKEN = os.environ.get("SECRET_TG")

if not TOKEN:
    print("Error: Telegram bot token not found. Please set the SECRET_TG environment variable.")
    exit(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Привет! Пожалуйста, введите вашу группу.')


def validate_group(group_name: str) -> bool:
    # Check if the group exists
    return parser.get_group_links(group_name) is not None


async def group_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if user_groups.get(update.message.chat_id, None) is None:
        group_name = update.message.text.strip()
        if validate_group(group_name):
            user_groups[update.message.chat_id] = group_name
            stack_tasks[update.message.chat_id] = []
            keyboard = [['Текущая неделя', 'Следующая неделя']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(
                f'Группа {group_name} сохранена. Вы можете запросить расписание на текущую или следующую неделю.',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text('Неверная группа. Пожалуйста, попробуйте снова.')
    else:
        if update.message.text.strip() in ('Текущая неделя', 'Следующая неделя'):
            keyboard = [['Текущая неделя', 'Следующая неделя']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

            stack_tasks[update.message.chat_id].append(await update.message.reply_text('Расписание генерируется...'))
            chat_id = update.message.chat_id
            group_name = user_groups[chat_id]

            current_week = update.message.text.strip().lower() == 'текущая неделя'

            output_file = f"schedule_{group_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

            success = parser.get_schedule_image(group_name, current_week, output_file)
            if success:
                await update.message.reply_photo(photo=open(output_file, 'rb'), reply_markup=reply_markup)
            else:
                await update.message.reply_text('Не удалось получить расписание.')
            try:
                for task in stack_tasks.get(chat_id, []):
                    await context.bot.deleteMessage(message_id=task.message_id,
                                                    chat_id=update.message.chat_id)
                    stack_tasks[chat_id].remove(task)
            except:
                pass
            os.remove(output_file)


def main() -> None:
    print("Initializing Telegram bot application...")
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, group_handler))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
