# Docker развертывание Telegram бота для УПД

## 🐳 Быстрый запуск с Docker

> **Образ основан на Alpine Linux** для минимального размера и максимальной безопасности

### Предварительные требования

- Docker Desktop установлен и запущен
- Git (для клонирования репозитория)

### 1. Подготовка

```bash
# Клонируйте репозиторий (если еще не сделано)
git clone <repository-url>
cd telegram-upd-bot

# Скопируйте пример конфигурации
cp .env.example .env
```

### 2. Настройка конфигурации

Отредактируйте файл `.env` и заполните необходимые токены:

```env
# Telegram Bot Token (получите у @BotFather)
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# МойСклад API Token
MOYSKLAD_API_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...

# Авторизованные пользователи (ваш Telegram ID)
AUTHORIZED_USERS=123456789

# Опциональные настройки
MOYSKLAD_ORGANIZATION_ID=
TEMP_DIR=./temp
LOG_LEVEL=INFO
MAX_FILE_SIZE=10485760
```

### 3. Запуск бота

```bash
# Сборка и запуск в фоновом режиме
docker-compose up -d

# Просмотр логов
docker-compose logs -f upd-telegram-bot

# Остановка бота
docker-compose down
```

## 📋 Доступные команды

### Основные команды

```bash
# Запуск бота
docker-compose up -d

# Просмотр статуса
docker-compose ps

# Просмотр логов
docker-compose logs upd-telegram-bot

# Следить за логами в реальном времени
docker-compose logs -f upd-telegram-bot

# Перезапуск бота
docker-compose restart upd-telegram-bot

# Остановка бота
docker-compose down

# Полная очистка (удаление контейнеров и образов)
docker-compose down --rmi all --volumes
```

### Обновление бота

```bash
# Остановка текущего контейнера
docker-compose down

# Пересборка образа
docker-compose build --no-cache

# Запуск обновленной версии
docker-compose up -d
```

## 🔍 Мониторинг и отладка

### Просмотр логов

```bash
# Последние 100 строк логов
docker-compose logs --tail=100 upd-telegram-bot

# Логи с временными метками
docker-compose logs -t upd-telegram-bot

# Логи за последний час
docker-compose logs --since="1h" upd-telegram-bot
```

### Веб-интерфейс для логов (опционально)

```bash
# Запуск с мониторингом логов
docker-compose --profile monitoring up -d

# Откройте в браузере: http://localhost:9999
# Для просмотра логов всех контейнеров
```

### Подключение к контейнеру

```bash
# Выполнение команд внутри контейнера
docker-compose exec upd-telegram-bot bash

# Проверка статуса внутри контейнера
docker-compose exec upd-telegram-bot python test_bot.py
```

## 📁 Структура томов

Docker монтирует следующие директории:

```
./logs     → /app/logs     # Логи бота
./temp     → /app/temp     # Временные файлы
./data     → /app/data     # Дополнительные данные
```

## 🛠️ Настройка Docker Compose

### Основной сервис

```yaml
services:
  upd-telegram-bot:
    build: .                    # Сборка из Dockerfile
    restart: unless-stopped     # Автоперезапуск
    env_file: .env             # Переменные окружения
    volumes:                   # Монтирование директорий
      - ./logs:/app/logs
      - ./temp:/app/temp
```

### Дополнительные возможности

- **Healthcheck**: Проверка здоровья контейнера каждые 30 секунд
- **Logging**: Ротация логов Docker (10MB, 3 файла)
- **Restart Policy**: Автоматический перезапуск при сбоях
- **Network**: Изолированная сеть для безопасности

## 🔧 Решение проблем

### Проблема: Контейнер не запускается

```bash
# Проверьте логи сборки
docker-compose build

# Проверьте конфигурацию
docker-compose config

# Проверьте статус
docker-compose ps
```

### Проблема: Ошибки в логах

```bash
# Подробные логи
docker-compose logs --details upd-telegram-bot

# Проверка внутри контейнера
docker-compose exec upd-telegram-bot python test_bot.py
```

### Проблема: Нет доступа к файлам

```bash
# Проверьте права доступа
ls -la logs/ temp/

# Исправьте права (если нужно)
sudo chown -R $USER:$USER logs/ temp/
```

### Проблема: Порты заняты

```bash
# Измените порт в docker-compose.yml
ports:
  - "9998:8080"  # Вместо 9999:8080
```

## 🚀 Продакшн развертывание

### Рекомендации для продакшн

1. **Используйте внешние тома**:
```yaml
volumes:
  - bot_logs:/app/logs
  - bot_temp:/app/temp
```

2. **Настройте мониторинг**:
```yaml
healthcheck:
  test: ["CMD", "python", "test_bot.py"]
  interval: 30s
  timeout: 10s
  retries: 3
```

3. **Ограничьте ресурсы**:
```yaml
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
```

4. **Используйте secrets для токенов**:
```yaml
secrets:
  telegram_token:
    file: ./secrets/telegram_token.txt
```

## 📊 Мониторинг производительности

```bash
# Использование ресурсов
docker stats upd-telegram-bot

# Информация о контейнере
docker inspect upd-telegram-bot

# Размер образа
docker images | grep upd-telegram-bot
```

## 🔄 Автоматическое обновление

Создайте скрипт `update.sh`:

```bash
#!/bin/bash
echo "Обновление UPD Telegram Bot..."
docker-compose down
git pull
docker-compose build --no-cache
docker-compose up -d
echo "Обновление завершено!"
```

```bash
chmod +x update.sh
./update.sh
```

## 🎯 Готово!

После настройки `.env` файла просто выполните:

```bash
docker-compose up -d
```

Бот будет запущен в фоновом режиме и автоматически перезапускаться при сбоях.