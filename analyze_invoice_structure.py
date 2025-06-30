#!/usr/bin/env python3
"""
Детальный анализ структуры XML файла счета покупателю в формате CommerceML
"""
import os
from xml.etree import ElementTree as ET
from datetime import datetime

def analyze_commerceml_invoice():
    """Анализ счета в формате CommerceML"""
    invoice_path = "Sample/Account/1/Schet na oplatu 239 27.06.2025 (30.06.2025 101328).xml"
    
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ СЧЕТА В ФОРМАТЕ COMMERCEML")
    print("=" * 70)
    
    try:
        with open(invoice_path, 'r', encoding='windows-1251') as f:
            content = f.read()
        
        tree = ET.fromstring(content)
        
        # Namespace для CommerceML
        ns = {'cm': 'urn:1C.ru:commerceml_2'}
        
        print("📋 ОСНОВНАЯ ИНФОРМАЦИЯ О ДОКУМЕНТЕ:")
        print("-" * 40)
        
        # Извлекаем основные данные документа
        doc = tree.find('.//cm:Документ', ns)
        if doc is not None:
            doc_id = doc.find('cm:Ид', ns)
            doc_number = doc.find('cm:Номер', ns)
            doc_date = doc.find('cm:Дата', ns)
            doc_operation = doc.find('cm:ХозОперация', ns)
            doc_role = doc.find('cm:Роль', ns)
            doc_currency = doc.find('cm:Валюта', ns)
            doc_rate = doc.find('cm:Курс', ns)
            doc_sum = doc.find('cm:Сумма', ns)
            doc_comment = doc.find('cm:Комментарий', ns)
            
            print(f"ID: {doc_id.text if doc_id is not None else 'Не указан'}")
            print(f"Номер: {doc_number.text if doc_number is not None else 'Не указан'}")
            print(f"Дата: {doc_date.text if doc_date is not None else 'Не указана'}")
            print(f"Операция: {doc_operation.text if doc_operation is not None else 'Не указана'}")
            print(f"Роль: {doc_role.text if doc_role is not None else 'Не указана'}")
            print(f"Валюта: {doc_currency.text if doc_currency is not None else 'Не указана'}")
            print(f"Курс: {doc_rate.text if doc_rate is not None else 'Не указан'}")
            print(f"Сумма: {doc_sum.text if doc_sum is not None else 'Не указана'}")
            print(f"Комментарий: {doc_comment.text if doc_comment is not None else 'Не указан'}")
        
        print("\n👥 КОНТРАГЕНТЫ:")
        print("-" * 40)
        
        # Анализируем контрагентов
        contractors = doc.findall('.//cm:Контрагент', ns)
        for i, contractor in enumerate(contractors, 1):
            print(f"\nКонтрагент {i}:")
            
            contractor_id = contractor.find('cm:Ид', ns)
            contractor_name = contractor.find('cm:Наименование', ns)
            contractor_full_name = contractor.find('cm:ПолноеНаименование', ns)
            contractor_role = contractor.find('cm:Роль', ns)
            
            print(f"  ID: {contractor_id.text if contractor_id is not None else 'Не указан'}")
            print(f"  Наименование: {contractor_name.text if contractor_name is not None else 'Не указано'}")
            print(f"  Полное наименование: {contractor_full_name.text if contractor_full_name is not None else 'Не указано'}")
            print(f"  Роль: {contractor_role.text if contractor_role is not None else 'Не указана'}")
            
            # Реквизиты
            requisites = contractor.find('cm:Реквизиты', ns)
            if requisites is not None:
                print("  Реквизиты:")
                for req in requisites:
                    req_name = req.find('cm:Наименование', ns)
                    req_value = req.find('cm:Значение', ns)
                    if req_name is not None and req_value is not None:
                        print(f"    {req_name.text}: {req_value.text}")
            
            # Адрес
            address = contractor.find('cm:АдресРегистрации', ns)
            if address is not None:
                print("  Адрес регистрации:")
                for addr_elem in address:
                    if addr_elem.text:
                        print(f"    {addr_elem.tag.split('}')[-1]}: {addr_elem.text}")
        
        print("\n📦 ТОВАРЫ И УСЛУГИ:")
        print("-" * 40)
        
        # Анализируем товары
        products = doc.findall('.//cm:Товар', ns)
        for i, product in enumerate(products, 1):
            print(f"\nТовар {i}:")
            
            product_id = product.find('cm:Ид', ns)
            product_name = product.find('cm:Наименование', ns)
            product_article = product.find('cm:Артикул', ns)
            
            print(f"  ID: {product_id.text if product_id is not None else 'Не указан'}")
            print(f"  Наименование: {product_name.text if product_name is not None else 'Не указано'}")
            print(f"  Артикул: {product_article.text if product_article is not None else 'Не указан'}")
            
            # Базовая единица
            base_unit = product.find('cm:БазовыеЕдиницы', ns)
            if base_unit is not None:
                unit_code = base_unit.get('Код')
                unit_name = base_unit.get('НаименованиеПолное')
                print(f"  Единица измерения: {unit_name} (код: {unit_code})")
            
            # Реквизиты товара
            product_requisites = product.find('cm:ЗначенияРеквизитов', ns)
            if product_requisites is not None:
                print("  Реквизиты товара:")
                for req in product_requisites.findall('cm:ЗначениеРеквизита', ns):
                    req_name = req.find('cm:Наименование', ns)
                    req_value = req.find('cm:Значение', ns)
                    if req_name is not None and req_value is not None:
                        print(f"    {req_name.text}: {req_value.text}")
            
            # Цены
            prices = product.find('cm:Цены', ns)
            if prices is not None:
                print("  Цены:")
                for price in prices.findall('cm:Цена', ns):
                    price_id = price.find('cm:ИдТипаЦены', ns)
                    price_value = price.find('cm:ЦенаЗаЕдиницу', ns)
                    price_currency = price.find('cm:Валюта', ns)
                    price_unit = price.find('cm:Единица', ns)
                    
                    print(f"    Тип цены: {price_id.text if price_id is not None else 'Не указан'}")
                    print(f"    Цена за единицу: {price_value.text if price_value is not None else 'Не указана'}")
                    print(f"    Валюта: {price_currency.text if price_currency is not None else 'Не указана'}")
                    print(f"    Единица: {price_unit.text if price_unit is not None else 'Не указана'}")
        
        print("\n📊 ТАБЛИЧНАЯ ЧАСТЬ:")
        print("-" * 40)
        
        # Анализируем табличную часть
        table_part = doc.find('cm:ТабличнаяЧасть', ns)
        if table_part is not None:
            rows = table_part.findall('cm:СтрокаТабличнойЧасти', ns)
            print(f"Количество строк: {len(rows)}")
            
            for i, row in enumerate(rows, 1):
                print(f"\nСтрока {i}:")
                
                row_id = row.find('cm:Ид', ns)
                row_product = row.find('cm:Товар', ns)
                row_quantity = row.find('cm:Количество', ns)
                row_price = row.find('cm:Цена', ns)
                row_sum = row.find('cm:Сумма', ns)
                row_discount_percent = row.find('cm:ПроцентСкидки', ns)
                row_discount_sum = row.find('cm:СуммаСкидки', ns)
                row_vat_rate = row.find('cm:СтавкаНДС', ns)
                row_vat_sum = row.find('cm:СуммаНДС', ns)
                row_total = row.find('cm:Всего', ns)
                
                print(f"  ID строки: {row_id.text if row_id is not None else 'Не указан'}")
                print(f"  Товар: {row_product.text if row_product is not None else 'Не указан'}")
                print(f"  Количество: {row_quantity.text if row_quantity is not None else 'Не указано'}")
                print(f"  Цена: {row_price.text if row_price is not None else 'Не указана'}")
                print(f"  Сумма: {row_sum.text if row_sum is not None else 'Не указана'}")
                print(f"  Процент скидки: {row_discount_percent.text if row_discount_percent is not None else 'Не указан'}")
                print(f"  Сумма скидки: {row_discount_sum.text if row_discount_sum is not None else 'Не указана'}")
                print(f"  Ставка НДС: {row_vat_rate.text if row_vat_rate is not None else 'Не указана'}")
                print(f"  Сумма НДС: {row_vat_sum.text if row_vat_sum is not None else 'Не указана'}")
                print(f"  Всего: {row_total.text if row_total is not None else 'Не указано'}")
                
                # Реквизиты строки
                row_requisites = row.find('cm:ЗначенияРеквизитов', ns)
                if row_requisites is not None:
                    print("  Реквизиты строки:")
                    for req in row_requisites.findall('cm:ЗначениеРеквизита', ns):
                        req_name = req.find('cm:Наименование', ns)
                        req_value = req.find('cm:Значение', ns)
                        if req_name is not None and req_value is not None:
                            print(f"    {req_name.text}: {req_value.text}")
        
        return extract_invoice_data(tree, ns)
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")
        return None

