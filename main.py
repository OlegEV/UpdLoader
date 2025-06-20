"""
Главный файл для запуска Telegram бота загрузки УПД в МойСклад
"""
import sys
from loguru import logger

from src.config import Config
from src.telegram_bot import TelegramUPDBot


def setup_logging():
    """Настройка логирования"""
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Добавляем консольный вывод
    logger.add(
        sys.stdout,
        level=Config.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Добавляем файловый вывод
    logger.add(
        "logs/bot.log",
        level=Config.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",
        retention="30 days",
        compression="zip"
    )


def validate_config():
    """Валидация конфигурации"""
    errors = Config.validate()
    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("Создайте файл .env на основе .env.example и заполните все необходимые параметры")
        sys.exit(1)
    
    logger.info("Конфигурация валидна")


def main():
    """Главная функция"""
    try:
        # Настраиваем логирование
        setup_logging()
        
        logger.info("=" * 50)
        logger.info("Запуск Telegram бота для загрузки УПД в МойСклад")
        logger.info("=" * 50)
        
        # Валидируем конфигурацию
        validate_config()
        
        # Создаем временную директорию
        Config.ensure_temp_dir()
        logger.info(f"Временная директория: {Config.TEMP_DIR}")
        
        # Выводим информацию о конфигурации
        logger.info(f"Авторизованных пользователей: {len(Config.AUTHORIZED_USERS)}")
        logger.info(f"Максимальный размер файла: {Config.MAX_FILE_SIZE // 1024 // 1024} МБ")
        logger.info(f"МойСклад API URL: {Config.MOYSKLAD_API_URL}")
        
        # Создаем и запускаем бота
        bot = TelegramUPDBot()
        logger.info("Бот создан, начинаю работу...")
        
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")
        logger.info("Завершение работы бота...")
        
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1)
    
    finally:
        logger.info("Бот остановлен")


if __name__ == "__main__":
    main()