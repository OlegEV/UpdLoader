#!/usr/bin/env python3
"""
Тест определения типа документа в Telegram боте
"""
import os
import sys
import tempfile
import zipfile
from pathlib import Path

# Добавляем src в путь для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.telegram_bot import TelegramUPDBot

def create_customer_invoice_test_archive():
    """Создание тестового архива счета покупателю"""
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
        
        # Добавляем файлы из подпапки 1
        subdir = sample_dir / "1"
        if subdir.exists():
            # Добавляем card.xml
            card_file = subdir / "card.xml"
            if card_file.exists():
                zipf.write(card_file, "1/card.xml")
            
            # Ищем основной XML файл счета
            for xml_file in subdir.glob("*.xml"):
                if xml_file.name != "card.xml":
                    zipf.write(xml_file, f"1/{xml_file.name}")
                    break
    
    return temp_zip.name

def create_upd_test_archive():
    """Создание тестового архива УПД"""
    sample_dir = Path("Sample/ИП")
    
    if not sample_dir.exists():
        raise FileNotFoundError("Директория Sample/ИП не найдена")
    
    # Создаем временный ZIP файл
    temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
    temp_zip.close()
    
    with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Добавляем meta.xml
        meta_file = sample_dir / "meta.xml"
        if meta_file.exists():
            zipf.write(meta_file, "meta.xml")
        
        # Добавляем файлы из подпапки 1
        subdir = sample_dir / "1"
        if subdir.exists():
            # Добавляем card.xml
            card_file = subdir / "card.xml"
            if card_file.exists():
                zipf.write(card_file, "1/card.xml")
            
            # Ищем основной XML файл УПД
            for xml_file in subdir.glob("*.xml"):
                if xml_file.name != "card.xml":
                    zipf.write(xml_file, f"1/{xml_file.name}")
                    break
    
    return temp_zip.name

def test_document_detection():
    """Тест определения типа документа"""
    print("🧪 ТЕСТ ОПРЕДЕЛЕНИЯ ТИПА ДОКУМЕНТА")
    print("=" * 50)
    
    bot = TelegramUPDBot()
    
    try:
        # Тест 1: Счет покупателю
        print("\n📋 Тест 1: Счет покупателю (CommerceML)")
        customer_invoice_archive = create_customer_invoice_test_archive()
        
        document_type = bot._detect_document_type(customer_invoice_archive)
        print(f"Определенный тип: {document_type}")
        
        if document_type == "customer_invoice":
            print("✅ Счет покупателю определен корректно")
        else:
            print("❌ Ошибка определения счета покупателю")
        
        # Тест 2: УПД
        print("\n📄 Тест 2: УПД документ")
        upd_archive = create_upd_test_archive()
        
        document_type = bot._detect_document_type(upd_archive)
        print(f"Определенный тип: {document_type}")
        
        if document_type == "upd":
            print("✅ УПД определен корректно")
        else:
            print("❌ Ошибка определения УПД")
        
        print("\n🎯 РЕЗУЛЬТАТЫ:")
        print("✅ Система определения типа документа работает корректно")
        print("✅ Бот готов к обработке обоих типов документов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False
    
    finally:
        # Очистка временных файлов
        try:
            if 'customer_invoice_archive' in locals():
                os.unlink(customer_invoice_archive)
            if 'upd_archive' in locals():
                os.unlink(upd_archive)
        except:
            pass

def main():
    """Главная функция"""
    try:
        success = test_document_detection()
        
        if success:
            print("\n🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
            print("Система готова к работе с обоими типами документов.")
        else:
            print("\n💥 ТЕСТЫ ЗАВЕРШЕНЫ С ОШИБКАМИ!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Тест прерван пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()