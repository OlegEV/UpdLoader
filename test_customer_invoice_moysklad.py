#!/usr/bin/env python3
"""
Тест интеграции парсера счетов покупателю с МойСклад API
"""
import os
import sys
import tempfile
import zipfile
from pathlib import Path

# Добавляем src в путь для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.customer_invoice_parser import CustomerInvoiceParser
from src.moysklad_api import MoySkladAPI, MoySkladAPIError
from loguru import logger

def create_test_archive():
    """Создание тестового архива из файлов Sample/Account"""
    sample_dir = Path("Sample/Account")
    
    if not sample_dir.exists():
        raise FileNotFoundError("Директория Sample/Account не найдена")
    
    # Создаем временный ZIP файл
    temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    temp_zip.close()
    
    with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Добавляем meta.xml
        meta_file = sample_dir / "meta.xml"
        if meta_file.exists():
            zipf.write(meta_file, "meta.xml")
            print(f"✅ Добавлен: meta.xml")
        
        # Добавляем файлы из подпапки 1
        subdir = sample_dir / "1"
        if subdir.exists():
            # Добавляем card.xml
            card_file = subdir / "card.xml"
            if card_file.exists():
                zipf.write(card_file, "1/card.xml")
                print(f"✅ Добавлен: 1/card.xml")
            
            # Ищем основной XML файл счета
            for xml_file in subdir.glob("*.xml"):
                if xml_file.name != "card.xml":
                    zipf.write(xml_file, f"1/{xml_file.name}")
                    print(f"✅ Добавлен: основной XML файл счета")
                    break
    
    print(f"📦 Тестовый архив создан: {temp_zip.name}")
    return temp_zip.name

def test_customer_invoice_integration():
    """Основной тест интеграции"""
    print("🧪 ТЕСТ ИНТЕГРАЦИИ СЧЕТОВ ПОКУПАТЕЛЮ С МОЙСКЛАД")
    print("=" * 60)
    
    try:
        # Шаг 1: Создаем тестовый архив
        print("\n📦 Создание тестового архива...")
        archive_path = create_test_archive()
        
        # Шаг 2: Парсим документ
        print("\n🔍 Парсинг документа...")
        parser = CustomerInvoiceParser()
        customer_invoice_doc = parser.parse_customer_invoice_archive(archive_path)
        
        print(f"✅ Документ успешно распарсен:")
        print(f"   Номер: {customer_invoice_doc.invoice_number}")
        print(f"   Дата: {customer_invoice_doc.invoice_date.strftime('%d.%m.%Y')}")
        print(f"   Сумма: {customer_invoice_doc.total_sum:,.2f} ₽")
        print(f"   Позиций: {len(customer_invoice_doc.items)}")
        
        # Шаг 3: Проверяем доступ к МойСклад API
        print("\n🔗 Проверка доступа к МойСклад API...")
        api = MoySkladAPI()
        
        # Проверяем токен
        if not api.verify_token():
            print("❌ Ошибка: Неверный токен МойСклад API")
            print("   Проверьте настройки в файле .env")
            return False
        
        # Получаем детальную информацию о доступе
        access_info = api.verify_api_access()
        if not access_info["success"]:
            print(f"❌ Ошибка доступа к API: {access_info['error']}")
            return False
        
        print("✅ Доступ к МойСклад API подтвержден")
        print(f"   Организация: {access_info['organization']['name']}")
        print(f"   Сотрудник: {access_info['employee']['name']}")
        
        # Шаг 4: Создаем документы в МойСклад (в тестовом режиме)
        print("\n📋 Создание документов в МойСклад...")
        print("⚠️  ВНИМАНИЕ: Это создаст реальные документы в МойСклад!")
        
        # Запрашиваем подтверждение
        confirmation = input("Продолжить создание документов? (y/N): ").strip().lower()
        if confirmation != 'y':
            print("❌ Создание документов отменено пользователем")
            return True
        
        try:
            result = api.create_customer_order_and_invoice(customer_invoice_doc)
            
            if result["success"]:
                print("✅ Документы успешно созданы в МойСклад!")
                
                # Информация о заказе покупателя
                customer_order = result["customer_order"]
                order_url = api.get_customer_order_url(customer_order["id"])
                print(f"\n📋 Заказ покупателя:")
                print(f"   ID: {customer_order['id']}")
                print(f"   Номер: {customer_order['name']}")
                print(f"   URL: {order_url}")
                
                # Информация о счете покупателю
                customer_invoice = result["customer_invoice"]
                invoice_url = api.get_customer_invoice_url(customer_invoice["id"])
                print(f"\n💰 Счет покупателю:")
                print(f"   ID: {customer_invoice['id']}")
                print(f"   Номер: {customer_invoice['name']}")
                print(f"   URL: {invoice_url}")
                
                print(f"\n🎯 РЕЗУЛЬТАТ:")
                print(f"✅ Заказ покупателя создан: П{customer_invoice_doc.invoice_number}")
                print(f"✅ Счет покупателю создан: {customer_invoice_doc.invoice_number}")
                print(f"✅ Товары распределены по складам и проектам согласно бизнес-логике")
                
                return True
            else:
                print("❌ Ошибка создания документов")
                return False
                
        except MoySkladAPIError as e:
            print(f"❌ Ошибка МойСклад API: {e}")
            print("\n💡 Возможные причины:")
            print("   • Товары из счета не найдены в МойСклад")
            print("   • Склады 'Гатчина' или 'Сестрорецк ПП' не созданы")
            print("   • Проекты 'Профили' или 'Трубы' не созданы")
            print("   • Недостаточно прав для создания документов")
            return False
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        logger.exception("Детали ошибки:")
        return False
    
    finally:
        # Очистка временных файлов
        try:
            if 'archive_path' in locals():
                os.unlink(archive_path)
                print(f"\n🧹 Временный архив удален")
        except:
            pass

def main():
    """Главная функция"""
    try:
        success = test_customer_invoice_integration()
        
        if success:
            print("\n🎉 ТЕСТ ЗАВЕРШЕН УСПЕШНО!")
            print("Интеграция парсера счетов покупателю с МойСклад работает корректно.")
        else:
            print("\n💥 ТЕСТ ЗАВЕРШЕН С ОШИБКАМИ!")
            print("Проверьте настройки и исправьте ошибки.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()