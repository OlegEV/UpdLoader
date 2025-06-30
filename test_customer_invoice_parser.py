#!/usr/bin/env python3
"""
Тестовый парсер для анализа структуры XML файла счета покупателю
"""
import os
import sys
from xml.etree import ElementTree as ET
from pathlib import Path

def analyze_xml_structure(xml_path: str):
    """Анализ структуры XML файла"""
    print(f"Анализ файла: {xml_path}")
    print("=" * 60)
    
    if not os.path.exists(xml_path):
        print(f"❌ Файл не найден: {xml_path}")
        return
    
    try:
        # Попробуем разные кодировки
        encodings = ['windows-1251', 'utf-8', 'cp1251']
        
        for encoding in encodings:
            try:
                print(f"\n🔍 Пробую кодировку: {encoding}")
                
                with open(xml_path, 'r', encoding=encoding) as f:
                    content = f.read()
                
                print(f"📄 Размер файла: {len(content)} символов")
                print(f"📝 Первые 200 символов:")
                print(content[:200])
                print("...")
                
                # Если файл слишком короткий, это может быть только заголовок
                if len(content.strip()) <= 100:
                    print("⚠️  Файл содержит только XML заголовок")
                    continue
                
                # Парсим XML
                tree = ET.fromstring(content)
                print(f"\n✅ XML успешно распарсен с кодировкой {encoding}")
                
                # Анализируем структуру
                analyze_xml_element(tree, level=0)
                
                return tree
                
            except UnicodeDecodeError as e:
                print(f"❌ Ошибка кодировки {encoding}: {e}")
                continue
            except ET.ParseError as e:
                print(f"❌ Ошибка парсинга XML с {encoding}: {e}")
                continue
            except Exception as e:
                print(f"❌ Неожиданная ошибка с {encoding}: {e}")
                continue
        
        print("\n❌ Не удалось распарсить файл ни с одной кодировкой")
        
        # Попробуем прочитать как бинарный файл
        print("\n🔍 Анализ как бинарный файл:")
        with open(xml_path, 'rb') as f:
            binary_content = f.read(500)  # Первые 500 байт
        
        print(f"📄 Размер файла: {os.path.getsize(xml_path)} байт")
        print(f"🔢 Первые 100 байт (hex): {binary_content[:100].hex()}")
        
        # Попробуем найти текстовые части
        try:
            text_parts = binary_content.decode('windows-1251', errors='ignore')
            print(f"📝 Текстовые части: {text_parts[:200]}")
        except:
            print("❌ Не удалось извлечь текстовые части")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")

def analyze_xml_element(element, level=0):
    """Рекурсивный анализ элементов XML"""
    indent = "  " * level
    
    # Информация об элементе
    tag = element.tag
    attribs = element.attrib
    text = element.text.strip() if element.text else ""
    
    print(f"{indent}📋 Элемент: {tag}")
    
    if attribs:
        print(f"{indent}   🏷️  Атрибуты: {attribs}")
    
    if text:
        print(f"{indent}   📝 Текст: {text[:100]}{'...' if len(text) > 100 else ''}")
    
    # Анализируем дочерние элементы
    children = list(element)
    if children:
        print(f"{indent}   👶 Дочерних элементов: {len(children)}")
        
        # Показываем только первые 5 дочерних элементов для краткости
        for i, child in enumerate(children[:5]):
            if level < 3:  # Ограничиваем глубину
                analyze_xml_element(child, level + 1)
            else:
                print(f"{indent}    📋 {child.tag} (атрибуты: {len(child.attrib)}, текст: {'есть' if child.text and child.text.strip() else 'нет'})")
        
        if len(children) > 5:
            print(f"{indent}    ... и еще {len(children) - 5} элементов")

def test_card_xml():
    """Тестирование card.xml для понимания структуры"""
    card_path = "Sample/Account/1/card.xml"
    print("🧪 ТЕСТИРОВАНИЕ CARD.XML")
    print("=" * 60)
    
    analyze_xml_structure(card_path)

def test_main_invoice_xml():
    """Тестирование основного XML файла счета"""
    invoice_path = "Sample/Account/1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml"
    print("\n\n🧪 ТЕСТИРОВАНИЕ ОСНОВНОГО XML ФАЙЛА СЧЕТА")
    print("=" * 60)
    
    analyze_xml_structure(invoice_path)

def extract_invoice_data_from_card(card_path: str):
    """Извлечение данных счета из card.xml"""
    print("\n\n📊 ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ CARD.XML")
    print("=" * 60)
    
    try:
        with open(card_path, 'r', encoding='windows-1251') as f:
            content = f.read()
        
        tree = ET.fromstring(content)
        
        # Извлекаем основные данные
        data = {}
        
        # Идентификаторы
        identifiers = tree.find(".//{http://api-invoice.taxcom.ru/card}Identifiers")
        if identifiers is not None:
            data['external_identifier'] = identifiers.get("ExternalIdentifier")
        
        # Описание (название и дата)
        description = tree.find(".//{http://api-invoice.taxcom.ru/card}Description")
        if description is not None:
            data['title'] = description.get("Title")
            data['date'] = description.get("Date")
        
        # Отправитель
        sender = tree.find(".//{http://api-invoice.taxcom.ru/card}Sender")
        if sender is not None:
            abonent = sender.find(".//{http://api-invoice.taxcom.ru/card}Abonent")
            if abonent is not None:
                data['sender_name'] = abonent.get("Name")
                data['sender_inn'] = abonent.get("Inn")
                data['sender_kpp'] = abonent.get("Kpp")
        
        print("✅ Извлеченные данные:")
        for key, value in data.items():
            print(f"   {key}: {value}")
        
        # Попробуем извлечь номер счета из названия
        title = data.get('title', '')
        if title:
            import re
            # Ищем числа в названии
            numbers = re.findall(r'\d+', title)
            if numbers:
                print(f"\n🔢 Найденные числа в названии: {numbers}")
                print(f"   Возможный номер счета: {numbers[0]}")
        
        return data
        
    except Exception as e:
        print(f"❌ Ошибка извлечения данных: {e}")
        return {}

if __name__ == "__main__":
    print("🚀 ТЕСТИРОВАНИЕ ПАРСЕРА СЧЕТОВ ПОКУПАТЕЛЮ")
    print("=" * 80)
    
    # Проверяем существование файлов
    card_path = "Sample/Account/1/card.xml"
    invoice_path = "Sample/Account/1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml"
    
    if not os.path.exists(card_path):
        print(f"❌ Файл card.xml не найден: {card_path}")
        sys.exit(1)
    
    if not os.path.exists(invoice_path):
        print(f"❌ Файл счета не найден: {invoice_path}")
        sys.exit(1)
    
    # Тестируем парсинг
    test_card_xml()
    test_main_invoice_xml()
    
    # Извлекаем данные
    extract_invoice_data_from_card(card_path)
    
    print("\n\n✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")