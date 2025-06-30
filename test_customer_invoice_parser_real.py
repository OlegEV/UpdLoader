#!/usr/bin/env python3
"""
Тестирование реального парсера счетов покупателю
"""
import os
import sys
import tempfile
import zipfile
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, 'src')

from customer_invoice_parser import CustomerInvoiceParser, CustomerInvoiceParsingError

def create_test_archive():
    """Создание тестового архива из примера"""
    print("📦 Создание тестового архива...")
    
    # Создаем временный ZIP файл
    temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(temp_zip.name, 'w') as zip_file:
            # Добавляем meta.xml
            meta_path = "Sample/Account/meta.xml"
            if os.path.exists(meta_path):
                zip_file.write(meta_path, "meta.xml")
                print(f"✅ Добавлен: meta.xml")
            
            # Добавляем card.xml
            card_path = "Sample/Account/1/card.xml"
            if os.path.exists(card_path):
                zip_file.write(card_path, "1/card.xml")
                print(f"✅ Добавлен: 1/card.xml")
            
            # Добавляем основной XML файл счета
            invoice_path = "Sample/Account/1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml"
            if os.path.exists(invoice_path):
                zip_file.write(invoice_path, "1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml")
                print(f"✅ Добавлен: основной XML файл счета")
        
        print(f"📦 Тестовый архив создан: {temp_zip.name}")
        return temp_zip.name
        
    except Exception as e:
        print(f"❌ Ошибка создания архива: {e}")
        if os.path.exists(temp_zip.name):
            os.remove(temp_zip.name)
        return None

def test_parser():
    """Тестирование парсера"""
    print("\n🧪 ТЕСТИРОВАНИЕ ПАРСЕРА СЧЕТОВ ПОКУПАТЕЛЮ")
    print("=" * 60)
    
    # Создаем тестовый архив
    test_archive = create_test_archive()
    if not test_archive:
        print("❌ Не удалось создать тестовый архив")
        return
    
    try:
        # Создаем парсер
        parser = CustomerInvoiceParser()
        
        # Парсим документ
        print("\n🔍 Парсинг документа...")
        invoice_doc = parser.parse_customer_invoice_archive(test_archive)
        
        # Выводим результаты
        print("\n✅ РЕЗУЛЬТАТЫ ПАРСИНГА:")
        print("-" * 40)
        
        print(f"📄 Номер счета: {invoice_doc.invoice_number}")
        print(f"📅 Дата счета: {invoice_doc.invoice_date.strftime('%d.%m.%Y')}")
        print(f"💰 Общая сумма: {invoice_doc.total_sum:,.2f} ₽")
        
        print(f"\n🏢 Продавец:")
        print(f"   Название: {invoice_doc.seller.name}")
        print(f"   ИНН: {invoice_doc.seller.inn}")
        print(f"   КПП: {invoice_doc.seller.kpp or 'не указан'}")
        
        print(f"\n🏪 Покупатель:")
        print(f"   Название: {invoice_doc.buyer.name}")
        print(f"   ИНН: {invoice_doc.buyer.inn}")
        print(f"   КПП: {invoice_doc.buyer.kpp or 'не указан'}")
        
        print(f"\n📦 Товары ({len(invoice_doc.items)} позиций):")
        for i, item in enumerate(invoice_doc.items, 1):
            print(f"   {i}. {item.name}")
            print(f"      Артикул: {item.article or 'не указан'}")
            print(f"      Количество: {item.quantity}")
            print(f"      Цена: {item.price:,.2f} ₽")
            print(f"      Сумма: {item.amount_with_vat:,.2f} ₽")
            print(f"      НДС: {item.vat_rate or 'не указан'}")
        
        # Тестируем логику для создания заказа покупателя
        print(f"\n🎯 ДАННЫЕ ДЛЯ СОЗДАНИЯ ЗАКАЗА ПОКУПАТЕЛЯ:")
        print("-" * 50)
        
        order_number = f"П{invoice_doc.invoice_number}"
        print(f"📋 Номер заказа: {order_number}")
        print(f"📅 Дата заказа: {invoice_doc.invoice_date.strftime('%d.%m.%Y')}")
        
        print(f"\n📦 Товары для заказа:")
        for item in invoice_doc.items:
            # Определяем группу товара по артикулу/названию
            group = determine_product_group(item)
            warehouse, project = get_warehouse_and_project(group)
            
            print(f"   • {item.name}")
            print(f"     Артикул: {item.article or 'не указан'}")
            print(f"     Группа: {group}")
            print(f"     Склад: {warehouse}")
            print(f"     Проект: {project}")
            print(f"     Количество: {item.quantity}")
            print(f"     Комментарий: {item.name} - {item.quantity} шт")
        
        print(f"\n✅ Парсинг успешно завершен!")
        return invoice_doc
        
    except CustomerInvoiceParsingError as e:
        print(f"❌ Ошибка парсинга: {e}")
        return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None
    finally:
        # Очищаем временный файл
        if os.path.exists(test_archive):
            os.remove(test_archive)
            print(f"\n🧹 Временный архив удален")

def determine_product_group(item):
    """Определение группы товара"""
    name_lower = item.name.lower()
    article_lower = (item.article or '').lower()
    
    # Проверяем ключевые слова для труб
    tube_keywords = ['труба', 'трубы', 'pipe', 'tube']
    for keyword in tube_keywords:
        if keyword in name_lower or keyword in article_lower:
            return 'трубы'
    
    # Проверяем ключевые слова для профилей
    profile_keywords = ['профиль', 'профили', 'profile']
    for keyword in profile_keywords:
        if keyword in name_lower or keyword in article_lower:
            return 'профиль'
    
    # По умолчанию
    return 'неопределено'

def get_warehouse_and_project(group):
    """Получение склада и проекта по группе товара"""
    if group == 'профиль':
        return 'Гатчина', 'Профили'
    elif group == 'трубы':
        return 'Сестрорецк ПП', 'Трубы'
    else:
        return 'Основной склад', 'Основной проект'

if __name__ == "__main__":
    # Проверяем наличие необходимых файлов
    required_files = [
        "Sample/Account/meta.xml",
        "Sample/Account/1/card.xml",
        "Sample/Account/1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Отсутствуют необходимые файлы:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        sys.exit(1)
    
    # Запускаем тестирование
    test_parser()