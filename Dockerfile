# Используем Alpine Linux для минимального размера образа
FROM python:3.11-alpine

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости для Alpine
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libxml2-dev \
    libxslt-dev \
    libffi-dev \
    openssl-dev \
    && rm -rf /var/cache/apk/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ ./src/
COPY main.py .

# Создаем директории для логов и временных файлов
RUN mkdir -p logs temp

# Создаем пользователя для безопасности (Alpine Linux)
RUN addgroup -g 1000 botuser && \
    adduser -D -s /bin/sh -u 1000 -G botuser botuser && \
    chown -R botuser:botuser /app
USER botuser

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Открываем порт (если потребуется для webhook)
EXPOSE 8080

# Команда запуска
CMD ["python", "main.py"]