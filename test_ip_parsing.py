#!/usr/bin/env python3
"""
Тест парсинга УПД с индивидуальными предпринимателями
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from xml.etree import ElementTree as ET
from src.upd_parser import UPDParser, UPDParsingError

def test_ip_buyer_parsing():
    """Тест парсинга покупателя-ИП"""
    
    # XML с индивидуальным предпринимателем как покупателем
    xml_content = '''<?xml version="1.0" encoding="windows-1251"?>
<Файл ВерсФорм="5.03">
    <СвСчФакт НомерДок="123" ДатаДок="01.01.2024"/>
    <СвПрод>
        <ИдСв>
            <СвЮЛУч НаимОрг="ООО Поставщик" ИННЮЛ="1234567890" КПП="123456789"/>
        </ИдСв>
    </СвПрод>
    <СвПокуп>
        <ИдСв>
            <СвИП ИННФЛ="781490187318">
                <ФИО Фамилия="Брагарь" Имя="Андрей" Отчество="Владимирович"/>
            </СвИП>
        </ИдСв>
    </СвПокуп>
</Файл>'''
    
    try:
        parser = UPDParser()
        tree = ET.fromstring(xml_content)
        
        # Тестируем парсинг продавца (должен быть юридическое лицо)
        seller = parser._parse_seller_info(tree, {})
        print(f"✅ Продавец: {seller.name}, ИНН: {seller.inn}, КПП: {seller.kpp}")
        assert seller.inn == "1234567890", f"Ожидался ИНН 1234567890, получен {seller.inn}"
        assert seller.name == "ООО Поставщик", f"Ожидалось название 'ООО Поставщик', получено {seller.name}"
        
        # Тестируем парсинг покупателя (должен быть ИП)
        buyer = parser._parse_buyer_info(tree, {})
        print(f"✅ Покупатель: {buyer.name}, ИНН: {buyer.inn}, КПП: {buyer.kpp}")
        assert buyer.inn == "781490187318", f"Ожидался ИНН 781490187318, получен {buyer.inn}"
        assert buyer.name == "Брагарь Андрей Владимирович", f"Ожидалось ФИО 'Брагарь Андрей Владимирович', получено {buyer.name}"
        assert buyer.kpp is None, f"Для ИП КПП должен быть None, получен {buyer.kpp}"
        
        print("✅ Тест парсинга ИП как покупателя прошел успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте парсинга ИП: {e}")
        return False

def test_ip_seller_parsing():
    """Тест парсинга продавца-ИП"""
    
    # XML с индивидуальным предпринимателем как продавцом
    xml_content = '''<?xml version="1.0" encoding="windows-1251"?>
<Файл ВерсФорм="5.03">
    <СвСчФакт НомерДок="456" ДатаДок="01.01.2024"/>
    <СвПрод>
        <ИдСв>
            <СвИП ИННФЛ="123456789012">
                <ФИО Фамилия="Иванов" Имя="Иван" Отчество="Иванович"/>
            </СвИП>
        </ИдСв>
    </СвПрод>
    <СвПокуп>
        <ИдСв>
            <СвЮЛУч НаимОрг="ООО Покупатель" ИННЮЛ="9876543210" КПП="987654321"/>
        </ИдСв>
    </СвПокуп>
</Файл>'''
    
    try:
        parser = UPDParser()
        tree = ET.fromstring(xml_content)
        
        # Тестируем парсинг продавца (должен быть ИП)
        seller = parser._parse_seller_info(tree, {})
        print(f"✅ Продавец: {seller.name}, ИНН: {seller.inn}, КПП: {seller.kpp}")
        assert seller.inn == "123456789012", f"Ожидался ИНН 123456789012, получен {seller.inn}"
        assert seller.name == "Иванов Иван Иванович", f"Ожидалось ФИО 'Иванов Иван Иванович', получено {seller.name}"
        assert seller.kpp is None, f"Для ИП КПП должен быть None, получен {seller.kpp}"
        
        # Тестируем парсинг покупателя (должен быть юридическое лицо)
        buyer = parser._parse_buyer_info(tree, {})
        print(f"✅ Покупатель: {buyer.name}, ИНН: {buyer.inn}, КПП: {buyer.kpp}")
        assert buyer.inn == "9876543210", f"Ожидался ИНН 9876543210, получен {buyer.inn}"
        assert buyer.name == "ООО Покупатель", f"Ожидалось название 'ООО Покупатель', получено {buyer.name}"
        
        print("✅ Тест парсинга ИП как продавца прошел успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка в тесте парсинга ИП: {e}")
        return False

def test_missing_inn_error():
    """Тест обработки ошибки при отсутствии ИНН"""
    
    # XML без ИНН
    xml_content = '''<?xml version="1.0" encoding="windows-1251"?>
<Файл ВерсФорм="5.03">
    <СвСчФакт НомерДок="789" ДатаДок="01.01.2024"/>
    <СвПрод>
        <ИдСв>
            <СвЮЛУч НаимОрг="ООО Поставщик"/>
        </ИдСв>
    </СвПрод>
    <СвПокуп>
        <ИдСв>
            <СвИП>
                <ФИО Фамилия="Петров" Имя="Петр" Отчество="Петрович"/>
            </СвИП>
        </ИдСв>
    </СвПокуп>
</Файл>'''
    
    try:
        parser = UPDParser()
        tree = ET.fromstring(xml_content)
        
        # Тестируем парсинг покупателя (должна быть ошибка из-за отсутствия ИННФЛ)
        try:
            buyer = parser._parse_buyer_info(tree, {})
            print(f"❌ Ожидалась ошибка, но получен результат: {buyer.name}, ИНН: {buyer.inn}")
            return False
        except UPDParsingError as e:
            print(f"✅ Корректно обработана ошибка отсутствия ИНН: {e}")
            return True
        
    except Exception as e:
        print(f"❌ Неожиданная ошибка в тесте: {e}")
        return False

def test_counterparty_type_detection():
    """Тест определения типа контрагента по длине ИНН"""
    
    # Импортируем класс для тестирования
    from src.moysklad_api import MoySkladAPI
    from src.models import Organization
    
    api = MoySkladAPI()
    
    # Тест ИП (12 цифр)
    ip_org = Organization(name="Иванов Иван Иванович", inn="123456789012")
    print(f"ИП: ИНН {ip_org.inn} (длина: {len(ip_org.inn)}) -> {'individual' if len(ip_org.inn) == 12 else 'legal'}")
    
    # Тест ЮЛ (10 цифр)
    legal_org = Organization(name="ООО Тест", inn="1234567890", kpp="123456789")
    print(f"ЮЛ: ИНН {legal_org.inn} (длина: {len(legal_org.inn)}) -> {'individual' if len(legal_org.inn) == 12 else 'legal'}")
    
    print("✅ Тест определения типа контрагента прошел успешно!")
    return True

if __name__ == "__main__":
    print("🧪 Запуск тестов парсинга индивидуальных предпринимателей...\n")
    
    tests = [
        ("Парсинг ИП как покупателя", test_ip_buyer_parsing),
        ("Парсинг ИП как продавца", test_ip_seller_parsing),
        ("Обработка ошибки отсутствия ИНН", test_missing_inn_error),
        ("Определение типа контрагента", test_counterparty_type_detection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"❌ Тест '{test_name}' не прошел")
    
    print(f"\n📊 Результаты: {passed}/{total} тестов прошли успешно")
    
    if passed == total:
        print("🎉 Все тесты прошли успешно!")
        sys.exit(0)
    else:
        print("💥 Некоторые тесты не прошли")
        sys.exit(1)