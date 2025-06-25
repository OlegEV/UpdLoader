"""
Интеграция с МойСклад API
"""
import requests
import time
from typing import Dict, Optional, List
from loguru import logger

from .config import Config
from .models import UPDDocument, UPDContent, Organization


class MoySkladAPIError(Exception):
    """Ошибка МойСклад API"""
    pass


class MoySkladAPI:
    """Клиент для работы с МойСклад API"""
    
    def __init__(self):
        self.base_url = Config.MOYSKLAD_API_URL
        # МойСклад API требует точно такие заголовки с charset=utf-8
        self.headers = {
            "Authorization": f"Bearer {Config.MOYSKLAD_API_TOKEN}",
            "Content-Type": "application/json;charset=utf-8",
            "Accept": "application/json;charset=utf-8"
        }
        self.organization_id = Config.MOYSKLAD_ORGANIZATION_ID
    
    def _log_request(self, method: str, url: str, response: requests.Response,
                     duration_ms: float, request_data: Optional[Dict] = None):
        """Логирование HTTP запросов к МойСклад API"""
        # Маскируем токен в заголовках для безопасности
        safe_headers = {k: v if k != 'Authorization' else 'Bearer ***' for k, v in self.headers.items()}
        
        log_data = {
            "method": method,
            "url": url.replace(self.base_url, ""),  # Убираем базовый URL для краткости
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "headers": safe_headers
        }
        
        # Добавляем данные запроса для POST/PUT
        if request_data and method in ['POST', 'PUT']:
            # Логируем только основные поля, не весь payload
            if isinstance(request_data, dict):
                log_data["request_summary"] = {
                    "name": request_data.get("name"),
                    "type": "invoice" if "invoice" in url else "counterparty" if "counterparty" in url else "unknown"
                }
        
        # Добавляем информацию об ответе
        if response.status_code == 200:
            try:
                response_json = response.json()
                if isinstance(response_json, dict):
                    if "rows" in response_json:
                        log_data["response_summary"] = {"rows_count": len(response_json["rows"])}
                    elif "id" in response_json:
                        log_data["response_summary"] = {"created_id": response_json["id"]}
            except:
                pass
        else:
            log_data["error_text"] = response.text[:200]  # Первые 200 символов ошибки
        
        # Логируем с соответствующим уровнем
        if response.status_code == 200:
            logger.info(f"МойСклад API: {method} {log_data['url']} -> {response.status_code} ({duration_ms:.0f}ms)", extra=log_data)
        elif response.status_code in [401, 403]:
            logger.error(f"МойСклад API: Ошибка авторизации {method} {log_data['url']} -> {response.status_code}", extra=log_data)
        elif response.status_code >= 500:
            logger.error(f"МойСклад API: Серверная ошибка {method} {log_data['url']} -> {response.status_code}", extra=log_data)
        else:
            logger.warning(f"МойСклад API: {method} {log_data['url']} -> {response.status_code} ({duration_ms:.0f}ms)", extra=log_data)
    
    def _make_request(self, method: str, url: str, json_data: Optional[Dict] = None,
                      params: Optional[Dict] = None, timeout: int = 10) -> requests.Response:
        """Выполнение HTTP запроса с логированием"""
        start_time = time.time()
        
        try:
            logger.debug(f"Отправляю {method} запрос к МойСклад: {url}")
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=json_data, timeout=timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=json_data, timeout=timeout)
            else:
                raise ValueError(f"Неподдерживаемый HTTP метод: {method}")
            
            duration_ms = (time.time() - start_time) * 1000
            self._log_request(method.upper(), url, response, duration_ms, json_data)
            
            return response
            
        except requests.RequestException as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"МойСклад API: Сетевая ошибка {method} {url} ({duration_ms:.0f}ms): {e}")
            raise
    
    def verify_token(self) -> bool:
        """Проверка валидности токена"""
        try:
            url = f"{self.base_url}/context/employee"
            response = self._make_request('GET', url)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ошибка проверки токена: {e}")
            return False
    
    def verify_api_access(self) -> Dict:
        """
        Проверка доступа к API МойСклад через получение информации об организации
        
        Returns:
            Dict: Результат проверки с детальной информацией
        """
        try:
            logger.info("Проверяю доступ к API МойСклад...")
            
            # Проверяем базовый доступ к API
            employee_url = f"{self.base_url}/context/employee"
            employee_response = self._make_request('GET', employee_url)
            
            if employee_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Ошибка доступа к API: {employee_response.status_code}",
                    "details": employee_response.text
                }
            
            employee_data = employee_response.json()
            
            # Получаем информацию об организации
            org_url = f"{self.base_url}/entity/organization"
            org_response = self._make_request('GET', org_url)
            
            if org_response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Нет доступа к справочнику организаций: {org_response.status_code}",
                    "details": org_response.text
                }
            
            org_data = org_response.json()
            organizations = org_data.get("rows", [])
            
            if not organizations:
                return {
                    "success": False,
                    "error": "Организации не найдены",
                    "details": "В аккаунте МойСклад нет доступных организаций"
                }
            
            # Проверяем доступ к созданию документов (счета-фактуры выданные)
            invoice_url = f"{self.base_url}/entity/factureout"
            invoice_response = self._make_request('GET', invoice_url)
            
            can_create_invoices = invoice_response.status_code == 200
            
            # Проверяем доступ к контрагентам
            counterparty_url = f"{self.base_url}/entity/counterparty"
            counterparty_response = self._make_request('GET', counterparty_url)
            
            can_access_counterparties = counterparty_response.status_code == 200
            
            # Проверяем доступ к складам (необходимо для отгрузок)
            store_url = f"{self.base_url}/entity/store"
            store_response = self._make_request('GET', store_url)
            
            can_access_stores = store_response.status_code == 200
            stores_count = 0
            if can_access_stores:
                stores_data = store_response.json()
                stores_count = len(stores_data.get("rows", []))
            
            # Проверяем доступ к заказам покупателей (необходимо для привязки отгрузок)
            customer_order_url = f"{self.base_url}/entity/customerorder"
            customer_order_response = self._make_request('GET', customer_order_url)
            
            can_access_customer_orders = customer_order_response.status_code == 200
            customer_orders_count = 0
            if can_access_customer_orders:
                customer_orders_data = customer_order_response.json()
                customer_orders_count = len(customer_orders_data.get("rows", []))
            
            # Формируем результат
            main_org = organizations[0]
            
            result = {
                "success": True,
                "employee": {
                    "name": employee_data.get("name", "Не указано"),
                    "email": employee_data.get("email", "Не указано")
                },
                "organization": {
                    "name": main_org.get("name", "Не указано"),
                    "inn": main_org.get("inn", "Не указано"),
                    "id": main_org.get("id", "Не указано")
                },
                "permissions": {
                    "can_create_invoices": can_create_invoices,
                    "can_access_counterparties": can_access_counterparties,
                    "can_access_stores": can_access_stores,
                    "can_access_customer_orders": can_access_customer_orders,
                    "organizations_count": len(organizations),
                    "stores_count": stores_count,
                    "customer_orders_count": customer_orders_count
                },
                "api_info": {
                    "base_url": self.base_url,
                    "response_time_ms": "< 10000"
                }
            }
            
            logger.info(f"Доступ к API подтвержден. Организация: {main_org.get('name')}")
            return result
            
        except requests.RequestException as e:
            logger.error(f"Сетевая ошибка при проверке API: {e}")
            return {
                "success": False,
                "error": f"Сетевая ошибка: {e}",
                "details": "Проверьте подключение к интернету и доступность api.moysklad.ru"
            }
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке API: {e}")
            return {
                "success": False,
                "error": f"Неожиданная ошибка: {e}",
                "details": "Обратитесь к администратору"
            }
    
    def create_invoice_from_upd(self, upd_document: UPDDocument) -> Dict:
        """
        Создание счета-фактуры из УПД документа
        
        Args:
            upd_document: УПД документ
            
        Returns:
            Dict: Ответ от МойСклад API с информацией о созданном документе
            
        Raises:
            MoySkladAPIError: Ошибка создания документа
        """
        try:
            logger.info(f"Создаю документы для УПД: {upd_document.document_id}")
            
            # Определяем поставщика и покупателя из УПД
            # Поставщик (продавец) - это наша организация, ищем по ИНН
            supplier_org = self._find_organization_by_inn(upd_document.content.seller.inn)
            if not supplier_org:
                raise MoySkladAPIError(f"Организация поставщика с ИНН {upd_document.content.seller.inn} не найдена в МойСклад")
            
            # Покупатель - ищем или создаем контрагента
            buyer_counterparty = self._get_or_create_counterparty(upd_document.content.buyer)
            
            # Шаг 1: Создаем отгрузку (документ-основание)
            logger.info("Создаю отгрузку как документ-основание...")
            demand = self._create_demand(upd_document, supplier_org, buyer_counterparty)
            
            # Шаг 2: Создаем счет-фактуру на основе отгрузки
            logger.info("Создаю счет-фактуру на основе отгрузки...")
            invoice_data = self._map_upd_to_factureout(upd_document, supplier_org, buyer_counterparty, demand)
            
            # Создаем счет-фактуру выданную
            url = f"{self.base_url}/entity/factureout"
            response = self._make_request('POST', url, json_data=invoice_data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Счет-фактура успешно создан: {result.get('id')}")
                return {
                    "factureout": result,
                    "demand": demand,
                    "success": True
                }
            else:
                error_msg = f"Ошибка создания счета-фактуры: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise MoySkladAPIError(error_msg)
                
        except requests.RequestException as e:
            error_msg = f"Сетевая ошибка при создании счета-фактуры: {e}"
            logger.error(error_msg)
            raise MoySkladAPIError(error_msg)
        except Exception as e:
            error_msg = f"Неожиданная ошибка при создании счета-фактуры: {e}"
            logger.error(error_msg)
            raise MoySkladAPIError(error_msg)
    
    def _get_or_create_counterparty(self, buyer: Organization) -> Dict:
        """Получение или создание контрагента"""
        try:
            # Поиск по ИНН
            search_url = f"{self.base_url}/entity/counterparty"
            params = {"filter": f"inn={buyer.inn}"}
            response = self._make_request('GET', search_url, params=params)
            
            if response.status_code == 200:
                counterparties = response.json().get("rows", [])
                if counterparties:
                    logger.info(f"Найден существующий контрагент: {counterparties[0]['name']}")
                    return counterparties[0]
            
            # Создание нового контрагента
            logger.info(f"Создаю нового контрагента: {buyer.name}")
            counterparty_data = {
                "name": buyer.name,
                "inn": buyer.inn,
                "companyType": "legal"
            }
            
            if buyer.kpp:
                counterparty_data["kpp"] = buyer.kpp
            
            response = self._make_request('POST', search_url, json_data=counterparty_data)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Контрагент успешно создан: {result['name']}")
                return result
            else:
                error_msg = f"Ошибка создания контрагента: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise MoySkladAPIError(error_msg)
                
        except requests.RequestException as e:
            error_msg = f"Сетевая ошибка при работе с контрагентом: {e}"
            logger.error(error_msg)
            raise MoySkladAPIError(error_msg)
    
    def _get_organization(self) -> Dict:
        """Получение информации об организации"""
        try:
            if self.organization_id:
                url = f"{self.base_url}/entity/organization/{self.organization_id}"
            else:
                url = f"{self.base_url}/entity/organization"
            
            response = self._make_request('GET', url)
            
            if response.status_code == 200:
                if self.organization_id:
                    return response.json()
                else:
                    organizations = response.json().get("rows", [])
                    if organizations:
                        return organizations[0]
                    else:
                        raise MoySkladAPIError("Организации не найдены")
            else:
                error_msg = f"Ошибка получения организации: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise MoySkladAPIError(error_msg)
                
        except requests.RequestException as e:
            error_msg = f"Сетевая ошибка при получении организации: {e}"
            logger.error(error_msg)
            raise MoySkladAPIError(error_msg)
    
    def _find_organization_by_inn(self, inn: str) -> Optional[Dict]:
        """Поиск организации по ИНН"""
        try:
            url = f"{self.base_url}/entity/organization"
            params = {"filter": f"inn={inn}"}
            response = self._make_request('GET', url, params=params)
            
            if response.status_code == 200:
                organizations = response.json().get("rows", [])
                if organizations:
                    logger.info(f"Найдена организация по ИНН {inn}: {organizations[0]['name']}")
                    return organizations[0]
            
            logger.warning(f"Организация с ИНН {inn} не найдена")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска организации по ИНН: {e}")
            return None
    
    def _create_demand(self, upd_document: UPDDocument, organization: Dict, counterparty: Dict) -> Dict:
        """Создание отгрузки как документа-основания для счета-фактуры"""
        content = upd_document.content
        
        # МойСклад требует формат даты: YYYY-MM-DD HH:MM:SS.sss
        moment_str = content.invoice_date.strftime("%Y-%m-%d %H:%M:%S.000")
        
        # Ищем счет покупателя по номеру из реквизитов
        customer_invoice = self._find_customer_invoice(content.requisite_number, counterparty)
        
        # Получаем склад из счета покупателя
        store = None
        if customer_invoice:
            logger.info(f"Найден счет покупателя: {customer_invoice['name']}")
            logger.debug(f"Структура счета: {list(customer_invoice.keys())}")
            
            # В счетах поставщика (invoiceout) ищем склад
            # Попробуем разные варианты получения склада
            store = customer_invoice.get('store')
            if not store:
                # Возможно склад в другом поле
                store = customer_invoice.get('warehouse')
            
            logger.debug(f"Найденный объект склада: {store}")
            logger.debug("Доступные поля в счете: " + ", ".join(customer_invoice.keys()))
            
            if store:
                # Проверяем структуру объекта склада
                if isinstance(store, dict):
                    store_name = store.get('name', 'без названия')
                    store_id = store.get('id', 'нет ID')
                    
                    # Если нет прямых полей name/id, возможно это мета-ссылка
                    if store_name == 'без названия' and 'meta' in store:
                        # Получаем полную информацию о складе
                        try:
                            store_url = store['meta']['href']
                            store_response = self._make_request('GET', store_url)
                            if store_response.status_code == 200:
                                store_data = store_response.json()
                                store_name = store_data.get('name', 'без названия')
                                store_id = store_data.get('id', 'нет ID')
                                # Обновляем объект склада полными данными
                                store = store_data
                                logger.debug(f"Получена полная информация о складе: {store_name} (ID: {store_id})")
                        except Exception as e:
                            logger.error(f"Ошибка получения информации о складе: {e}")
                    
                    logger.info(f"Склад из счета: {store_name} (ID: {store_id})")
                    
                    # Проверяем что у нас есть корректные данные склада
                    if not store.get('meta') and not store.get('id'):
                        logger.error("Объект склада не содержит необходимых мета-данных")
                        raise MoySkladAPIError(
                            f"В найденном счете покупателя '{customer_invoice['name']}' склад указан некорректно.\n"
                            f"Проверьте настройки склада в счете и повторите попытку."
                        )
                else:
                    logger.error(f"Неожиданный тип объекта склада: {type(store)}")
                    raise MoySkladAPIError(
                        f"В найденном счете покупателя '{customer_invoice['name']}' склад указан в неожиданном формате.\n"
                        f"Обратитесь к администратору системы."
                    )
            else:
                logger.error("В найденном счете не указан склад")
                raise MoySkladAPIError(
                    f"В найденном счете покупателя '{customer_invoice['name']}' не указан склад.\n"
                    f"Укажите склад в счете и повторите попытку."
                )
        else:
            logger.error(f"Счет покупателя с номером {content.requisite_number} не найден")
            raise MoySkladAPIError(
                f"Счет покупателя с номером '{content.requisite_number}' не найден.\n"
                f"Создайте счет с указанным номером и повторите попытку."
            )
        
        logger.info(f"Итоговый склад для отгрузки: {store.get('name', 'без названия')} (ID: {store.get('id', 'нет ID')})")
        
        # Создаем имя для отгрузки с префиксом "О"
        demand_data = {
            "name": f"О{content.invoice_number}",  # Префикс "О" + номер УПД
            "moment": moment_str,
            "organization": {
                "meta": organization["meta"]
            },
            "agent": {
                "meta": counterparty["meta"]
            },
            "store": {
                "meta": store["meta"]
            },
            "vatEnabled": True,
            "vatIncluded": True,
            "positions": []
        }
        
        # Привязываем к счету поставщика, если найден
        if customer_invoice:
            demand_data["invoicesOut"] = [
                {
                    "meta": customer_invoice["meta"]
                }
            ]
        
        # Добавляем позиции (используем ту же логику что и для счета-фактуры)
        positions = self._create_positions_from_upd(content, customer_invoice)
        demand_data["positions"] = positions
        
        # Создаем отгрузку
        url = f"{self.base_url}/entity/demand"
        response = self._make_request('POST', url, json_data=demand_data, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Отгрузка успешно создана: {result.get('id')}")
            return result
        else:
            error_msg = f"Ошибка создания отгрузки: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise MoySkladAPIError(error_msg)
    
    def _map_upd_to_factureout(self, upd_document: UPDDocument, organization: Dict, counterparty: Dict, demand: Dict) -> Dict:
        """Преобразование УПД в формат счета-фактуры МойСклад с документом-основанием"""
        content = upd_document.content
        
        # МойСклад требует формат даты: YYYY-MM-DD HH:MM:SS.sss
        moment_str = content.invoice_date.strftime("%Y-%m-%d %H:%M:%S.000")
        logger.debug(f"Формат даты для МойСклад: {moment_str}")
        
        # Создаем имя для счета-фактуры равное номеру УПД
        invoice_data = {
            "name": content.invoice_number,  # Номер УПД как есть
            "moment": moment_str,
            "organization": {
                "meta": organization["meta"]
            },
            "agent": {
                "meta": counterparty["meta"]
            },
            "vatEnabled": True,
            "vatIncluded": True,
            # Ссылка на документ-основание (отгрузку)
            "demands": [
                {
                    "meta": demand["meta"]
                }
            ],
            "positions": []
        }
        
        logger.debug(f"Создаю счет-фактуру: {invoice_data['name']} на основе отгрузки {demand['id']}")
        
        # Добавляем позиции (используем ту же логику что и для отгрузки)
        # Нужно найти счет покупателя для получения цен
        customer_invoice = self._find_customer_invoice(content.requisite_number, None)
        positions = self._create_positions_from_upd(content, customer_invoice)
        invoice_data["positions"] = positions
        
        logger.debug(f"Итоговые данные счета-фактуры: позиций={len(invoice_data['positions'])}")
        
        return invoice_data
    
    def _create_positions_from_upd(self, content: UPDContent, customer_invoice: Optional[Dict] = None) -> List[Dict]:
        """Создание позиций документа из УПД с использованием цен из счета"""
        positions = []
        missing_items = []
        
        # Получаем позиции из счета для сопоставления цен
        invoice_positions = {}
        if customer_invoice:
            # Получаем полную информацию о счете с позициями
            try:
                invoice_url = customer_invoice['meta']['href']
                invoice_response = self._make_request('GET', invoice_url + '?expand=positions.assortment')
                if invoice_response.status_code == 200:
                    invoice_data = invoice_response.json()
                    logger.debug(f"Структура счета: {list(invoice_data.keys())}")
                    logger.debug(f"Полная структура счета: {invoice_data}")
                    
                    # Проверяем разные варианты структуры позиций
                    positions_data = None
                    if 'positions' in invoice_data:
                        positions_data = invoice_data['positions']
                        logger.debug(f"Тип positions: {type(positions_data)}")
                        logger.debug(f"Содержимое positions: {positions_data}")
                        
                        if isinstance(positions_data, dict):
                            if 'rows' in positions_data:
                                positions_data = positions_data['rows']
                                logger.debug(f"Используем positions.rows, найдено: {len(positions_data)}")
                            elif 'meta' in positions_data and 'href' in positions_data['meta']:
                                # Позиции нужно загрузить отдельно
                                logger.debug("Позиции нужно загрузить отдельно по ссылке")
                                positions_url = positions_data['meta']['href']
                                positions_response = self._make_request('GET', positions_url)
                                if positions_response.status_code == 200:
                                    positions_result = positions_response.json()
                                    positions_data = positions_result.get('rows', [])
                                    logger.debug(f"Загружено позиций по ссылке: {len(positions_data)}")
                                else:
                                    logger.error(f"Ошибка загрузки позиций по ссылке: {positions_response.status_code}")
                                    positions_data = []
                            else:
                                logger.warning(f"Неожиданная структура positions dict: {list(positions_data.keys())}")
                                positions_data = []
                        elif isinstance(positions_data, list):
                            # positions уже список
                            logger.debug(f"Positions уже список, найдено: {len(positions_data)}")
                        else:
                            logger.warning(f"Неожиданная структура positions: {type(positions_data)}")
                            positions_data = []
                    else:
                        logger.warning("Поле 'positions' не найдено в счете")
                        positions_data = []
                    
                    logger.debug(f"Итого найдено позиций в счете: {len(positions_data) if positions_data else 0}")
                    
                    if positions_data:
                        for i, pos in enumerate(positions_data):
                            logger.debug(f"Обрабатываю позицию {i+1}: {list(pos.keys()) if isinstance(pos, dict) else type(pos)}")
                            logger.debug(f"Полное содержимое позиции {i+1}: {pos}")
                            
                            assortment = pos.get('assortment', {})
                            if assortment:
                                # Создаем ключи для поиска по артикулу и названию
                                product_name = assortment.get('name', '')
                                product_article = assortment.get('article', '')
                                price = pos.get('price', 0)
                                logger.debug(f"Товар: {product_name}, артикул: {product_article}, цена: {price}")
                                
                                if product_article:
                                    invoice_positions[f"article:{product_article}"] = price
                                if product_name:
                                    invoice_positions[f"name:{product_name}"] = price
                            else:
                                logger.warning(f"В позиции {i+1} не найдено поле assortment")
                    
                    logger.info(f"Загружено {len(invoice_positions)} позиций из счета для сопоставления цен")
                    if invoice_positions:
                        logger.debug(f"Ключи позиций: {list(invoice_positions.keys())}")
            except Exception as e:
                logger.error(f"Ошибка получения позиций из счета: {e}")
        
        # Добавляем позиции из УПД
        for item in content.items:
            # Ищем товар по артикулу, если есть
            product = None
            if item.article:
                logger.info(f"Ищем товар по артикулу: {item.article}")
                product = self._find_product_by_article(item.article)
                if product:
                    logger.info(f"✅ Товар найден по артикулу {item.article}: {product.get('name', 'без названия')} (ID: {product.get('id', 'нет ID')})")
                else:
                    logger.warning(f"❌ Товар не найден по артикулу: {item.article}")
            
            # Если не найден по артикулу, ищем по названию
            if not product:
                logger.info(f"Ищем товар по названию: {item.name}")
                product = self._find_product(item.name)
                if product:
                    logger.info(f"✅ Товар найден по названию: {product.get('name', 'без названия')} (ID: {product.get('id', 'нет ID')})")
                else:
                    logger.warning(f"❌ Товар не найден по названию: {item.name}")
            
            if product:
                # Определяем цену: сначала из счета, потом из УПД
                price_kopecks = int(float(item.price) * 100)  # Цена из УПД по умолчанию
                
                # Ищем цену в счете по артикулу
                if item.article and f"article:{item.article}" in invoice_positions:
                    invoice_price = invoice_positions[f"article:{item.article}"]
                    if invoice_price > 0:
                        price_kopecks = invoice_price
                        logger.info(f"Использую цену из счета по артикулу {item.article}: {price_kopecks/100:.2f} руб")
                # Если не найдено по артикулу, ищем по названию
                elif f"name:{item.name}" in invoice_positions:
                    invoice_price = invoice_positions[f"name:{item.name}"]
                    if invoice_price > 0:
                        price_kopecks = invoice_price
                        logger.info(f"Использую цену из счета по названию '{item.name}': {price_kopecks/100:.2f} руб")
                else:
                    logger.warning(f"Цена для товара '{item.name}' не найдена в счете, использую цену из УПД: {price_kopecks/100:.2f} руб")
                
                position = {
                    "quantity": float(item.quantity),
                    "price": price_kopecks,
                    "assortment": {
                        "meta": product["meta"]
                    },
                    "vat": self._get_vat_rate(item.vat_rate)
                }
                positions.append(position)
            else:
                missing_items.append(f"{item.name} (артикул: {item.article or 'не указан'})")
        
        # Если есть отсутствующие товары, выдаем ошибку
        if missing_items:
            error_msg = (
                f"В МойСклад не найдены следующие товары из УПД:\n"
                f"• {chr(10).join(missing_items)}\n\n"
                f"Создайте эти товары в МойСклад вручную и повторите загрузку УПД."
            )
            raise MoySkladAPIError(error_msg)
        
        # Если нет позиций из УПД, используем любую доступную услугу
        if not positions:
            # Цена в копейках
            total_price_kopecks = int(float(content.total_with_vat) * 100) if content.total_with_vat > 0 else 100000  # 1000 руб по умолчанию
            
            # Ищем любую доступную услугу
            service = self._get_any_available_service()
            
            if not service:
                raise MoySkladAPIError(
                    "В МойСклад нет доступных услуг для создания позиции документа.\n"
                    "Создайте хотя бы одну услугу в МойСклад и повторите попытку."
                )
            
            positions.append({
                "quantity": 1,
                "price": total_price_kopecks,
                "assortment": {
                    "meta": service["meta"]
                },
                "vat": 18
            })
        
        return positions
    
    def _get_vat_rate(self, vat_rate_str: Optional[str]) -> int:
        """Преобразование строки НДС в числовое значение"""
        if not vat_rate_str:
            return 18
        
        # Извлекаем число из строки типа "18%" или "20%"
        import re
        match = re.search(r'(\d+)', vat_rate_str)
        if match:
            return int(match.group(1))
        
        return 18  # По умолчанию
    
    def get_invoice_url(self, invoice_id: str) -> str:
        """Получение URL счета-фактуры в веб-интерфейсе МойСклад"""
        return f"https://online.moysklad.ru/app/#factureout/edit?id={invoice_id}"
    
    def get_demand_url(self, demand_id: str) -> str:
        """Получение URL отгрузки в веб-интерфейсе МойСклад"""
        return f"https://online.moysklad.ru/app/#demand/edit?id={demand_id}"
    
    def get_invoice_info(self, invoice_id: str) -> Optional[Dict]:
        """Получение информации о счете-фактуре"""
        try:
            url = f"{self.base_url}/entity/factureout/{invoice_id}"
            response = self._make_request('GET', url)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения информации о счете-фактуре: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Ошибка получения информации о счете-фактуре: {e}")
            return None
    
    def _find_product(self, product_name: str) -> Optional[Dict]:
        """Поиск существующего товара по имени"""
        try:
            search_url = f"{self.base_url}/entity/product"
            params = {"filter": f"name={product_name}"}
            response = self._make_request('GET', search_url, params=params)
            
            if response.status_code == 200:
                products = response.json().get("rows", [])
                if products:
                    logger.debug(f"Найден товар: {products[0]['name']}")
                    return products[0]
            
            logger.warning(f"Товар '{product_name}' не найден в МойСклад")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска товара: {e}")
            return None
    
    def _find_product_by_article(self, article: str) -> Optional[Dict]:
        """Поиск существующего товара по артикулу"""
        try:
            search_url = f"{self.base_url}/entity/product"
            params = {"filter": f"article={article}"}
            response = self._make_request('GET', search_url, params=params)
            
            if response.status_code == 200:
                products = response.json().get("rows", [])
                if products:
                    logger.debug(f"Найден товар по артикулу {article}: {products[0]['name']}")
                    return products[0]
            
            logger.debug(f"Товар с артикулом {article} не найден")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска товара по артикулу: {e}")
            return None
    
    def _find_service(self, service_name: str) -> Optional[Dict]:
        """Поиск существующей услуги по имени"""
        try:
            search_url = f"{self.base_url}/entity/service"
            params = {"filter": f"name={service_name}"}
            response = self._make_request('GET', search_url, params=params)
            
            if response.status_code == 200:
                services = response.json().get("rows", [])
                if services:
                    logger.debug(f"Найдена услуга: {services[0]['name']}")
                    return services[0]
            
            logger.warning(f"Услуга '{service_name}' не найдена в МойСклад")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска услуги: {e}")
            return None
    
    def _get_any_available_service(self) -> Optional[Dict]:
        """Получение любой доступной услуги"""
        try:
            search_url = f"{self.base_url}/entity/service"
            response = self._make_request('GET', search_url)
            
            if response.status_code == 200:
                services = response.json().get("rows", [])
                if services:
                    logger.debug(f"Использую доступную услугу: {services[0]['name']}")
                    return services[0]
            
            logger.warning("В МойСклад нет доступных услуг")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка получения услуг: {e}")
            return None
    
    def _find_customer_invoice(self, requisite_number: Optional[str], counterparty: Dict) -> Optional[Dict]:
        """Поиск счета поставщика по номеру из реквизитов (без привязки к контрагенту)"""
        if not requisite_number:
            logger.debug("Номер из реквизитов не найден")
            return None
        
        try:
            logger.info(f"Ищем счет поставщика с номером: {requisite_number} (без привязки к контрагенту)")
            
            # Варианты поиска счета
            search_patterns = [
                f"name={requisite_number}",  # Точное совпадение имени
                f"name~{requisite_number}",  # Частичное совпадение имени
                f"description~{requisite_number}",  # Поиск в описании
            ]
            
            for pattern in search_patterns:
                logger.debug(f"Поиск счета с фильтром: {pattern}")
                
                search_url = f"{self.base_url}/entity/invoiceout"  # Изменено на invoiceout
                params = {"filter": pattern}
                
                response = self._make_request('GET', search_url, params=params)
                
                if response.status_code == 200:
                    invoices = response.json().get("rows", [])
                    logger.debug(f"Найдено счетов с фильтром '{pattern}': {len(invoices)}")
                    
                    # Берем первый найденный счет (без проверки контрагента)
                    if invoices:
                        invoice = invoices[0]
                        
                        # Получаем полную информацию о счете
                        invoice_url = invoice['meta']['href']
                        invoice_response = self._make_request('GET', invoice_url)
                        
                        if invoice_response.status_code == 200:
                            invoice_data = invoice_response.json()
                            invoice_agent = invoice_data.get('agent', {})
                            agent_name = invoice_agent.get('name', 'неизвестно') if invoice_agent else 'неизвестно'
                            
                            logger.info(f"Найден счет поставщика: {invoice['name']} (контрагент: {agent_name}, фильтр: {pattern})")
                            return invoice_data
                else:
                    logger.debug(f"Ошибка поиска с фильтром '{pattern}': {response.status_code}")
            
            logger.warning(f"Счет поставщика с номером {requisite_number} не найден")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска счета поставщика по реквизиту {requisite_number}: {e}")
            return None
    
    def _get_store_from_invoice(self, requisite_number: Optional[str], counterparty: Dict) -> Optional[Dict]:
        """Получение склада из счета покупателя по номеру из реквизитов"""
        if not requisite_number:
            logger.debug("Номер счета из реквизитов не найден")
            return None
        
        try:
            # Ищем счет покупателя по номеру и контрагенту
            search_url = f"{self.base_url}/entity/invoicein"
            params = {
                "filter": f"name~{requisite_number};agent={counterparty['meta']['href']}"
            }
            response = self._make_request('GET', search_url, params=params)
            
            if response.status_code == 200:
                invoices = response.json().get("rows", [])
                if invoices:
                    invoice = invoices[0]
                    logger.info(f"Найден счет покупателя: {invoice['name']}")
                    
                    # Получаем полную информацию о счете для извлечения склада
                    invoice_url = invoice['meta']['href']
                    invoice_response = self._make_request('GET', invoice_url)
                    
                    if invoice_response.status_code == 200:
                        invoice_data = invoice_response.json()
                        store = invoice_data.get('store')
                        if store:
                            logger.info(f"Найден склад из счета: {store.get('name', 'Неизвестно')}")
                            return store
            
            logger.warning(f"Счет с номером {requisite_number} не найден")
            return None
                
        except Exception as e:
            logger.error(f"Ошибка поиска счета по номеру {requisite_number}: {e}")
            return None
    