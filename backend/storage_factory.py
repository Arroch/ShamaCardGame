"""
Фабрика для создания хранилища данных.

Позволяет выбрать между PostgreSQL и файловым хранилищем
в зависимости от настроек.

Автор: ShamaVibe Team
"""

import os
import logging
from typing import Optional, Dict, Any

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class StorageFactory:
    """Фабрика для создания хранилища данных."""
    
    @staticmethod
    async def create_storage(storage_type: Optional[str] = None) -> Any:
        """
        Создает и возвращает хранилище данных указанного типа.
        
        :param storage_type: Тип хранилища ('postgres' или 'file')
                            Если не указан, пытается определить из переменной
                            окружения STORAGE_TYPE
        :return: Объект для работы с хранилищем
        """
        # Определяем тип хранилища
        if not storage_type:
            storage_type = os.environ.get("STORAGE_TYPE", "file").lower()
        
        if storage_type == "postgres":
            try:
                # Импортируем DatabaseManager только если нужен PostgreSQL
                from database_manager import DatabaseManager
                
                # Получаем параметры подключения из переменных окружения
                db_params = {
                    'host': os.environ.get('DB_HOST', 'localhost'),
                    'port': os.environ.get('DB_PORT', '5432'),
                    'database': os.environ.get('DB_NAME', 'shama_game'),
                    'user': os.environ.get('DB_USER', 'postgres'),
                    'password': os.environ.get('DB_PASSWORD', '')
                }
                
                # Создаем менеджер базы данных
                db_manager = DatabaseManager(db_params)
                
                # Инициализируем базу данных
                await db_manager.init_database()
                
                logger.info("Используется хранилище PostgreSQL")
                return db_manager
                
            except ImportError:
                logger.warning("Не удалось импортировать PostgreSQL, используется файловое хранилище")
                storage_type = "file"
            except Exception as e:
                logger.error(f"Ошибка при создании хранилища PostgreSQL: {e}")
                logger.info("Используется файловое хранилище в качестве запасного варианта")
                storage_type = "file"
        
        if storage_type == "file":
            try:
                # Импортируем FileStorage
                from file_storage import FileStorage
                
                # Получаем путь к хранилищу из переменных окружения
                storage_dir = os.environ.get('STORAGE_DIR')
                
                # Создаем файловое хранилище
                file_storage = FileStorage(storage_dir)
                
                # Инициализируем хранилище
                await file_storage.init_database()
                
                logger.info("Используется файловое хранилище")
                return file_storage
                
            except Exception as e:
                logger.error(f"Ошибка при создании файлового хранилища: {e}")
                raise
        
        # Если указан неизвестный тип хранилища
        raise ValueError(f"Неизвестный тип хранилища: {storage_type}")

    @staticmethod
    def get_storage_types() -> Dict[str, str]:
        """
        Возвращает словарь доступных типов хранилищ.
        
        :return: Словарь {код: описание}
        """
        return {
            "postgres": "PostgreSQL - производительная база данных (требует установки сервера)",
            "file": "Файловое хранилище CSV - простой вариант без дополнительных зависимостей"
        }
