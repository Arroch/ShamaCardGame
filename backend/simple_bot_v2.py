"""
Улучшенная упрощенная версия Telegram бота для игры Шама.
Используется для тестирования базовой функциональности.

Автор: ShamaVibe Team
"""

import os
import logging
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, TelegramError
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Уменьшаем уровень логирования для некоторых модулей
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('httpcore').setLevel(logging.INFO)

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
        "/ping - Проверить работу бота\n"
        "/info - Показать информацию о боте"
    )
    
    await update.message.reply_text(help_text)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /ping для проверки работы бота."""
    logger.info(f"Получена команда /ping от пользователя {update.effective_user.id}")
    
    await update.message.reply_text("Понг! Бот работает.")

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /info для вывода информации о боте и среде."""
    logger.info(f"Получена команда /info от пользователя {update.effective_user.id}")
    
    bot = context.bot
    bot_info = await bot.get_me()
    
    info_text = (
        f"🤖 Информация о боте:\n"
        f"ID: {bot_info.id}\n"
        f"Имя: {bot_info.first_name}\n"
        f"Имя пользователя: @{bot_info.username}\n\n"
        f"🔄 Версия бота: Simple Bot V2\n"
        f"💾 Тип хранилища: {os.environ.get('STORAGE_TYPE', 'file')}\n\n"
        f"👤 Информация о пользователе:\n"
        f"ID: {update.effective_user.id}\n"
        f"Имя: {update.effective_user.first_name}\n"
        f"Имя пользователя: @{update.effective_user.username or 'отсутствует'}"
    )
    
    await update.message.reply_text(info_text)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений."""
    logger.info(f"Получено текстовое сообщение от пользователя {update.effective_user.id}: {update.message.text[:30]}...")
    
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
    
    # Если это конфликт при получении обновлений, сообщаем о нем, но не отправляем пользователю
    if isinstance(context.error, Conflict):
        logger.warning("Обнаружен конфликт при получении обновлений. Возможно запущен другой экземпляр бота.")
        return
    
    # Уведомляем пользователя об ошибке, если возможно
    if update and update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при обработке вашего запроса."
        )

async def reset_webhook():
    """Сброс и удаление webhook."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    bot = Bot(token=token)
    
    # Получаем информацию о webhook
    webhook_info = await bot.get_webhook_info()
    logger.info(f"Webhook: {webhook_info.url or 'не установлен'}")
    
    # Удаляем webhook если он установлен
    if webhook_info.url:
        await bot.delete_webhook()
        logger.info("Webhook удален")
    
    # Получаем последние обновления без их обработки
    updates = await bot.get_updates(timeout=1, limit=1, offset=-1)
    update_count = len(updates)
    logger.info(f"Получено {update_count} обновлений")
    
    if update_count > 0:
        offset = updates[-1].update_id + 1
        logger.info(f"Последний update_id: {updates[-1].update_id}, новый offset: {offset}")
        # Отмечаем все обновления как прочитанные
        await bot.get_updates(offset=offset)
    else:
        logger.info("Нет непрочитанных обновлений")
    
    return update_count

async def setup_and_run(token: str, update_count: int):
    """Асинхронная настройка и запуск бота."""
    # Создаем цикл событий если его нет
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    # Регистрируем обработчик ошибок
    application.add_error_handler(error_handler)
    
    logger.info("Запуск бота...")
    
    # Запускаем бота с более безопасными настройками
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
        poll_interval=1.0,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
    )
    
    logger.info("Бот запущен и ожидает сообщений")
    
    # Держим бота запущенным до Ctrl+C
    try:
        # Создаем Future для ожидания завершения
        stop_signal = asyncio.Future()
        await stop_signal
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Получен сигнал остановки")
    finally:
        # Останавливаем бота
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

def main() -> None:
    """Основная функция для запуска бота."""
    try:
        # Получаем токен бота из переменных окружения
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not token:
            logger.error("Не указан токен бота! Установите переменную окружения TELEGRAM_BOT_TOKEN")
            return
        
        logger.info(f"Использую токен: {token[:5]}...{token[-5:]}")
        
        # Сначала сбрасываем webhook и проверяем обновления
        update_count = asyncio.run(reset_webhook())
        logger.info(f"Сброс webhook завершен, найдено {update_count} обновлений")
        
        # Запускаем бота через асинхронную функцию
        asyncio.run(setup_and_run(token, update_count))
        
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
    finally:
        logger.info("Бот завершил работу")

if __name__ == "__main__":
    main()
