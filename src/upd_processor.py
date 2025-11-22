"""
Основной процессор УПД документов
"""
import os
import tempfile
from typing import Optional, Dict

from loguru import logger

from .config import Config
from .models import ProcessingResult, UPDDocument
from .upd_parser import UPDParser, UPDParsingError
from .moysklad_api import MoySkladAPI, MoySkladAPIError


class UPDProcessor:
    """Основной класс для обработки УПД документов"""
    
    def __init__(self):
        self.parser = UPDParser()
        self.moysklad_api = MoySkladAPI()
    
    def process_upd_file(self, file_content: bytes, filename: str) -> ProcessingResult:
        """
        Обработка УПД файла
        
        Args:
            file_content: Содержимое ZIP файла
            filename: Имя файла
            
        Returns:
            ProcessingResult: Результат обработки
        """
        temp_zip_path = None
        
        try:
            logger.info(f"Начинаю обработку УПД файла: {filename}")
            
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
                    message="❌ Поддерживаются только ZIP архивы с УПД",
                    error_code="INVALID_FILE_TYPE"
                )
            
            # Создаем временный файл
            Config.ensure_temp_dir()
            temp_zip_path = self._save_temp_file(file_content, filename)
            
            # Парсим УПД
            upd_document = self._parse_upd(temp_zip_path)
            
            # Загружаем в МойСклад
            invoice_result = self._upload_to_moysklad(upd_document)
            
            # Формируем успешный результат
            return self._create_success_result(upd_document, invoice_result)
            
        except UPDParsingError as e:
            logger.error(f"Ошибка парсинга УПД: {e}")
            return ProcessingResult(
                success=False,
                message=f"❌ Ошибка обработки УПД:\n{str(e)}",
                error_code="PARSING_ERROR"
            )
            
        except MoySkladAPIError as e:
            logger.error(f"Ошибка МойСклад API: {e}")
            return ProcessingResult(
                success=False,
                message=f"❌ Ошибка загрузки в МойСклад:\n{str(e)}",
                error_code="MOYSKLAD_API_ERROR"
            )
            
        except Exception as e:
            logger.error(f"Неожиданная ошибка обработки УПД: {e}")
            return ProcessingResult(
                success=False,
                message=f"❌ Неожиданная ошибка:\n{str(e)}",
                error_code="UNEXPECTED_ERROR"
            )
            
        finally:
            # Очищаем временные файлы
            if temp_zip_path:
                self._cleanup_temp_files(temp_zip_path)
    
    def _save_temp_file(self, file_content: bytes, filename: str) -> str:
        """Сохранение временного файла"""
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
    
    def _parse_upd(self, zip_path: str) -> UPDDocument:
        """Парсинг УПД документа"""
        logger.info("Парсинг УПД документа...")
        return self.parser.parse_upd_archive(zip_path)
    
    def _upload_to_moysklad(self, upd_document: UPDDocument) -> dict:
        """Загрузка в МойСклад"""
        logger.info("Загрузка в МойСклад...")
        
        # Проверяем токен
        if not self.moysklad_api.verify_token():
            raise MoySkladAPIError("Неверный токен МойСклад API")
        
        # Создаем счет-фактуру
        return self.moysklad_api.create_invoice_from_upd(upd_document)
    
    def _create_success_result(self, upd_document: UPDDocument, invoice_result: dict) -> ProcessingResult:
        """Создание результата успешной обработки"""
        # Новая структура ответа содержит factureout и demand
        demand = invoice_result.get('demand', {})
        
        demand_id = demand.get('id')
        demand_name = demand.get('name', 'Не указано')
        
        # Получаем URL документов
        invoice_url = None
        demand_url = None
        if demand_id:
            demand_url = self.moysklad_api.get_demand_url(demand_id)
        
        # Формируем детальное сообщение
        message = self._format_success_message(upd_document, demand_name, demand_url, invoice_result)
        
        return ProcessingResult(
            success=True,
            message=message,
            upd_document=upd_document
        )
    
    def _format_success_message(self, upd_document: UPDDocument, demand_name: str,
                               demand_url: Optional[str], invoice_result: dict) -> str:
        """Форматирование сообщения об успешной обработке"""
        content = upd_document.content
        
        message = "✅ УПД успешно обработан и загружен в МойСклад!\n\n"

        # Информация об участниках
        message += f"🏢 Поставщик: {content.seller.name}"
        if content.seller.inn:
            message += f" (ИНН: {content.seller.inn})"
        message += "\n"
        
        message += f"🏪 Покупатель: {content.buyer.name}"
        if content.buyer.inn:
            message += f" (ИНН: {content.buyer.inn})"
        message += "\n\n"

        # Информация о созданных документах
        message += f" Дата: {content.invoice_date.strftime('%d.%m.%Y')}\n\n"
        message += f"📦 Отгрузка: {demand_name}\n"
        
        # Ссылки на документы
        message += "🔗 Ссылки в МойСклад:\n"
        if demand_url:
            message += f"• Отгрузка: {demand_url}\n"
        
        return message
    
    def _cleanup_temp_files(self, zip_path: str):
        """Очистка временных файлов"""
        try:
            self.parser.cleanup_temp_files(zip_path)
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов: {e}")
    
    def check_moysklad_connection(self) -> bool:
        """Проверка подключения к МойСклад"""
        try:
            return self.moysklad_api.verify_token()
        except Exception as e:
            logger.error(f"Ошибка проверки подключения к МойСклад: {e}")
            return False
    
    def get_moysklad_status(self) -> Dict:
        """Получение детального статуса МойСклад API"""
        try:
            return self.moysklad_api.verify_api_access()
        except Exception as e:
            logger.error(f"Ошибка получения статуса МойСклад: {e}")
            return {
                "success": False,
                "error": f"Ошибка получения статуса: {e}",
                "details": "Проверьте настройки API"
            }