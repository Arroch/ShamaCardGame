"""
Скрипт для проверки информации о боте.
Выводит основную информацию без запуска длительной сессии.

Автор: ShamaVibe Team
"""

import os
import asyncio
import logging
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def check_bot():
    try:
        # Получаем токен бота из переменных окружения
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        
        if not token:
            logger.error("Не указан токен бота! Установите переменную окружения TELEGRAM_BOT_TOKEN")
            return
        
        logger.info(f"Проверка бота с токеном: {token[:5]}...{token[-5:]}")
        
        # Создаем экземпляр бота
        bot = Bot(token=token)
        
        # Получаем информацию о боте
        bot_info = await bot.get_me()
        logger.info(f"Информация о боте: ID={bot_info.id}, Имя={bot_info.first_name}, Username=@{bot_info.username}")
        
        # Пробуем получить webhook
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook: {webhook_info.url or 'не установлен'}")
        
        # Удаляем webhook для освобождения бота
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
            
        logger.info("Проверка завершена успешно!")
            
    except TelegramError as e:
        logger.error(f"Ошибка Telegram API: {e}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(check_bot())
