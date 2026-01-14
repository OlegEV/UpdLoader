"""
Утилиты для работы с XML
"""
from typing import Optional, List
from xml.etree import ElementTree as ET

from loguru import logger

from src.models import Organization


def safe_get_text(element: Optional[ET.Element]) -> Optional[str]:
    """
    Безопасное извлечение текста из элемента XML
    
    Args:
        element: XML элемент
        
    Returns:
        Optional[str]: Текст элемента или None
    """
    return element.text.strip() if element is not None and element.text else None


def find_xml_element_with_fallback(tree: ET.Element, 
                                   paths: List[str], 
                                   namespaces: dict = None) -> Optional[ET.Element]:
    """
    Поиск XML элемента с несколькими путями для fallback
    
    Args:
        tree: XML дерево
        paths: Список путей для поиска
        namespaces: Пространства имен XML
        
    Returns:
        Optional[ET.Element]: Найденный элемент или None
    """
    for path in paths:
        if namespaces:
            element = tree.find(path, namespaces)
        else:
            element = tree.find(path)
        
        if element is not None:
            return element
    
    return None


def parse_organization_from_xml(org_elem: ET.Element, 
                             namespaces: dict,
                             role: str = None) -> Organization:
    """
    Парсинг организации из XML элемента
    
    Args:
        org_elem: XML элемент организации
        namespaces: Пространства имен XML
        role: Роль организации (для логирования)
        
    Returns:
        Organization: Объект организации
    """
    # Сначала пробуем найти юридическое лицо (СвЮЛУч)
    legal_entity = None
    if namespaces:
        legal_entity = org_elem.find(".//ns:ИдСв/ns:СвЮЛУч", namespaces)
    if legal_entity is None:
        legal_entity = org_elem.find(".//ИдСв/СвЮЛУч")
    
    # Fallback: ищем СвЮЛУч напрямую
    if legal_entity is None:
        if namespaces:
            legal_entity = org_elem.find(".//ns:СвЮЛУч", namespaces)
        if legal_entity is None:
            legal_entity = org_elem.find(".//СвЮЛУч")
    
    # Если найдено юридическое лицо, парсим его данные
    if legal_entity is not None:
        logger.debug(f"Найдено юридическое лицо {role or 'организации'}")
        
        # Данные находятся в атрибутах элемента СвЮЛУч
        name = legal_entity.get("НаимОрг") or "Не указано"
        inn = legal_entity.get("ИННЮЛ") or None
        kpp = legal_entity.get("КПП")
        
        # Fallback: если в атрибутах нет данных, ищем в дочерних элементах
        if name == "Не указано" or inn is None:
            name_elem = None
            inn_elem = None
            kpp_elem = None
            
            if namespaces:
                name_elem = legal_entity.find("ns:НаимОрг", namespaces)
                inn_elem = legal_entity.find("ns:ИННЮЛ", namespaces)
                kpp_elem = legal_entity.find("ns:КПП", namespaces)
            
            if name_elem is None:
                name_elem = legal_entity.find("НаимОрг")
            if inn_elem is None:
                inn_elem = legal_entity.find("ИННЮЛ")
            if kpp_elem is None:
                kpp_elem = legal_entity.find("КПП")
            
            if name == "Не указано" and name_elem is not None:
                name = name_elem.text or "Не указано"
            if inn is None and inn_elem is not None:
                inn = inn_elem.text
            if kpp is None and kpp_elem is not None:
                kpp = kpp_elem.text
        
        # Если ИНН найден для юридического лица, возвращаем результат
        if inn:
            logger.debug(f"{role or 'Организация'} (юридическое лицо): {name}, ИНН: {inn}, КПП: {kpp}")
            return Organization(name=name, inn=inn, kpp=kpp)
        else:
            logger.debug("ИНН для юридического лица не найден, ищем индивидуального предпринимателя")
    
    # Если юридическое лицо не найдено или у него нет ИНН, ищем индивидуального предпринимателя (СвИП)
    individual_entity = None
    if namespaces:
        individual_entity = org_elem.find(".//ns:ИдСв/ns:СвИП", namespaces)
    if individual_entity is None:
        individual_entity = org_elem.find(".//ИдСв/СвИП")
    
    # Fallback: ищем СвИП напрямую
    if individual_entity is None:
        if namespaces:
            individual_entity = org_elem.find(".//ns:СвИП", namespaces)
        if individual_entity is None:
            individual_entity = org_elem.find(".//СвИП")
    
    # Если найден индивидуальный предприниматель, парсим его данные
    if individual_entity is not None:
        logger.debug(f"Найден индивидуальный предприниматель {role or 'организации'}")
        
        # Для ИП ИНН находится в атрибуте ИННФЛ
        inn_fl = individual_entity.get("ИННФЛ")
        
        # Ищем ФИО в дочернем элементе ФИО
        fio_elem = None
        if namespaces:
            fio_elem = individual_entity.find("ns:ФИО", namespaces)
        if fio_elem is None:
            fio_elem = individual_entity.find("ФИО")
        
        # Формируем имя из ФИО
        name = "Не указано"
        if fio_elem is not None:
            surname = fio_elem.get("Фамилия") or ""
            first_name = fio_elem.get("Имя") or ""
            patronymic = fio_elem.get("Отчество") or ""
            
            # Собираем полное имя
            name_parts = [surname, first_name, patronymic]
            name = " ".join(part for part in name_parts if part)
            if not name:
                name = "Не указано"
        
        # Если ИНН найден для ИП, возвращаем результат
        if inn_fl:
            logger.debug(f"{role or 'Организация'} (индивидуальный предприниматель): {name}, ИНН: {inn_fl}")
            return Organization(name=name, inn=inn_fl, kpp=None)
        else:
            logger.debug("ИННФЛ для индивидуального предпринимателя не найден")
    
    # Если не удалось найти ни юридическое лицо, ни ИП с ИНН
    logger.error(f"Не удалось определить ИНН {role or 'организации'} (ни для юридического лица, ни для ИП)")
    raise Exception(f"Не удалось определить ИНН {role or 'организации'} в документе. Проверьте корректность документа.")
