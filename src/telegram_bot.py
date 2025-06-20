"""
Telegram бот для загрузки УПД в МойСклад
"""
import asyncio
from typing import Optional

from telegram import Update, Document
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, filters
)
from loguru import logger

from .config import Config
from .upd_processor import UPDProcessor


class TelegramUPDBot:
    """Telegram бот для обработки УПД"""
    
    def __init__(self):
        self.processor = UPDProcessor()
        self.application = None
    
    def setup_bot(self) -> Application:
        """Настройка бота"""
        # Создаем приложение
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Добавляем обработчик документов
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        
        # Добавляем обработчик текстовых сообщений
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text)
        )
        
        logger.info("Telegram бот настроен")
        return self.application
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту.\n"
                "Обратитесь к администратору для получения доступа."
            )
            return
        
        welcome_message = (
            "🤖 Добро пожаловать в бот загрузки УПД в МойСклад!\n\n"
            "📋 Что я умею:\n"
            "• Обрабатывать ZIP архивы с УПД документами\n"
            "• Создавать счета-фактуры в МойСклад\n"
            "• Предоставлять детальную информацию о результатах\n\n"
            "📎 Просто отправьте мне ZIP файл с УПД, и я его обработаю!\n\n"
            "ℹ️ Используйте /help для получения дополнительной информации."
        )
        
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        help_message = (
            "📖 Справка по использованию бота\n\n"
            "🔧 Доступные команды:\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "/status - Проверить статус подключения к МойСклад\n\n"
            "📎 Как загрузить УПД:\n"
            "1. Отправьте ZIP архив с УПД документом\n"
            "2. Дождитесь обработки (обычно 10-30 секунд)\n"
            "3. Получите результат с ссылкой на созданный документ\n\n"
            "📋 Требования к файлам:\n"
            f"• Формат: ZIP архив\n"
            f"• Максимальный размер: {Config.MAX_FILE_SIZE // 1024 // 1024} МБ\n"
            "• Содержимое: УПД в стандартном формате\n\n"
            "❓ При возникновении проблем обратитесь к администратору."
        )
        
        await update.message.reply_text(help_message)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        # Отправляем сообщение о проверке
        status_message = await update.message.reply_text("🔄 Проверяю подключение к МойСклад...")
        
        # Проверяем подключение с детальной информацией
        try:
            status_info = await asyncio.get_event_loop().run_in_executor(
                None, self.processor.get_moysklad_status
            )
            
            if status_info["success"]:
                # Формируем детальное сообщение об успехе
                org_info = status_info.get("organization", {})
                employee_info = status_info.get("employee", {})
                permissions = status_info.get("permissions", {})
                
                result_message = (
                    "✅ Статус системы: Все работает!\n\n"
                    "👤 Пользователь МойСклад:\n"
                    f"   Имя: {employee_info.get('name', 'Не указано')}\n"
                    f"   Email: {employee_info.get('email', 'Не указано')}\n\n"
                    "🏢 Организация:\n"
                    f"   Название: {org_info.get('name', 'Не указано')}\n"
                    f"   ИНН: {org_info.get('inn', 'Не указано')}\n\n"
                    "🔐 Права доступа:\n"
                    f"   {'✅' if permissions.get('can_create_invoices') else '❌'} Создание счетов-фактур\n"
                    f"   {'✅' if permissions.get('can_access_counterparties') else '❌'} Работа с контрагентами\n"
                    f"   📊 Организаций: {permissions.get('organizations_count', 0)}\n\n"
                    "🤖 Telegram бот: Активен\n"
                    "📁 Временная папка: Доступна\n\n"
                    "🎉 Готов к обработке УПД документов!"
                )
            else:
                # Формируем сообщение об ошибке
                error = status_info.get("error", "Неизвестная ошибка")
                details = status_info.get("details", "")
                
                result_message = (
                    "⚠️ Статус системы: Есть проблемы\n\n"
                    f"❌ МойСклад API: {error}\n"
                    "🤖 Telegram бот: Активен\n\n"
                    f"📝 Детали: {details}\n\n"
                    "💡 Рекомендации:\n"
                    "• Проверьте токен МойСклад API\n"
                    "• Убедитесь в наличии прав доступа\n"
                    "• Обратитесь к администратору"
                )
            
            await status_message.edit_text(result_message)
            
        except Exception as e:
            logger.error(f"Ошибка проверки статуса: {e}")
            await status_message.edit_text(
                "❌ Ошибка при проверке статуса системы.\n"
                "Обратитесь к администратору."
            )
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик документов"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        document: Document = update.message.document
        
        try:
            logger.info(f"Получен документ от пользователя {user_id}: {document.file_name}")
            
            # Отправляем сообщение о начале обработки
            processing_message = await update.message.reply_text(
                f"📄 Получен файл: {document.file_name}\n"
                "🔄 Начинаю обработку УПД...\n\n"
                "⏳ Это может занять до 30 секунд, пожалуйста, подождите."
            )
            
            # Скачиваем файл
            file = await context.bot.get_file(document.file_id)
            file_content = await file.download_as_bytearray()
            
            # Обрабатываем УПД
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                self.processor.process_upd_file,
                bytes(file_content),
                document.file_name
            )
            
            # Отправляем результат
            await processing_message.edit_text(result.message)
            
            if result.success:
                logger.info(f"УПД успешно обработан для пользователя {user_id}")
            else:
                logger.warning(f"Ошибка обработки УПД для пользователя {user_id}: {result.error_code}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки документа: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке файла.\n"
                "Попробуйте еще раз или обратитесь к администратору."
            )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        await update.message.reply_text(
            "📎 Для обработки УПД отправьте мне ZIP архив с документом.\n\n"
            "ℹ️ Используйте /help для получения подробной информации."
        )
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """Проверка авторизации пользователя"""
        return user_id in Config.AUTHORIZED_USERS
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка в боте: {context.error}")
        
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ Произошла внутренняя ошибка.\n"
                    "Попробуйте еще раз или обратитесь к администратору."
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
    
    def run(self):
        """Запуск бота"""
        try:
            logger.info("Запуск Telegram бота...")
            
            # Настраиваем бот
            app = self.setup_bot()
            
            # Добавляем обработчик ошибок
            app.add_error_handler(self.error_handler)
            
            # Запускаем бота
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
        except Exception as e:
            logger.error(f"Критическая ошибка при запуске бота: {e}")
            raise