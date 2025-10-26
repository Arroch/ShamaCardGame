"""
Упрощенная версия Telegram бота для игры Шама.
Используется для тестирования базовой функциональности.

Автор: ShamaVibe Team
"""

import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    logger.info(f"Получена команда /start от пользователя {update.effective_user.id}")
    user_name = update.effective_user.first_name
    
    await update.message.reply_text(
        f"Привет, {user_name}! Добро пожаловать в тестовый режим игры «Шама».\n\n"
        f"Используйте /help для получения списка команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    logger.info(f"Получена команда /help от пользователя {update.effective_user.id}")
    
    help_text = (
        "Доступные команды:\n"
        "/start - Начать использование бота\n"
        "/help - Показать это сообщение\n"
        "/ping - Проверить работу бота"
    )
    
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /ping для проверки работы бота."""
    logger.info(f"Получена команда /ping от пользователя {update.effective_user.id}")
    
    await update.message.reply_text("Понг! Бот работает.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений."""
    logger.info(f"Получено текстовое сообщение от пользователя {update.effective_user.id}")
    
    await update.message.reply_text(
        "Я понимаю только команды, начинающиеся с /\n"
        "Отправьте /help чтобы увидеть список доступных команд."
    )

async def error_handler(update, context) -> None:
    """Обработчик ошибок."""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")
    
    # Подробное логирование
    import traceback
    traceback_str = ''.join(traceback.format_tb(context.error.__traceback__))
    logger.error(f"Трассировка ошибки:\n{traceback_str}")
    
    # Уведомляем пользователя об ошибке, если возможно
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке вашего запроса."
        )

def main() -> None:
    """Основная функция для запуска бота."""
    try:
        # Получаем токен бота из переменных окружения
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not token:
            logger.error("Не указан токен бота! Установите переменную окружения TELEGRAM_BOT_TOKEN")
            return
        
        logger.info(f"Использую токен: {token[:5]}...{token[-5:]}")
        
        # Создаем приложение
        application = Application.builder().token(token).build()
        
        # Регистрируем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("ping", ping_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(error_handler)
        
        logger.info("Запуск бота...")
        
        # Запускаем бота
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
            poll_interval=1.0
        )
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)

if __name__ == "__main__":
    main()
