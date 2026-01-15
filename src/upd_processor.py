"""
Основной процессор УПД документов
"""
from typing import Optional, Dict

from loguru import logger

from .config import Config
from .models import ProcessingResult, UPDDocument
from .upd_parser import UPDParser, UPDParsingError
from .moysklad_api import MoySkladAPI, MoySkladAPIError
from .processors.base_processor import BaseDocumentProcessor


class UPDProcessor(BaseDocumentProcessor):
    """Основной класс для обработки УПД документов"""
    
    def __init__(self):
        super().__init__()
        self.parser = UPDParser()
    
    def process_upd_file(self, file_content: bytes, filename: str) -> ProcessingResult:
        """
        Обработка УПД файла

        Args:
            file_content: Содержимое ZIP файла
            filename: Имя файла

        Returns:
            ProcessingResult: Результат обработки
        """
        return self._process_document_file(
            file_content=file_content,
            filename=filename,
            doc_type_name="УПД",
            parse_func=self._parse_upd,
            upload_func=self._upload_to_moysklad,
            create_result_func=self._create_success_result
        )
    
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
        factureout = invoice_result.get('factureout', {})
        demand = invoice_result.get('demand', {})
        
        invoice_id = factureout.get('id')
        invoice_name = factureout.get('name', 'Не указано')
        demand_id = demand.get('id')
        demand_name = demand.get('name', 'Не указано')
        
        # Получаем URL документов
        invoice_url = None
        demand_url = None
        if invoice_id:
            invoice_url = self.moysklad_api.get_invoice_url(invoice_id)
        if demand_id:
            demand_url = self.moysklad_api.get_demand_url(demand_id)
        
        # Формируем детальное сообщение
        message = self._format_success_message(upd_document, invoice_name, invoice_url, demand_name, demand_url, invoice_result)
        
        return ProcessingResult(
            success=True,
            message=message,
            upd_document=upd_document,
            moysklad_invoice_id=invoice_id,
            moysklad_invoice_url=invoice_url
        )
    
    def _format_success_message(self, upd_document: UPDDocument, invoice_name: str,
                               invoice_url: Optional[str], demand_name: str,
                               demand_url: Optional[str], invoice_result: dict) -> str:
        """Форматирование сообщения об успешной обработке"""
        content = upd_document.content
        
        message = "✅ УПД успешно обработан и загружен в МойСклад!\n\n"
        
        # Информация о созданных документах
        message += f"📄 Счет-фактура: {invoice_name}\n"
        message += f"📦 Отгрузка: {demand_name}\n"
        message += f" Дата: {content.invoice_date.strftime('%d.%m.%Y')}\n\n"
        
        # Информация об участниках
        message += f"🏢 Поставщик: {content.seller.name}"
        if content.seller.inn:
            message += f" (ИНН: {content.seller.inn})"
        message += "\n"
        
        message += f"🏪 Покупатель: {content.buyer.name}"
        if content.buyer.inn:
            message += f" (ИНН: {content.buyer.inn})"
        message += "\n\n"
        
        # Финансовая информация
        if content.total_with_vat > 0:
            message += f"💰 Сумма без НДС: {content.total_without_vat:,.2f} ₽\n"
            message += f"🧾 НДС: {content.total_vat:,.2f} ₽\n"
            message += f"💵 Итого с НДС: {content.total_with_vat:,.2f} ₽\n\n"
        
        # Ссылки на документы
        message += "🔗 Ссылки в МойСклад:\n"
        if invoice_url:
            message += f"• Счет-фактура: {invoice_url}\n"
        if demand_url:
            message += f"• Отгрузка: {demand_url}\n"
        
        if upd_document.meta_info.doc_flow_id:
            message += f"\n🆔 ID документооборота: {upd_document.meta_info.doc_flow_id}"
        
        return message
    