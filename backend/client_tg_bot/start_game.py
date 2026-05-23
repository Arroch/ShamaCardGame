"""Точка входа TG-бота «Шама». Запуск: python -m client_tg_bot.start_game из backend/.

Переменные окружения:
  TELEGRAM_BOT_TOKEN  — токен бота (обязательно)
  PROXY_URL           — SOCKS5-прокси (опционально)
                        Форматы:
                          socks5://host:port
                          socks5://user:pass@host:port
"""

import os
import sys
import logging
import asyncio

# Гарантируем, что backend/ в sys.path при прямом запуске скрипта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Bot
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from telegram.request import HTTPXRequest
from telegram.error import TelegramError
from dotenv import load_dotenv

from bin.storage_factory import StorageFactory
import client_tg_bot.state as S
from client_tg_bot.handlers import (
    start_command, create_game_command, start_game_command,
    help_command, ping_command, info_command, rules_command,
    status_command, stats_command, fill_bots_command, leave_game_command,
    text_handler, error_handler, callback_handler,
)

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('telegram').setLevel(logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


def _build_application() -> Application:
    """Создаёт Application, при наличии PROXY_URL подключает SOCKS5."""
    proxy_url = os.environ.get("PROXY_URL", "").strip()

    # Увеличиваем пул соединений: бот отправляет много сообщений одновременно
    # (auto_play_bots + polling), дефолтный пул (1-5 соединений) не справляется.
    pool_kwargs = dict(
        connection_pool_size=16,
        pool_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        connect_timeout=30.0,
    )

    builder = Application.builder().token(BOT_TOKEN)

    if proxy_url:
        if not proxy_url.startswith("socks5://"):
            raise ValueError(f"PROXY_URL должен начинаться с socks5://, получено: {proxy_url!r}")
        safe = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logger.info(f"SOCKS5-прокси: {safe}")
        request = HTTPXRequest(proxy=proxy_url, **pool_kwargs)
    else:
        request = HTTPXRequest(**pool_kwargs)

    builder = builder.request(request).get_updates_request(request)
    return builder.build()


async def init_storage() -> bool:
    """Инициализирует хранилище данных."""
    try:
        storage_type = os.environ.get("STORAGE_TYPE", "file")
        S.storage = await StorageFactory.create_storage(storage_type)
        logger.info(f"Хранилище ({storage_type}) инициализировано")
        return True
    except Exception as e:
        logger.error(f"Ошибка инициализации хранилища: {e}")
        return False


async def cleanup_bot() -> bool:
    """Сбрасывает предыдущую сессию бота (вебхук, очередь обновлений)."""
    try:
        bot = Bot(BOT_TOKEN)
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            await bot.delete_webhook()
            logger.info("Webhook удалён")
        updates = await bot.get_updates(timeout=1, offset=-1)
        if updates:
            await bot.get_updates(offset=updates[-1].update_id + 1)
            logger.info(f"Сброшено {len(updates)} обновлений")
        return True
    except TelegramError as e:
        logger.error(f"Telegram API при очистке: {e}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при очистке: {e}")
        return False


async def run_bot() -> None:
    """Основная функция запуска бота."""
    if not await init_storage():
        logger.error("Хранилище не инициализировано — бот не запущен.")
        return

    application = _build_application()
    S._bot = application.bot

    application.add_handler(CommandHandler("start",        start_command))
    application.add_handler(CommandHandler("help",         help_command))
    application.add_handler(CommandHandler("ping",         ping_command))
    application.add_handler(CommandHandler("info",         info_command))
    application.add_handler(CommandHandler("rules",        rules_command))
    application.add_handler(CommandHandler("create_game",  create_game_command))
    application.add_handler(CommandHandler("start_game",   start_game_command))
    application.add_handler(CommandHandler("status",       status_command))
    application.add_handler(CommandHandler("stats",        stats_command))
    application.add_handler(CommandHandler("fill_bots",   fill_bots_command))
    application.add_handler(CommandHandler("leave_game",  leave_game_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_error_handler(error_handler)

    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
        poll_interval=1.0,
    )
    logger.info("Бот запущен. Ctrl+C для остановки.")

    stop_signal = asyncio.Future()

    def _signal_handler():
        if not stop_signal.done():
            stop_signal.set_result(None)

    try:
        asyncio.get_event_loop().add_signal_handler(2, _signal_handler)  # SIGINT
    except NotImplementedError:
        pass

    try:
        await stop_signal
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Остановка бота...")
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except Exception as e:
            logger.error(f"Ошибка при остановке: {e}")


def main() -> int:
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не задан.")
        return 1

    logger.info(f"Токен: {BOT_TOKEN[:5]}...{BOT_TOKEN[-5:]}")
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(cleanup_bot())
        loop.run_until_complete(run_bot())
        return 0
    except KeyboardInterrupt:
        logger.info("Остановлен пользователем.")
        return 0
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        return 1
    finally:
        logger.info("Программа завершена.")


if __name__ == "__main__":
    sys.exit(main())
