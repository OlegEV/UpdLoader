"""
Парсер УПД документов
"""
import os
from datetime import datetime
from decimal import Decimal
from typing import Optional
from xml.etree import ElementTree as ET

from loguru import logger

from .config import Config
from .models import (
    UPDDocument, UPDContent, MetaInfo, CardInfo,
    InvoiceItem, Organization, Address
)
from .parsers.base_parser import BaseDocumentParser
from .utils.xml_utils import safe_get_text, find_xml_element_with_fallback, parse_organization_from_xml


class UPDParsingError(Exception):
    """Ошибка парсинга УПД"""
    pass


class UPDParser(BaseDocumentParser):
    """Парсер УПД документов"""
    
    def parse_upd_archive(self, zip_path: str) -> UPDDocument:
        """
        Основной метод парсинга УПД архива
        
        Args:
            zip_path: Путь к ZIP архиву с УПД
            
        Returns:
            UPDDocument: Распарсенный УПД документ
            
        Raises:
            UPDParsingError: Ошибка парсинга
        """
        try:
            logger.info(f"Начинаю парсинг УПД архива: {zip_path}")
            
            # Извлекаем архив
            extract_dir = self._extract_archive(zip_path)
            
            # Парсим meta.xml
            meta_info = self._parse_meta_xml(extract_dir)
            
            # Парсим card.xml
            card_info = self._parse_card_xml(extract_dir, meta_info.card_path)
            
            # Парсим основной УПД документ
            content = self._parse_upd_content(extract_dir, meta_info.main_document_path)
            
            upd_document = UPDDocument(
                meta_info=meta_info,
                card_info=card_info,
                content=content
            )
            
            logger.info(f"УПД успешно распарсен: {upd_document.document_id}")
            return upd_document
            
        except Exception as e:
            logger.error(f"Ошибка парсинга УПД: {e}")
            raise UPDParsingError(f"Ошибка парсинга УПД: {e}")
    
    def _extract_archive(self, zip_path: str) -> str:
        """Извлечение ZIP архива"""
        return super()._extract_archive(zip_path, "upd_extract")
    
    def _parse_meta_xml(self, extract_dir: str) -> MetaInfo:
        """Парсинг meta.xml"""
        meta_path = os.path.join(extract_dir, "meta.xml")
        
        if not os.path.exists(meta_path):
            raise UPDParsingError("Файл meta.xml не найден в архиве")
        
        try:
            tree = ET.parse(meta_path)
            root = tree.getroot()
            
            # Находим DocFlow
            doc_flow = root.find(".//{http://api-invoice.taxcom.ru/meta}DocFlow")
            if doc_flow is None:
                raise UPDParsingError("Элемент DocFlow не найден в meta.xml")
            
            doc_flow_id = doc_flow.get("Id")
            if not doc_flow_id:
                raise UPDParsingError("Атрибут Id не найден в DocFlow")
            
            # Находим пути к файлам
            main_image = root.find(".//{http://api-invoice.taxcom.ru/meta}MainImage")
            external_card = root.find(".//{http://api-invoice.taxcom.ru/meta}ExternalCard")
            
            if main_image is None:
                raise UPDParsingError("Элемент MainImage не найден в meta.xml")
            if external_card is None:
                raise UPDParsingError("Элемент ExternalCard не найден в meta.xml")
            
            main_document_path = main_image.get("Path")
            card_path = external_card.get("Path")
            
            if not main_document_path or not card_path:
                raise UPDParsingError("Пути к файлам не найдены в meta.xml")
            
            return MetaInfo(
                doc_flow_id=doc_flow_id,
                main_document_path=main_document_path,
                card_path=card_path
            )
            
        except ET.ParseError as e:
            raise UPDParsingError(f"Ошибка парсинга meta.xml: {e}")
    
    def _parse_card_xml(self, extract_dir: str, card_path: str) -> CardInfo:
        """Парсинг card.xml"""
        full_card_path = os.path.join(extract_dir, card_path)
        
        if not os.path.exists(full_card_path):
            raise UPDParsingError(f"Файл card.xml не найден: {card_path}")
        
        try:
            with open(full_card_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            tree = ET.fromstring(content)
            
            # Извлекаем основную информацию
            identifiers = tree.find(".//{http://api-invoice.taxcom.ru/card}Identifiers")
            description = tree.find(".//{http://api-invoice.taxcom.ru/card}Description")
            sender = tree.find(".//{http://api-invoice.taxcom.ru/card}Sender")
            
            external_identifier = identifiers.get("ExternalIdentifier") if identifiers is not None else ""
            title = description.get("Title") if description is not None else ""
            date_str = description.get("Date") if description is not None else ""
            
            # Парсим дату
            try:
                date = datetime.fromisoformat(date_str.replace('T', ' ').replace('Z', ''))
            except:
                date = datetime.now()
            
            # Информация об отправителе
            sender_inn = None
            sender_kpp = None
            sender_name = None
            
            if sender is not None:
                abonent = sender.find(".//{http://api-invoice.taxcom.ru/card}Abonent")
                if abonent is not None:
                    sender_inn = abonent.get("Inn")
                    sender_kpp = abonent.get("Kpp")
                    sender_name = abonent.get("Name")
            
            return CardInfo(
                external_identifier=external_identifier,
                title=title,
                date=date,
                sender_inn=sender_inn,
                sender_kpp=sender_kpp,
                sender_name=sender_name
            )
            
        except ET.ParseError as e:
            raise UPDParsingError(f"Ошибка парсинга card.xml: {e}")
    
    def _parse_upd_content(self, extract_dir: str, main_document_path: str) -> UPDContent:
        """Парсинг основного УПД документа"""
        full_upd_path = os.path.join(extract_dir, main_document_path)
        
        if not os.path.exists(full_upd_path):
            raise UPDParsingError(f"Основной УПД файл не найден: {main_document_path}")
        
        try:
            with open(full_upd_path, 'r', encoding=self.encoding) as f:
                content = f.read()
            
            # Если файл содержит только заголовок XML, создаем базовую структуру
            if len(content.strip()) <= 100:  # Только XML заголовок
                logger.warning("УПД файл содержит только XML заголовок, создаю базовую структуру")
                return self._create_basic_upd_content()
            
            tree = ET.fromstring(content)
            
            # Парсим основные элементы УПД
            return self._parse_full_upd_content(tree)
            
        except ET.ParseError as e:
            logger.warning(f"Ошибка парсинга основного УПД файла: {e}, создаю базовую структуру")
            return self._create_basic_upd_content()
    
    def _create_basic_upd_content(self) -> UPDContent:
        """Создание базовой структуры УПД при отсутствии полных данных"""
        return UPDContent(
            invoice_number="Не указан",
            invoice_date=datetime.now(),
            currency_code="643",
            seller=Organization(
                name="Не указано",
                inn="0000000000"
            ),
            buyer=Organization(
                name="Не указано", 
                inn="0000000000"
            ),
            items=[],
            total_without_vat=Decimal('0'),
            total_vat=Decimal('0'),
            total_with_vat=Decimal('0')
        )
    
    def _parse_full_upd_content(self, tree: ET.Element) -> UPDContent:
        """Парсинг полного содержимого УПД"""
        try:
            logger.info("Парсинг полного УПД документа...")
            
            # Проверяем версию формата УПД
            version = tree.get('ВерсФорм')
            if version:
                logger.info(f"Обнаружена версия формата УПД: {version}")
                if version == "5.03":
                    logger.info("Используем парсинг для УПД 5.03")
                else:
                    logger.warning(f"Неожиданная версия УПД: {version}, используем универсальный парсинг")
            
            # Отладочная информация о структуре XML
            logger.debug(f"Корневой элемент: {tree.tag}")
            logger.debug(f"Атрибуты корневого элемента: {tree.attrib}")
            
            # Выводим первые несколько дочерних элементов
            for i, child in enumerate(tree):
                if i < 5:  # Первые 5 элементов
                    logger.debug(f"Дочерний элемент {i}: {child.tag}, атрибуты: {child.attrib}")
            
            # Попробуем разные пространства имен
            possible_namespaces = [
                {'ns': 'urn:cbr-ru:ed:v2.0'},
                {'ns': 'http://www.w3.org/2001/XMLSchema-instance'},
                {'ns': ''},  # Без пространства имен
                {}  # Пустой словарь
            ]
            
            # Ищем основные элементы УПД с разными пространствами имен
            namespaces = None
            for ns in possible_namespaces:
                logger.debug(f"Пробую пространство имен: {ns}")
                
                # Пробуем найти элементы с текущим пространством имен
                if ns:
                    invoice_info = tree.find(".//ns:СвСчФакт", ns) or tree.find(".//СвСчФакт")
                    seller_info = tree.find(".//ns:СвПрод", ns) or tree.find(".//СвПрод")
                else:
                    invoice_info = tree.find(".//СвСчФакт")
                    seller_info = tree.find(".//СвПрод")
                
                if invoice_info is not None or seller_info is not None:
                    logger.info(f"Найдены элементы с пространством имен: {ns}")
                    namespaces = ns
                    break
            
            if namespaces is None:
                logger.warning("Не удалось найти подходящее пространство имен, пробую без него")
                namespaces = {}
            
            # Ищем сведения о счете-фактуре для УПД 5.03
            invoice_info = None
            if namespaces:
                invoice_info = tree.find(".//ns:СвСчФакт", namespaces)
            if invoice_info is None:
                invoice_info = tree.find(".//СвСчФакт")
            
            invoice_number = "Не указан"
            invoice_date = datetime.now()
            requisite_number = None  # Номер счета из реквизитов
            
            if invoice_info is not None:
                # В УПД 5.03 номер и дата могут быть в атрибутах СвСчФакт
                invoice_number = invoice_info.get("НомерДок") or "Не указан"
                date_str = invoice_info.get("ДатаДок")
                
                if date_str:
                    try:
                        # Формат даты в УПД 5.03: ДД.ММ.ГГГГ
                        invoice_date = datetime.strptime(date_str, "%d.%m.%Y")
                    except:
                        try:
                            # Альтернативный формат: ГГГГ-ММ-ДД
                            invoice_date = datetime.strptime(date_str, "%Y-%m-%d")
                        except:
                            invoice_date = datetime.now()
                
            # Ищем реквизит РеквНомерДок в элементе ОснПер (СвПродПер/СвПер/ОснПер)
            # Поиск выносим за пределы блока invoice_info, так как ОснПер находится в другой части документа
            osn_per_elem = None
            if namespaces:
                osn_per_elem = tree.find(".//ns:СвПродПер/ns:СвПер/ns:ОснПер", namespaces)
            if osn_per_elem is None:
                osn_per_elem = tree.find(".//СвПродПер/СвПер/ОснПер")
            
            # Fallback: ищем ОснПер напрямую
            if osn_per_elem is None:
                if namespaces:
                    osn_per_elem = tree.find(".//ns:ОснПер", namespaces)
                if osn_per_elem is None:
                    osn_per_elem = tree.find(".//ОснПер")
            
            if osn_per_elem is not None:
                requisite_doc_number = osn_per_elem.get("РеквНомерДок")
                if requisite_doc_number:
                    logger.debug(f"Найден РеквНомерДок: {requisite_doc_number}")
                    
                    # Извлекаем только цифры из РеквНомерДок (убираем "счет" и другие префиксы)
                    import re
                    numbers = re.findall(r'\d+', requisite_doc_number)
                    if numbers:
                        requisite_number = numbers[0]  # Берем первое найденное число
                        logger.debug(f"Номер счета из реквизитов (только цифры): {requisite_number}")
                    else:
                        requisite_number = requisite_doc_number.strip()
                        logger.debug(f"Номер счета из реквизитов (как есть): {requisite_number}")
                else:
                    logger.debug("Атрибут РеквНомерДок не найден в ОснПер")
            else:
                logger.debug("Элемент ОснПер не найден")
                
                # Fallback: ищем в дочерних элементах
                if invoice_number == "Не указан":
                    number_elem = None
                    if namespaces:
                        number_elem = invoice_info.find("ns:НомерСчФ", namespaces) or invoice_info.find("ns:НомерДок", namespaces)
                    if number_elem is None:
                        number_elem = invoice_info.find("НомерСчФ") or invoice_info.find("НомерДок")
                    
                    if number_elem is not None:
                        invoice_number = number_elem.text or "Не указан"
                
                if date_str is None:
                    date_elem = None
                    if namespaces:
                        date_elem = invoice_info.find("ns:ДатаСчФ", namespaces) or invoice_info.find("ns:ДатаДок", namespaces)
                    if date_elem is None:
                        date_elem = invoice_info.find("ДатаСчФ") or invoice_info.find("ДатаДок")
                    
                    if date_elem is not None:
                        try:
                            invoice_date = datetime.strptime(date_elem.text, "%d.%m.%Y")
                        except:
                            try:
                                invoice_date = datetime.strptime(date_elem.text, "%Y-%m-%d")
                            except:
                                invoice_date = datetime.now()
            
            # Если не нашли стандартные элементы, попробуем найти любые элементы с ИНН
            if invoice_number == "Не указан":
                # Ищем любые элементы, которые могут содержать номер
                for elem in tree.iter():
                    if elem.tag and ('номер' in elem.tag.lower() or 'number' in elem.tag.lower()):
                        if elem.text:
                            invoice_number = elem.text
                            logger.debug(f"Найден номер в элементе {elem.tag}: {invoice_number}")
                            break
            
            # Парсим информацию о продавце (поставщике)
            seller = self._parse_seller_info(tree, namespaces)
            
            # Парсим информацию о покупателе
            buyer = self._parse_buyer_info(tree, namespaces)
            
            # Парсим позиции
            items = self._parse_invoice_items(tree, namespaces)
            
            # Парсим итоговые суммы
            totals = self._parse_totals(tree, namespaces)
            
            logger.info(f"УПД распарсен: № {invoice_number}, поставщик ИНН {seller.inn}, покупатель ИНН {buyer.inn}")
            
            return UPDContent(
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                seller=seller,
                buyer=buyer,
                items=items,
                total_without_vat=totals.get('without_vat', Decimal('0')),
                total_vat=totals.get('vat', Decimal('0')),
                total_with_vat=totals.get('with_vat', Decimal('0')),
                requisite_number=requisite_number
            )
            
        except Exception as e:
            logger.error(f"Ошибка парсинга полного УПД: {e}")
            logger.warning("Возвращаю базовую структуру УПД")
            return self._create_basic_upd_content()
    
    def cleanup_temp_files(self, zip_path: str):
        """Очистка временных файлов"""
        super().cleanup_temp_files(zip_path, "upd_extract")
    
    def _parse_seller_info(self, tree: ET.Element, namespaces: dict) -> Organization:
        """Парсинг информации о продавце (поставщике) для УПД 5.03"""
        try:
            # В УПД 5.03 продавец находится в СвПрод
            seller_elem = None
            if namespaces:
                seller_elem = tree.find(".//ns:СвПрод", namespaces)
            if seller_elem is None:
                seller_elem = tree.find(".//СвПрод")
            
            if seller_elem is None:
                logger.warning("Элемент СвПрод не найден")
                raise UPDParsingError("Не удалось определить продавца в УПД документе")
            
            return parse_organization_from_xml(seller_elem, namespaces, "продавца")
            
        except UPDParsingError:
            # Пробрасываем ошибки парсинга дальше
            raise
        except Exception as e:
            logger.error(f"Ошибка парсинга информации о продавце: {e}")
            raise UPDParsingError(f"Ошибка парсинга информации о продавце: {e}")
    
    def _parse_buyer_info(self, tree: ET.Element, namespaces: dict) -> Organization:
        """Парсинг информации о покупателе (грузополучателе) для УПД 5.03"""
        try:
            # В УПД 5.03 покупатель (грузополучатель) находится в ГрузПолуч
            buyer_elem = None
            if namespaces:
                buyer_elem = tree.find(".//ns:ГрузПолуч", namespaces)
            if buyer_elem is None:
                buyer_elem = tree.find(".//ГрузПолуч")
            
            # Если не найден ГрузПолуч, пробуем СвПокуп (fallback)
            if buyer_elem is None:
                if namespaces:
                    buyer_elem = tree.find(".//ns:СвПокуп", namespaces)
                if buyer_elem is None:
                    buyer_elem = tree.find(".//СвПокуп")
            
            if buyer_elem is None:
                logger.warning("Элементы ГрузПолуч и СвПокуп не найдены")
                raise UPDParsingError("Не удалось определить покупателя в УПД документе")
            
            return parse_organization_from_xml(buyer_elem, namespaces, "покупателя")
            
        except UPDParsingError:
            # Пробрасываем ошибки парсинга дальше
            raise
        except Exception as e:
            logger.error(f"Ошибка парсинга информации о покупателе: {e}")
            raise UPDParsingError(f"Ошибка парсинга информации о покупателе: {e}")
    
    def _parse_invoice_items(self, tree: ET.Element, namespaces: dict) -> list:
        """Парсинг позиций счета-фактуры"""
        items = []
        try:
            # Ищем табличную часть
            table_elem = None
            if namespaces:
                table_elem = tree.find(".//ns:ТаблСчФакт", namespaces)
            if table_elem is None:
                table_elem = tree.find(".//ТаблСчФакт")
            
            if table_elem is None:
                logger.warning("Элемент ТаблСчФакт не найден")
                return items
            
            # Ищем все позиции товаров
            item_elements = []
            if namespaces:
                item_elements = table_elem.findall("ns:СведТов", namespaces)
            if not item_elements:
                item_elements = table_elem.findall("СведТов")
            
            for i, item_elem in enumerate(item_elements, 1):
                try:
                    # Извлекаем данные позиции из атрибутов
                    name = item_elem.get("НаимТов") or f"Товар {i}"
                    quantity_str = item_elem.get("КолТов") or "1"
                    price_str = item_elem.get("ЦенаТов") or "0"
                    amount_str = item_elem.get("СтТовБезНДС") or "0"
                    vat_rate = item_elem.get("НалСт") or "20%"
                    total_str = item_elem.get("СтТовУчНал") or "0"
                    
                    # Ищем артикул в ДопСведТов/КодТов
                    article = None
                    dop_sved_elem = None
                    if namespaces:
                        dop_sved_elem = item_elem.find("ns:ДопСведТов", namespaces)
                    if dop_sved_elem is None:
                        dop_sved_elem = item_elem.find("ДопСведТов")
                    
                    if dop_sved_elem is not None:
                        article = dop_sved_elem.get("КодТов")
                        logger.debug(f"Найден артикул: {article}")
                    
                    # Ищем НДС в СумНал
                    vat_amount = Decimal('0')
                    sum_nal_elem = None
                    if namespaces:
                        sum_nal_elem = item_elem.find(".//ns:СумНал/ns:СумНал", namespaces)
                    if sum_nal_elem is None:
                        sum_nal_elem = item_elem.find(".//СумНал/СумНал")
                    
                    if sum_nal_elem is not None:
                        vat_amount = Decimal(sum_nal_elem.text or '0')
                    
                    # Преобразуем в числа
                    quantity = Decimal(quantity_str)
                    price = Decimal(price_str)
                    amount_without_vat = Decimal(amount_str)
                    amount_with_vat = Decimal(total_str)
                    
                    # ИСПРАВЛЕНИЕ: Используем СтТовУчНал (сумма с НДС) как основную сумму товара
                    # так как она включает НДС и должна использоваться в МойСклад
                    main_amount = amount_with_vat  # Основная сумма = сумма с НДС
                    
                    item = InvoiceItem(
                        line_number=i,
                        name=name,
                        quantity=quantity,
                        price=price,
                        amount_without_vat=main_amount,  # Используем сумму с НДС как основную
                        vat_rate=vat_rate,
                        vat_amount=vat_amount,
                        amount_with_vat=amount_with_vat,
                        article=article  # Добавляем артикул
                    )
                    
                    items.append(item)
                    logger.debug(f"Позиция {i}: {name}, артикул: {article}, количество: {quantity}, цена: {price}, сумма с НДС: {main_amount}")
                    
                except Exception as e:
                    logger.error(f"Ошибка парсинга позиции {i}: {e}")
                    continue
            
            logger.info(f"Распарсено позиций: {len(items)}")
            return items
            
        except Exception as e:
            logger.error(f"Ошибка парсинга позиций: {e}")
            return items
    
    def _parse_totals(self, tree: ET.Element, namespaces: dict) -> dict:
        """Парсинг итоговых сумм"""
        try:
            totals_elem = tree.find(".//ns:ВсегоОпл", namespaces)
            if totals_elem is None:
                logger.warning("Элемент ВсегоОпл не найден")
                return {'without_vat': Decimal('0'), 'vat': Decimal('0'), 'with_vat': Decimal('0')}
            
            # Извлекаем суммы
            without_vat_elem = totals_elem.find("ns:СтТовБезНДСВсего", namespaces)
            with_vat_elem = totals_elem.find("ns:СтТовУчНалВсего", namespaces)
            vat_sum_elem = totals_elem.find(".//ns:СумНал", namespaces)
            
            without_vat = Decimal(without_vat_elem.text) if without_vat_elem is not None else Decimal('0')
            with_vat = Decimal(with_vat_elem.text) if with_vat_elem is not None else Decimal('0')
            vat = Decimal(vat_sum_elem.text) if vat_sum_elem is not None else Decimal('0')
            
            logger.debug(f"Итоги: без НДС {without_vat}, НДС {vat}, с НДС {with_vat}")
            
            return {
                'without_vat': without_vat,
                'vat': vat,
                'with_vat': with_vat
            }
            
        except Exception as e:
            logger.error(f"Ошибка парсинга итогов: {e}")
            return {'without_vat': Decimal('0'), 'vat': Decimal('0'), 'with_vat': Decimal('0')}