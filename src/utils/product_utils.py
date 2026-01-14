"""
Утилиты для работы с товарами
"""
from typing import List, Dict, Optional

from loguru import logger

from src.models import InvoiceItem


def determine_product_group(product_name: str, 
                       product_article: Optional[str] = None) -> str:
    """
    Определение группы товара по названию и артикулу
    
    Args:
        product_name: Название товара
        product_article: Артикул товара
        
    Returns:
        str: Группа товара ("трубы" или "профиль")
    """
    # Приводим к нижнему регистру для поиска
    name_lower = product_name.lower() if product_name else ""
    article_lower = product_article.lower() if product_article else ""
    
    # Ключевые слова для определения группы "трубы"
    tube_keywords = ["труба", "трубы", "трубка", "трубный", "трубопровод"]
    
    # Ключевые слова для определения группы "профиль"
    profile_keywords = ["профиль", "профили", "профильный", "профилированный"]
    
    # Проверяем название товара
    for keyword in tube_keywords:
        if keyword in name_lower:
            return "трубы"
    
    for keyword in profile_keywords:
        if keyword in name_lower:
            return "профиль"
    
    # Проверяем артикул
    for keyword in tube_keywords:
        if keyword in article_lower:
            return "трубы"
    
    for keyword in profile_keywords:
        if keyword in article_lower:
            return "профиль"
    
    # По умолчанию возвращаем "профиль"
    return "профиль"


def count_products_by_group(items: List[InvoiceItem], 
                           moysklad_api) -> Dict[str, int]:
    """
    Подсчет товаров по группам на основе данных из МойСклад
    
    Args:
        items: Список товаров
        moysklad_api: Экземпляр MoySkladAPI
        
    Returns:
        Dict[str, int]: Словарь с количеством товаров по группам
    """
    profile_count = 0
    tube_count = 0
    
    for item in items:
        # Сначала ищем товар в МойСклад
        product = None
        if item.article:
            logger.debug(f"Ищем товар по артикулу: {item.article}")
            product = moysklad_api._find_product_by_article(item.article)
        
        # Если не найден по артикулу, ищем по названию
        if not product:
            logger.debug(f"Ищем товар по названию: {item.name}")
            product = moysklad_api._find_product(item.name)
        
        if product:
            # Получаем группу товара из МойСклад
            group_name = moysklad_api._get_product_group_name(product)
            logger.debug(f"Товар '{item.name}' принадлежит группе: {group_name}")
            
            # Определяем группу на основе названия группы из МойСклад
            if group_name and 'профиль' in group_name.lower():
                profile_count += 1
                logger.debug(f"Товар '{item.name}' отнесен к группе профилей")
            elif group_name and 'труб' in group_name.lower():
                tube_count += 1
                logger.debug(f"Товар '{item.name}' отнесен к группе труб")
            else:
                # Если группа не определена, используем старую логику по названию товара
                logger.debug(f"Группа товара '{item.name}' не определена, используем анализ названия")
                item_name = item.name.lower()
                if 'профиль' in item_name:
                    profile_count += 1
                elif 'труб' in item_name:
                    tube_count += 1
        else:
            # Если товар не найден в МойСклад, используем старую логику
            logger.warning(f"Товар '{item.name}' не найден в МойСклад, используем анализ названия")
            item_name = item.name.lower()
            if 'профиль' in item_name:
                profile_count += 1
            elif 'труб' in item_name:
                tube_count += 1
    
    return {
        'profile': profile_count,
        'tube': tube_count
    }


def get_warehouse_and_project_for_group(product_group: str) -> tuple[str, str]:
    """
    Получение склада и проекта для группы товара
    
    Args:
        product_group: Группа товара ("трубы" или "профиль")
        
    Returns:
        tuple[str, str]: (название_склада, название_проекта)
    """
    if product_group == "трубы":
        return "Сестрорецк, ПП", "Трубы"
    elif product_group == "профиль":
        return "Гатчина", "профили"
    else:
        # По умолчанию
        return "Гатчина", "профили"