def extract_invoice_data(tree, ns):
    """Извлечение структурированных данных из счета"""
    print("\n\n📋 ИЗВЛЕЧЕННЫЕ СТРУКТУРИРОВАННЫЕ ДАННЫЕ:")
    print("=" * 70)
    
    data = {
        'invoice_info': {},
        'seller': {},
        'buyer': {},
        'items': []
    }
    
    try:
        doc = tree.find('.//cm:Документ', ns)
        if doc is not None:
            # Основная информация о счете
            doc_number = doc.find('cm:Номер', ns)
            doc_date = doc.find('cm:Дата', ns)
            doc_sum = doc.find('cm:Сумма', ns)
            doc_comment = doc.find('cm:Комментарий', ns)
            
            data['invoice_info'] = {
                'number': doc_number.text if doc_number is not None else None,
                'date': doc_date.text if doc_date is not None else None,
                'total_sum': doc_sum.text if doc_sum is not None else None,
                'comment': doc_comment.text if doc_comment is not None else None
            }
            
            # Контрагенты
            contractors = doc.findall('.//cm:Контрагент', ns)
            for contractor in contractors:
                role = contractor.find('cm:Роль', ns)
                role_text = role.text if role is not None else ''
                
                contractor_data = {
                    'id': contractor.find('cm:Ид', ns).text if contractor.find('cm:Ид', ns) is not None else None,
                    'name': contractor.find('cm:Наименование', ns).text if contractor.find('cm:Наименование', ns) is not None else None,
                    'full_name': contractor.find('cm:ПолноеНаименование', ns).text if contractor.find('cm:ПолноеНаименование', ns) is not None else None,
                    'requisites': {}
                }
                
                # Реквизиты
                requisites = contractor.find('cm:Реквизиты', ns)
                if requisites is not None:
                    for req in requisites:
                        req_name = req.find('cm:Наименование', ns)
                        req_value = req.find('cm:Значение', ns)
                        if req_name is not None and req_value is not None:
                            contractor_data['requisites'][req_name.text] = req_value.text
                
                if 'Продавец' in role_text:
                    data['seller'] = contractor_data
                elif 'Покупатель' in role_text:
                    data['buyer'] = contractor_data
            
            # Товары из табличной части
            table_part = doc.find('cm:ТабличнаяЧасть', ns)
            if table_part is not None:
                rows = table_part.findall('cm:СтрокаТабличнойЧасти', ns)
                
                for row in rows:
                    item_data = {
                        'product_id': row.find('cm:Товар', ns).text if row.find('cm:Товар', ns) is not None else None,
                        'quantity': row.find('cm:Количество', ns).text if row.find('cm:Количество', ns) is not None else None,
                        'price': row.find('cm:Цена', ns).text if row.find('cm:Цена', ns) is not None else None,
                        'sum': row.find('cm:Сумма', ns).text if row.find('cm:Сумма', ns) is not None else None,
                        'vat_rate': row.find('cm:СтавкаНДС', ns).text if row.find('cm:СтавкаНДС', ns) is not None else None,
                        'vat_sum': row.find('cm:СуммаНДС', ns).text if row.find('cm:СуммаНДС', ns) is not None else None,
                        'total': row.find('cm:Всего', ns).text if row.find('cm:Всего', ns) is not None else None
                    }
                    data['items'].append(item_data)
        
        # Выводим извлеченные данные
        print("💰 Информация о счете:")
        for key, value in data['invoice_info'].items():
            print(f"  {key}: {value}")
        
        print("\n🏢 Продавец:")
        for key, value in data['seller'].items():
            if key == 'requisites':
                print(f"  {key}:")
                for req_name, req_value in value.items():
                    print(f"    {req_name}: {req_value}")
            else:
                print(f"  {key}: {value}")
        
        print("\n🏪 Покупатель:")
        for key, value in data['buyer'].items():
            if key == 'requisites':
                print(f"  {key}:")
                for req_name, req_value in value.items():
                    print(f"    {req_name}: {req_value}")
            else:
                print(f"  {key}: {value}")
        
        print(f"\n📦 Товары ({len(data['items'])} позиций):")
        for i, item in enumerate(data['items'], 1):
            print(f"  Позиция {i}:")
            for key, value in item.items():
                print(f"    {key}: {value}")
        
        return data
        
    except Exception as e:
        print(f"❌ Ошибка извлечения данных: {e}")
        return data

if __name__ == "__main__":
    analyze_commerceml_invoice()