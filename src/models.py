"""
Модели данных для УПД документов
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Optional


@dataclass
class Address:
    """Адрес организации"""
    postal_code: Optional[str] = None
    region_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    house: Optional[str] = None
    apartment: Optional[str] = None


@dataclass
class MetaInfo:
    """Метаданные из meta.xml"""
    doc_flow_id: str
    main_document_path: str
    card_path: str


@dataclass
class CardInfo:
    """Информация из card.xml"""
    external_identifier: str
    title: str
    date: datetime
    sender_inn: Optional[str] = None
    sender_kpp: Optional[str] = None
    sender_name: Optional[str] = None


@dataclass
class InvoiceItem:
    """Позиция счета-фактуры"""
    line_number: int
    name: str
    unit_code: Optional[str] = None
    unit_name: Optional[str] = None
    quantity: Decimal = Decimal('0')
    price: Decimal = Decimal('0')
    amount_without_vat: Decimal = Decimal('0')
    vat_rate: Optional[str] = None
    vat_amount: Decimal = Decimal('0')
    amount_with_vat: Decimal = Decimal('0')
    article: Optional[str] = None  # Артикул товара из КодТов


@dataclass
class Organization:
    """Информация об организации"""
    name: str
    inn: str
    kpp: Optional[str] = None
    address: Optional[Address] = None


@dataclass
class UPDContent:
    """Основное содержимое УПД"""
    # Сведения о счете-фактуре
    invoice_number: str
    invoice_date: datetime
    seller: Organization
    buyer: Organization
    
    # Опциональные поля с значениями по умолчанию
    items: List[InvoiceItem] = None
    currency_code: str = "643"  # RUB по умолчанию
    total_without_vat: Decimal = Decimal('0')
    total_vat: Decimal = Decimal('0')
    total_with_vat: Decimal = Decimal('0')
    requisite_number: Optional[str] = None  # Номер счета из реквизитов
    
    def __post_init__(self):
        if self.items is None:
            self.items = []


@dataclass
class UPDDocument:
    """Полный УПД документ"""
    meta_info: MetaInfo
    card_info: CardInfo
    content: UPDContent
    
    @property
    def document_id(self) -> str:
        """Уникальный идентификатор документа"""
        return self.card_info.external_identifier
    
    @property
    def summary(self) -> str:
        """Краткое описание документа"""
        return (
            f"УПД № {self.content.invoice_number} от {self.content.invoice_date.strftime('%d.%m.%Y')}\n"
            f"Поставщик: {self.content.seller.name} (ИНН: {self.content.seller.inn})\n"
            f"Покупатель: {self.content.buyer.name} (ИНН: {self.content.buyer.inn})\n"
            f"Сумма: {self.content.total_with_vat:,.2f} ₽"
        )


@dataclass
class ProcessingResult:
    """Результат обработки УПД"""
    success: bool
    message: str
    upd_document: Optional[UPDDocument] = None
    moysklad_invoice_id: Optional[str] = None
    moysklad_invoice_url: Optional[str] = None
    error_code: Optional[str] = None