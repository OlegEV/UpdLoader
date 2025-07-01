"""
Тест функциональности добавления комментариев в заказы и счета
"""
import sys
import os
from datetime import datetime
from loguru import logger

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from moysklad_api import MoySkladAPI
from customer_invoice_parser import CustomerInvoiceDocument
from models import InvoiceItem, Organization

def test_comment_generation():
    """Тест генерации комментария из товаров"""
    
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")
    
    # Создаем тестовые данные
    seller = Organization(
        name="ООО Тест Продавец",
        inn="1234567890",
        kpp="123456789"
    )
    
    buyer = Organization(
        name="ООО Тест Покупатель", 
        inn="0987654321",
        kpp="987654321"
    )
    
    # Создаем тестовые товары
    from decimal import Decimal
    items = [
        InvoiceItem(
            line_number=1,
            name="Профиль алюминиевый",
            quantity=Decimal("10"),
            price=Decimal("150.50"),
            amount_without_vat=Decimal("1505.00"),
            vat_rate="20%",
            vat_amount=Decimal("301.00"),
            amount_with_vat=Decimal("1806.00"),
            article="PROF-001"
        ),
        InvoiceItem(
            line_number=2,
            name="Труба стальная",
            quantity=Decimal("5"),
            price=Decimal("200.00"),
            amount_without_vat=Decimal("1000.00"),
            vat_rate="20%",
            vat_amount=Decimal("200.00"),
            amount_with_vat=Decimal("1200.00"),
            article="TUBE-002"
        ),
        InvoiceItem(
            line_number=3,
            name="Болт крепежный",
            quantity=Decimal("100"),
            price=Decimal("5.25"),
            amount_without_vat=Decimal("525.00"),
            vat_rate="20%",
            vat_amount=Decimal("105.00"),
            amount_with_vat=Decimal("630.00"),
            article=""  # Без артикула
        )
    ]
    
    # Создаем документ счета
    customer_invoice_doc = CustomerInvoiceDocument(
        invoice_number="TEST-001",
        invoice_date=datetime.now(),
        seller=seller,
        buyer=buyer,
        items=items,
        total_sum=Decimal("3636.00")
    )
    
    # Создаем экземпляр API
    api = MoySkladAPI()
    
    # Тестируем генерацию комментария
    logger.info("Тестируем генерацию комментария...")
    comment = api._generate_comment_from_items(customer_invoice_doc)
    
    logger.info(f"Сгенерированный комментарий:")
    logger.info(f"---")
    logger.info(comment)
    logger.info(f"---")
    
    # Проверяем ожидаемый формат
    expected_lines = [
        "PROF-001 - 10",
        "TUBE-002 - 5", 
        "Болт крепежный - 100"  # Без артикула используется название
    ]
    
    actual_lines = comment.split('\n')
    
    logger.info("Проверяем соответствие ожидаемому формату...")
    
    success = True
    for i, expected_line in enumerate(expected_lines):
        if i < len(actual_lines):
            actual_line = actual_lines[i]
            if actual_line == expected_line:
                logger.info(f"✅ Строка {i+1}: '{actual_line}' - OK")
            else:
                logger.error(f"❌ Строка {i+1}: ожидалось '{expected_line}', получено '{actual_line}'")
                success = False
        else:
            logger.error(f"❌ Строка {i+1}: отсутствует в результате")
            success = False
    
    if len(actual_lines) > len(expected_lines):
        logger.warning(f"⚠️ Лишние строки в результате: {actual_lines[len(expected_lines):]}")
    
    if success:
        logger.info("🎉 Тест генерации комментария прошел успешно!")
        return True
    else:
        logger.error("💥 Тест генерации комментария провален!")
        return False

if __name__ == "__main__":
    success = test_comment_generation()
    sys.exit(0 if success else 1)