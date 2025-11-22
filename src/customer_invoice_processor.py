"""
Процессор счетов покупателю в формате CommerceML
"""
import os
import tempfile
from typing import Optional, Dict

from loguru import logger

from src.config import Config
from src.models import ProcessingResult
from src.customer_invoice_parser import CustomerInvoiceParser, CustomerInvoiceParsingError, CustomerInvoiceDocument
from src.moysklad_api import MoySkladAPI, MoySkladAPIError


class CustomerInvoiceProcessor:
    """Основной класс для обработки счетов покупателю"""
    
    def __init__(self):
        self.parser = CustomerInvoiceParser()
        self.moysklad_api = MoySkladAPI()
    
    def process_customer_invoice_file(self, file_content: bytes, filename: str) -> ProcessingResult:
        """
        Обработка файла счета покупателю
        
        Args:
            file_content: Содержимое ZIP файла
            filename: Имя файла
            
        Returns:
            ProcessingResult: Результат обработки
        """
        temp_zip_path = None
        
        try:
            logger.info(f"Начинаю обработку счета покупателю: {filename}")
            
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
                    message="❌ Поддерживаются только ZIP архивы со счетами покупателю",
                    error_code="INVALID_FILE_TYPE"
                )
            
            # Создаем временный файл
            Config.ensure_temp_dir()
            temp_zip_path = self._save_temp_file(file_content, filename)
            
            # Парсим счет покупателю
            customer_invoice_doc = self._parse_customer_invoice(temp_zip_path)
            
            # Загружаем в МойСклад
            moysklad_result = self._upload_to_moysklad(customer_invoice_doc)
            
            # Формируем успешный результат
            return self._create_success_result(customer_invoice_doc, moysklad_result)
            
        except CustomerInvoiceParsingError as e:
            logger.error(f"Ошибка парсинга счета покупателю: {e}")
            return ProcessingResult(
                success=False,
                message=f"❌ Ошибка обработки счета покупателю:\n{str(e)}",
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
            logger.error(f"Неожиданная ошибка обработки счета покупателю: {e}")
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
    
    def _parse_customer_invoice(self, zip_path: str) -> CustomerInvoiceDocument:
        """Парсинг счета покупателю"""
        logger.info("Парсинг счета покупателю...")
        return self.parser.parse_customer_invoice_archive(zip_path)
    
    def _upload_to_moysklad(self, customer_invoice_doc: CustomerInvoiceDocument) -> dict:
        """Загрузка в МойСклад"""
        logger.info("Создание заказа покупателя и счета в МойСклад...")
        
        # Проверяем токен
        if not self.moysklad_api.verify_token():
            raise MoySkladAPIError("Неверный токен МойСклад API")
        
        # Создаем заказ покупателя
        return self.moysklad_api.create_customer_order_and_invoice(customer_invoice_doc)
    
    def _create_success_result(self, customer_invoice_doc: CustomerInvoiceDocument, moysklad_result: dict) -> ProcessingResult:
        """Создание результата успешной обработки"""
        customer_order = moysklad_result.get('customer_order', {})
        
        order_id = customer_order.get('id')
        order_name = customer_order.get('name', 'Не указано')
        
        # Получаем URL документов
        order_url = None
        invoice_url = None
        if order_id:
            order_url = self.moysklad_api.get_customer_order_url(order_id)
        
        # Формируем детальное сообщение
        message = self._format_success_message(customer_invoice_doc, order_name, order_url)
        
        return ProcessingResult(
            success=True,
            message=message
        )
    
    def _format_success_message(self, customer_invoice_doc: CustomerInvoiceDocument, 
                               order_name: str, order_url: Optional[str]) -> str:
        """Форматирование сообщения об успешной обработке"""
        message = "✅ Счет покупателю успешно обработан и загружен в МойСклад!\n\n"
        
        # Информация о созданных документах
        message += f"📋 Заказ покупателя: {order_name}\n"
        message += f"📅 Дата: {customer_invoice_doc.invoice_date.strftime('%d.%m.%Y')}\n\n"
        
        # Информация об участниках
        message += f"🏢 Продавец: {customer_invoice_doc.seller.name}"
        if customer_invoice_doc.seller.inn:
            message += f" (ИНН: {customer_invoice_doc.seller.inn})"
        message += "\n"
        
        message += f"🏪 Покупатель: {customer_invoice_doc.buyer.name}"
        if customer_invoice_doc.buyer.inn:
            message += f" (ИНН: {customer_invoice_doc.buyer.inn})"
        message += "\n\n"
        
        # Финансовая информация
        message += f"💵 Общая сумма: {customer_invoice_doc.total_sum:,.2f} ₽\n"
        message += f"📦 Товарных позиций: {len(customer_invoice_doc.items)}\n\n"
        
        # Информация о товарах и их распределении
        message += "🎯 Распределение товаров:\n"
        for item in customer_invoice_doc.items:
            # Определяем группу товара
            product_group = self._determine_product_group(item.name, item.article)
            warehouse_name, project_name = self._get_warehouse_and_project_for_group(product_group)
            
            message += f"• {item.name}"
            if item.article:
                message += f" (арт. {item.article})"
            message += f"\n  └ Группа: {product_group} → Склад: {warehouse_name}, Проект: {project_name}\n"
        
        message += "\n"
        
        # Ссылки на документы
        message += "🔗 Ссылки в МойСклад:\n"
        if order_url:
            message += f"• Заказ покупателя: {order_url}\n"
        
        return message
    
    def _determine_product_group(self, product_name: str, product_article: Optional[str]) -> str:
        """Определение группы товара по названию и артикулу"""
        # Приводим к нижнему регистру для поиска
        name_lower = product_name.lower() if product_name else ""
        article_lower = product_article.lower() if product_article else ""
        
        # Ключевые слова для определения группы "трубы"
        tube_keywords = ["труба", "трубы", "трубка", "трубный", "трубопровод"]
        
        # Ключевые слова для определения группы "профиль"
        profile_keywords = ["профиль", "профили", "профильный", "профилированный"]
        
        # Проверяем название товара
        for keyword in tube_keywords:
            if keyword in name_lower:
                return "трубы"
        
        for keyword in profile_keywords:
            if keyword in name_lower:
                return "профиль"
        
        # Проверяем артикул
        for keyword in tube_keywords:
            if keyword in article_lower:
                return "трубы"
        
        for keyword in profile_keywords:
            if keyword in article_lower:
                return "профиль"
        
        # По умолчанию возвращаем "профиль"
        return "профиль"
    
    def _get_warehouse_and_project_for_group(self, product_group: str) -> tuple[str, str]:
        """Получение склада и проекта для группы товара"""
        if product_group == "трубы":
            return "Сестрорецк, ПП", "Трубы"
        elif product_group == "профиль":
            return "Гатчина", "профили"  # Используем точное название из справочника
        else:
            # По умолчанию
            return "Гатчина", "профили"  # Используем точное название из справочника
    
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