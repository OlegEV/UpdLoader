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
from src.upd_parser import UPDParsingError
from src.customer_invoice_parser import CustomerInvoiceParsingError


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
        logger.error(f"Ошибка парсинга {doc_type_name}: {error}", exc_info=True)
        return ProcessingResult(
            success=False,
            message=f"❌ Ошибка обработки {doc_type_name}:\n{str(error)}\n\n💡 Рекомендации:\n• Проверьте структуру файла\n• Убедитесь, что файл соответствует формату {doc_type_name}\n• Обратитесь к администратору если проблема повторяется",
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
        logger.error(f"Ошибка МойСклад API: {error}", exc_info=True)
        return ProcessingResult(
            success=False,
            message=f"❌ Ошибка загрузки в МойСклад:\n{str(error)}\n\n💡 Рекомендации:\n• Проверьте настройки API МойСклад\n• Убедитесь, что у токена есть необходимые права\n• Проверьте подключение к интернету\n• Обратитесь к администратору если проблема повторяется",
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
        logger.error(f"Неожиданная ошибка: {error}", exc_info=True)
        return ProcessingResult(
            success=False,
            message=f"❌ Неожиданная ошибка:\n{str(error)}\n\n💡 Рекомендации:\n• Повторите попытку позже\n• Обратитесь к администратору для диагностики проблемы\n• Проверьте логи приложения для дополнительной информации",
            error_code="UNEXPECTED_ERROR"
        )

    def _process_document_file(self, file_content: bytes, filename: str, doc_type_name: str,
                              parse_func, upload_func, create_result_func) -> ProcessingResult:
        """
        Общий метод обработки документа

        Args:
            file_content: Содержимое файла
            filename: Имя файла
            doc_type_name: Название типа документа
            parse_func: Функция для парсинга документа
            upload_func: Функция для загрузки в МойСклад
            create_result_func: Функция для создания результата

        Returns:
            ProcessingResult: Результат обработки
        """
        temp_zip_path = None

        try:
            logger.info(f"Начинаю обработку {doc_type_name.lower()} файла: {filename}")

            # Проверяем размер файла и расширение
            validation_result = self._validate_file(file_content, filename, doc_type_name)
            if validation_result:
                return validation_result

            # Создаем временный файл
            Config.ensure_temp_dir()
            temp_zip_path = self._save_temp_file(file_content, filename)

            # Парсим документ
            document = parse_func(temp_zip_path)

            # Загружаем в МойСклад
            upload_result = upload_func(document)

            # Формируем успешный результат
            return create_result_func(document, upload_result)

        except UPDParsingError as e:
            return self._handle_parsing_error(e, doc_type_name)

        except MoySkladAPIError as e:
            return self._handle_api_error(e)

        except Exception as e:
            return self._handle_unexpected_error(e)

        finally:
            # Очищаем временные файлы
            if temp_zip_path:
                self._cleanup_temp_files(temp_zip_path)
