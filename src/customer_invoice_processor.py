"""
Процессор счетов покупателю в формате CommerceML
"""
from typing import Optional

from loguru import logger

from src.config import Config
from src.models import ProcessingResult
from src.customer_invoice_parser import CustomerInvoiceParser, CustomerInvoiceParsingError, CustomerInvoiceDocument
from src.moysklad_api import MoySkladAPI, MoySkladAPIError
from src.processors.base_processor import BaseDocumentProcessor
from src.utils.product_utils import determine_product_group, get_warehouse_and_project_for_group


class CustomerInvoiceProcessor(BaseDocumentProcessor):
    """Основной класс для обработки счетов покупателю"""
    
    def __init__(self):
        super().__init__()
        self.parser = CustomerInvoiceParser()
    
    def process_customer_invoice_file(self, file_content: bytes, filename: str) -> ProcessingResult:
        """
        Обработка файла счета покупателю

        Args:
            file_content: Содержимое ZIP файла
            filename: Имя файла

        Returns:
            ProcessingResult: Результат обработки
        """
        return self._process_document_file(
            file_content=file_content,
            filename=filename,
            doc_type_name="счета покупателю",
            parse_func=self._parse_customer_invoice,
            upload_func=self._upload_to_moysklad,
            create_result_func=self._create_success_result
        )
    
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
        
        # Создаем заказ покупателя и счет покупателю
        return self.moysklad_api.create_customer_order_and_invoice(customer_invoice_doc)
    
    def _create_success_result(self, customer_invoice_doc: CustomerInvoiceDocument, moysklad_result: dict) -> ProcessingResult:
        """Создание результата успешной обработки"""
        customer_order = moysklad_result.get('customer_order', {})
        customer_invoice = moysklad_result.get('customer_invoice', {})
        
        order_id = customer_order.get('id')
        order_name = customer_order.get('name', 'Не указано')
        invoice_id = customer_invoice.get('id')
        invoice_name = customer_invoice.get('name', 'Не указано')
        
        # Получаем URL документов
        order_url = None
        invoice_url = None
        if order_id:
            order_url = self.moysklad_api.get_customer_order_url(order_id)
        if invoice_id:
            invoice_url = self.moysklad_api.get_customer_invoice_url(invoice_id)
        
        # Формируем детальное сообщение
        message = self._format_success_message(customer_invoice_doc, order_name, order_url, invoice_name, invoice_url)
        
        return ProcessingResult(
            success=True,
            message=message,
            moysklad_invoice_id=invoice_id,
            moysklad_invoice_url=invoice_url
        )
    
    def _format_success_message(self, customer_invoice_doc: CustomerInvoiceDocument, 
                               order_name: str, order_url: Optional[str],
                               invoice_name: str, invoice_url: Optional[str]) -> str:
        """Форматирование сообщения об успешной обработке"""
        message = "✅ Счет покупателю успешно обработан и загружен в МойСклад!\n\n"
        
        # Информация о созданных документах
        message += f"📋 Заказ покупателя: {order_name}\n"
        message += f"💰 Счет покупателю: {invoice_name}\n"
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
            product_group = determine_product_group(item.name, item.article)
            warehouse_name, project_name = get_warehouse_and_project_for_group(product_group)
            
            message += f"• {item.name}"
            if item.article:
                message += f" (арт. {item.article})"
            message += f"\n  └ Группа: {product_group} → Склад: {warehouse_name}, Проект: {project_name}\n"
        
        message += "\n"
        
        # Ссылки на документы
        message += "🔗 Ссылки в МойСклад:\n"
        if order_url:
            message += f"• Заказ покупателя: {order_url}\n"
        if invoice_url:
            message += f"• Счет покупателю: {invoice_url}\n"
        
        return message
    