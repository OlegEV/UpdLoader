"""
Базовый класс для процессоров документов
"""
import os
import tempfile
from typing import Dict, Optional

from loguru import logger

from src.config import Config
from src.models import ProcessingResult
from src.moysklad_api import MoySkladAPI, MoySkladAPIError


class BaseDocumentProcessor:
    """Базовый класс для процессоров документов"""
    
    def __init__(self):
        self.moysklad_api = MoySkladAPI()
    
    def _validate_file(self, file_content: bytes, filename: str, 
                     doc_type_name: str) -> Optional[ProcessingResult]:
        """
        Валидация файла
        
        Args:
            file_content: Содержимое файла
            filename: Имя файла
            doc_type_name: Название типа документа для сообщений
            
        Returns:
            Optional[ProcessingResult]: Результат валидации или None если валидация прошла
        """
        # Проверяем размер файла
        if len(file_content) > Config.MAX_FILE_SIZE:
            return ProcessingResult(
                success=False,
                message=f"❌ Файл слишком большой. Максимальный размер: {Config.MAX_FILE_SIZE // 1024 // 1024} МБ",
                error_code="FILE_TOO_LARGE"
            )
        
        # Проверяем расширение файла
        if not filename.lower().endswith('.zip'):
            return ProcessingResult(
                success=False,
                message=f"❌ Поддерживаются только ZIP архивы с {doc_type_name}",
                error_code="INVALID_FILE_TYPE"
            )
        
        return None
    
    def _save_temp_file(self, file_content: bytes, filename: str) -> str:
        """
        Сохранение временного файла
        
        Args:
            file_content: Содержимое файла
            filename: Имя файла
            
        Returns:
            str: Путь к временному файлу
        """
        temp_file = tempfile.NamedTemporaryFile(
            dir=Config.TEMP_DIR,
            suffix='.zip',
            delete=False
        )
        
        try:
            temp_file.write(file_content)
            temp_file.flush()
            logger.debug(f"Временный файл сохранен: {temp_file.name}")
            return temp_file.name
        finally:
            temp_file.close()
    
    def _cleanup_temp_files(self, zip_path: str):
        """
        Очистка временных файлов
        
        Args:
            zip_path: Путь к ZIP файлу
        """
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            logger.debug(f"Временный файл удален: {zip_path}")
        except Exception as e:
            logger.error(f"Ошибка удаления временного файла: {e}")
    
    def check_moysklad_connection(self) -> bool:
        """
        Проверка подключения к МойСклад
        
        Returns:
            bool: True если подключение успешно
        """
        try:
            return self.moysklad_api.verify_token()
        except Exception as e:
            logger.error(f"Ошибка проверки подключения к МойСклад: {e}")
            return False
    
    def get_moysklad_status(self) -> Dict:
        """
        Получение детального статуса МойСклад API
        
        Returns:
            Dict: Статус API
        """
        try:
            return self.moysklad_api.verify_api_access()
        except Exception as e:
            logger.error(f"Ошибка получения статуса МойСклад: {e}")
            return {
                "success": False,
                "error": f"Ошибка получения статуса: {e}",
                "details": "Проверьте настройки API"
            }
    
    def _handle_parsing_error(self, error: Exception, doc_type_name: str) -> ProcessingResult:
        """
        Обработка ошибки парсинга
        
        Args:
            error: Исключение
            doc_type_name: Название типа документа
            
        Returns:
            ProcessingResult: Результат с ошибкой
        """
        logger.error(f"Ошибка парсинга {doc_type_name}: {error}")
        return ProcessingResult(
            success=False,
            message=f"❌ Ошибка обработки {doc_type_name}:\n{str(error)}",
            error_code="PARSING_ERROR"
        )
    
    def _handle_api_error(self, error: Exception) -> ProcessingResult:
        """
        Обработка ошибки API
        
        Args:
            error: Исключение
            
        Returns:
            ProcessingResult: Результат с ошибкой
        """
        logger.error(f"Ошибка МойСклад API: {error}")
        return ProcessingResult(
            success=False,
            message=f"❌ Ошибка загрузки в МойСклад:\n{str(error)}",
            error_code="MOYSKLAD_API_ERROR"
        )
    
    def _handle_unexpected_error(self, error: Exception) -> ProcessingResult:
        """
        Обработка неожиданной ошибки
        
        Args:
            error: Исключение
            
        Returns:
            ProcessingResult: Результат с ошибкой
        """
        logger.error(f"Неожиданная ошибка: {error}")
        return ProcessingResult(
            success=False,
            message=f"❌ Неожиданная ошибка:\n{str(error)}",
            error_code="UNEXPECTED_ERROR"
        )
