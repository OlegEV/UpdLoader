"""
Парсер счетов покупателю в формате CommerceML
"""
import os
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from xml.etree import ElementTree as ET

from loguru import logger

from src.config import Config
from src.models import InvoiceItem, Organization


class CustomerInvoiceParsingError(Exception):
    """Ошибка парсинга счета покупателю"""
    pass


class CustomerInvoiceDocument:
    """Документ счета покупателю"""
    def __init__(self, invoice_number: str, invoice_date: datetime, 
                 seller: Organization, buyer: Organization, 
                 items: List[InvoiceItem], total_sum: Decimal):
        self.invoice_number = invoice_number
        self.invoice_date = invoice_date
        self.seller = seller
        self.buyer = buyer
        self.items = items
        self.total_sum = total_sum


class CustomerInvoiceParser:
    """Парсер счетов покупателю в формате CommerceML"""
    
    def __init__(self):
        self.encoding = Config.UPD_ENCODING
    
    def parse_customer_invoice_archive(self, zip_path: str) -> CustomerInvoiceDocument:
        """
        Основной метод парсинга архива счета покупателю
        
        Args:
            zip_path: Путь к ZIP архиву со счетом
            
        Returns:
            CustomerInvoiceDocument: Распарсенный документ счета
            
        Raises:
            CustomerInvoiceParsingError: Ошибка парсинга
        """
        try:
            logger.info(f"Начинаю парсинг архива счета покупателю: {zip_path}")
            
            # Извлекаем архив
            extract_dir = self._extract_archive(zip_path)
            
            # Ищем основной XML файл счета (CommerceML)
            invoice_xml_path = self._find_invoice_xml(extract_dir)
            
            # Парсим основной документ
            invoice_document = self._parse_invoice_xml(invoice_xml_path)
            
            logger.info(f"Счет покупателю успешно распарсен: № {invoice_document.invoice_number}")
            return invoice_document
            
        except Exception as e:
            logger.error(f"Ошибка парсинга счета покупателю: {e}")
            raise CustomerInvoiceParsingError(f"Ошибка парсинга счета покупателю: {e}")
    
    def _extract_archive(self, zip_path: str) -> str:
        """Извлечение ZIP архива"""
        extract_dir = os.path.join(Config.TEMP_DIR, "customer_invoice_extract")
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            logger.debug(f"Архив извлечен в: {extract_dir}")
            return extract_dir
            
        except zipfile.BadZipFile:
            raise CustomerInvoiceParsingError("Неверный формат ZIP файла")
    
    def _find_invoice_xml(self, extract_dir: str) -> str:
        """Поиск основного XML файла счета"""
        # Ищем XML файлы, исключая meta.xml и card.xml
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if (file.endswith('.xml') and 
                    file.lower() not in ['meta.xml', 'card.xml'] and
                    'schet' in file.lower()):
                    
                    full_path = os.path.join(root, file)
                    logger.debug(f"Найден XML файл счета: {file}")
                    return full_path
        
        raise CustomerInvoiceParsingError("XML файл счета не найден в архиве")
    
    def _parse_invoice_xml(self, xml_path: str) -> CustomerInvoiceDocument:
        """Парсинг основного XML файла счета в формате CommerceML"""
        try:
            with open(xml_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            tree = ET.fromstring(content)
            
            # Namespace для CommerceML
            ns = {'cm': 'urn:1C.ru:commerceml_2'}
            
            # Находим документ
            doc = tree.find('.//cm:Документ', ns)
            if doc is None:
                raise CustomerInvoiceParsingError("Элемент Документ не найден в XML")
            
            # Извлекаем основную информацию
            invoice_number = self._get_text(doc.find('cm:Номер', ns))
            if not invoice_number:
                raise CustomerInvoiceParsingError("Номер счета не найден")
            
            date_str = self._get_text(doc.find('cm:Дата', ns))
            if not date_str:
                raise CustomerInvoiceParsingError("Дата счета не найдена")
            
            try:
                invoice_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise CustomerInvoiceParsingError(f"Неверный формат даты: {date_str}")
            
            total_sum_str = self._get_text(doc.find('cm:Сумма', ns))
            total_sum = Decimal(total_sum_str) if total_sum_str else Decimal('0')
            
            # Парсим контрагентов
            seller, buyer = self._parse_contractors(doc, ns)
            
            # Парсим товары
            items = self._parse_items(doc, ns, tree, total_sum)
            
            return CustomerInvoiceDocument(
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                seller=seller,
                buyer=buyer,
                items=items,
                total_sum=total_sum
            )
            
        except ET.ParseError as e:
            raise CustomerInvoiceParsingError(f"Ошибка парсинга XML: {e}")
    
    def _parse_contractors(self, doc: ET.Element, ns: dict) -> tuple[Organization, Organization]:
        """Парсинг контрагентов"""
        seller = None
        buyer = None
        
        contractors = doc.findall('.//cm:Контрагент', ns)
        for contractor in contractors:
            role = self._get_text(contractor.find('cm:Роль', ns))
            
            # Извлекаем ID контрагента (содержит ИНН_КПП)
            contractor_id = self._get_text(contractor.find('cm:Ид', ns))
            
            # Парсим ИНН и КПП из ID
            inn = None
            kpp = None
            if contractor_id and '_' in contractor_id:
                parts = contractor_id.split('_')
                inn = parts[0]
                kpp = parts[1] if len(parts) > 1 else None
            
            # Имя контрагента (пока не найдено в структуре, используем роль)
            name = self._get_text(contractor.find('cm:Наименование', ns)) or \
                   self._get_text(contractor.find('cm:ПолноеНаименование', ns)) or \
                   f"Контрагент ({role})"
            
            org = Organization(name=name, inn=inn or "0000000000", kpp=kpp)
            
            if role == "Продавец":
                seller = org
            elif role == "Покупатель":
                buyer = org
        
        if not seller:
            raise CustomerInvoiceParsingError("Продавец не найден в документе")
        if not buyer:
            raise CustomerInvoiceParsingError("Покупатель не найден в документе")
        
        return seller, buyer
    
    def _parse_items(self, doc: ET.Element, ns: dict, tree: ET.Element, total_sum: Decimal) -> List[InvoiceItem]:
        """Парсинг товарных позиций"""
        items = []
        
        # Сначала собираем информацию о товарах
        products = {}
        product_elements = tree.findall('.//cm:Товар', ns)
        
        for product in product_elements:
            product_name = self._get_text(product.find('cm:Наименование', ns))
            product_article = self._get_text(product.find('cm:Артикул', ns))
            
            # Ищем ID товара в реквизитах
            product_id = None
            requisites = product.find('cm:ЗначенияРеквизитов', ns)
            if requisites is not None:
                for req in requisites.findall('cm:ЗначениеРеквизита', ns):
                    req_name = self._get_text(req.find('cm:Наименование', ns))
                    req_value = self._get_text(req.find('cm:Значение', ns))
                    
                    if req_name == "Для1С_Идентификатор":
                        product_id = req_value.replace('##', '') if req_value else None
                        break
            
            # Если ID не найден в реквизитах, используем название как ключ
            if not product_id:
                product_id = product_name
            
            if product_id:
                products[product_id] = {
                    'name': product_name,
                    'article': product_article
                }
        
        logger.debug(f"Найдено товаров: {len(products)}")
        for pid, pinfo in products.items():
            logger.debug(f"  {pid}: {pinfo['name']} (артикул: {pinfo['article']})")
        
        # Теперь ищем табличную часть
        table_part = doc.find('cm:ТабличнаяЧасть', ns)
        if table_part is not None:
            logger.debug("Найдена табличная часть")
            rows = table_part.findall('cm:СтрокаТабличнойЧасти', ns)
            logger.debug(f"Найдено строк в табличной части: {len(rows)}")
            
            for i, row in enumerate(rows, 1):
                logger.debug(f"Обрабатываю строку {i}")
                
                product_id = self._get_text(row.find('cm:Товар', ns))
                quantity_str = self._get_text(row.find('cm:Количество', ns))
                price_str = self._get_text(row.find('cm:Цена', ns))
                sum_str = self._get_text(row.find('cm:Сумма', ns))
                vat_rate_str = self._get_text(row.find('cm:СтавкаНДС', ns))
                vat_sum_str = self._get_text(row.find('cm:СуммаНДС', ns))
                total_str = self._get_text(row.find('cm:Всего', ns))
                
                logger.debug(f"  Товар ID: {product_id}")
                logger.debug(f"  Количество: {quantity_str}")
                logger.debug(f"  Цена: {price_str}")
                logger.debug(f"  Сумма: {sum_str}")
                
                # Получаем информацию о товаре
                product_info = products.get(product_id, {})
                product_name = product_info.get('name', f'Товар {i}')
                product_article = product_info.get('article')
                
                # Преобразуем в числа
                quantity = Decimal(quantity_str) if quantity_str else Decimal('1')
                price = Decimal(price_str) if price_str else Decimal('0')
                amount_without_vat = Decimal(sum_str) if sum_str else Decimal('0')
                vat_amount = Decimal(vat_sum_str) if vat_sum_str else Decimal('0')
                amount_with_vat = Decimal(total_str) if total_str else amount_without_vat + vat_amount
                
                item = InvoiceItem(
                    line_number=i,
                    name=product_name,
                    quantity=quantity,
                    price=price,
                    amount_without_vat=amount_without_vat,
                    vat_rate=vat_rate_str,
                    vat_amount=vat_amount,
                    amount_with_vat=amount_with_vat,
                    article=product_article
                )
                
                items.append(item)
                logger.debug(f"Позиция {i}: {product_name}, артикул: {product_article}, количество: {quantity}")
        else:
            logger.debug("Табличная часть не найдена")
        
        # Если табличная часть не найдена или пуста, создаем позиции из товаров
        if not items and products:
            logger.warning("Табличная часть не найдена или пуста, создаю позиции из списка товаров")
            
            # Пытаемся извлечь количество и цену из общей суммы
            price_per_item = total_sum / len(products) if products else Decimal('0')
            
            for i, (product_id, product_info) in enumerate(products.items(), 1):
                item = InvoiceItem(
                    line_number=i,
                    name=product_info.get('name', f'Товар {i}'),
                    quantity=Decimal('1'),
                    price=price_per_item,
                    amount_without_vat=price_per_item,
                    vat_rate="20%",
                    vat_amount=price_per_item * Decimal('0.2'),
                    amount_with_vat=price_per_item * Decimal('1.2'),
                    article=product_info.get('article')
                )
                items.append(item)
        
        logger.info(f"Распарсено позиций: {len(items)}")
        return items
    
    def _get_text(self, element: Optional[ET.Element]) -> Optional[str]:
        """Безопасное извлечение текста из элемента"""
        return element.text.strip() if element is not None and element.text else None
    
    def cleanup_temp_files(self, zip_path: str):
        """Очистка временных файлов"""
        try:
            # Удаляем исходный ZIP файл
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            # Удаляем извлеченные файлы
            extract_dir = os.path.join(Config.TEMP_DIR, "customer_invoice_extract")
            if os.path.exists(extract_dir):
                import shutil
                shutil.rmtree(extract_dir)
                
            logger.debug("Временные файлы счета покупателю очищены")
            
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов счета покупателю: {e}")