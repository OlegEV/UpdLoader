"""
Базовый класс для парсеров документов
"""
import os
import zipfile
import shutil
from typing import Optional
from xml.etree import ElementTree as ET

from loguru import logger

from src.config import Config


class BaseDocumentParser:
    """Базовый класс для парсеров документов"""
    
    def __init__(self):
        self.encoding = Config.UPD_ENCODING
    
    def _extract_archive(self, zip_path: str, extract_dir_name: str) -> str:
        """
        Извлечение ZIP архива
        
        Args:
            zip_path: Путь к ZIP архиву
            extract_dir_name: Имя директории для извлечения
            
        Returns:
            str: Путь к извлеченной директории
        """
        extract_dir = os.path.join(Config.TEMP_DIR, extract_dir_name)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            logger.debug(f"Архив извлечен в: {extract_dir}")
            return extract_dir
            
        except zipfile.BadZipFile:
            raise Exception("Неверный формат ZIP файла")
    
    def _get_text(self, element: Optional[ET.Element]) -> Optional[str]:
        """
        Безопасное извлечение текста из элемента XML
        
        Args:
            element: XML элемент
            
        Returns:
            Optional[str]: Текст элемента или None
        """
        return element.text.strip() if element is not None and element.text else None
    
    def cleanup_temp_files(self, zip_path: str, extract_dir_name: str):
        """
        Очистка временных файлов
        
        Args:
            zip_path: Путь к ZIP файлу
            extract_dir_name: Имя директории для очистки
        """
        try:
            # Удаляем исходный ZIP файл
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            # Удаляем извлеченные файлы
            extract_dir = os.path.join(Config.TEMP_DIR, extract_dir_name)
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
                
            logger.debug(f"Временные файлы очищены: {extract_dir_name}")
            
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов {extract_dir_name}: {e}")
    
    def _find_xml_element_with_fallback(self, tree: ET.Element, 
                                       paths: list, 
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
