"""
Конфигурация приложения
"""
import os
from typing import List
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Config:
    """Класс конфигурации приложения"""
    
    # Telegram Bot
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    AUTHORIZED_USERS = [
        int(user_id.strip()) 
        for user_id in os.getenv('AUTHORIZED_USERS', '').split(',') 
        if user_id.strip()
    ]
    
    # МойСклад API
    MOYSKLAD_API_TOKEN = os.getenv('MOYSKLAD_API_TOKEN')
    MOYSKLAD_API_URL = "https://api.moysklad.ru/api/remap/1.2"
    MOYSKLAD_ORGANIZATION_ID = os.getenv('MOYSKLAD_ORGANIZATION_ID')
    
    # Настройки приложения
    TEMP_DIR = os.getenv('TEMP_DIR', './temp')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB
    
    # Кодировка УПД файлов
    UPD_ENCODING = 'windows-1251'
    
    @classmethod
    def validate(cls) -> List[str]:
        """Валидация конфигурации"""
        errors = []
        
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN не установлен")
            
        if not cls.MOYSKLAD_API_TOKEN:
            errors.append("MOYSKLAD_API_TOKEN не установлен")
            
        if not cls.AUTHORIZED_USERS:
            errors.append("AUTHORIZED_USERS не установлены")
            
        return errors
    
    @classmethod
    def ensure_temp_dir(cls):
        """Создание временной директории если не существует"""
        os.makedirs(cls.TEMP_DIR, exist_ok=True)