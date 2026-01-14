"""
Утилиты проекта
"""
from .xml_utils import safe_get_text, find_xml_element_with_fallback
from .product_utils import determine_product_group, count_products_by_group

__all__ = [
    'safe_get_text',
    'find_xml_element_with_fallback',
    'determine_product_group',
    'count_products_by_group'
]
