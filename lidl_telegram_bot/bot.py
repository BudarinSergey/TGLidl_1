# bot.py
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
import asyncio
import time
import signal
import sys
import os

from config import BOT_TOKEN, CHANNEL_ID, NOTIFICATION_TIMES
from image_data_parser import ImageDataLidlParser
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class LidlTelegramBot:
    def __init__(self):
        self.parser = ImageDataLidlParser()
        self.db = Database("lidl_offers.db")
        self.scheduler = BackgroundScheduler()
        self.application = None
        self.is_running = True

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""

        def signal_handler(signum, frame):
            print(f"\n🛑 Получен сигнал {signum}. Завершаем работу...")
            self.is_running = False
            self.scheduler.shutdown()
            if self.application:
                self.application.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start для администратора"""
        await update.message.reply_text(
            "🤖 Бот Lidl акций запущен и работает!\n\n"
            "Команды:\n"
            "/update - Обновить акции\n"
            "/stats - Статистика\n"
            "/test - Тестовая отправка\n"
            "/status - Статус бота"
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверка статуса бота"""
        status_msg = (
            "✅ Бот активен и работает\n"
            f"🕒 Время работы: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            "📡 Ожидаю команды и запланированные обновления"
        )
        await update.message.reply_text(status_msg)

    async def update_offers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ручное обновление акций"""
        await update.message.reply_text("🔄 Обновляю акции...")

        result = await self.fetch_and_send_offers()
        if result["success"]:
            await update.message.reply_text(
                f"✅ Обновлено! Найдено {result['total_offers']} акций, отправлено {result['sent_offers']}"
            )
        else:
            await update.message.reply_text(f"❌ Ошибка: {result['error']}")

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статистика бота"""
        try:
            total_offers = self.db.get_total_offers_count()
            sent_offers = self.db.get_sent_offers_count()

            await update.message.reply_text(
                f"📊 Статистика бота:\n"
                f"• Всего акций в базе: {total_offers}\n"
                f"• Отправлено акций: {sent_offers}\n"
                f"• Последнее обновление: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка получения статистики: {e}")

    async def test_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестовая отправка"""
        try:
            test_offer = {
                'name': 'Тестовый товар - Mleko 2.8% 1L',
                'price': '89.99 RSD',
                'category': 'Mlečni proizvodi',
                'image_url': None
            }

            message = await self.format_offer_message(test_offer)
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode='HTML'
            )
            await update.message.reply_text("✅ Тестовое сообщение отправлено в канал")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка отправки: {e}")

    async def format_offer_message(self, offer):
        """Форматирование сообщения об акции"""
        message = f"🔥 <b>AKCIJA - LIDL</b> 🔥\n\n"
        message += f"🛍️ <b>{offer['name']}</b>\n"
        message += f"💰 <b>Cena: {offer['price']}</b>\n"

        if offer.get('category'):
            message += f"📂 Kategorija: {offer['category']}\n"

        message += f"\n🛒 <b>Lidl Serbia</b>\n"
        message += f"⚡ Brza porudžbina pre nego što ponestane!\n"
        message += f"\n#Lidl #Akcija #Srbija #Cene"

        return message

    async def fetch_and_send_offers(self):
        """Получение и отправка новых акций"""
        try:
            print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Запуск парсинга акций...")

            result = self.parser.parse_offers()

            if not result["success"]:
                return {"success": False, "error": result["error"]}

            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Найдено: {result['total']} акций")

            self.db.save_offers(result["offers"])
            new_offers = self.db.get_new_offers()

            sent_count = 0
            for offer in new_offers[:15]:
                try:
                    message = await self.format_offer_message(offer)

                    if offer.get('image_url') and self.is_valid_url(offer['image_url']):
                        await self.send_offer_with_photo(offer, message)
                    else:
                        sent_message = await self.application.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message,
                            parse_mode='HTML'
                        )

                    self.db.mark_as_sent(offer['offer_id'],
                                         sent_message.message_id if 'sent_message' in locals() else 0)
                    sent_count += 1

                    print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Отправлена: {offer['name']}")
                    await asyncio.sleep(3)

                except Exception as e:
                    logger.error(f"Ошибка отправки: {e}")
                    continue

            return {
                "success": True,
                "total_offers": len(result["offers"]),
                "new_offers": len(new_offers),
                "sent_offers": sent_count
            }

        except Exception as e:
            logger.error(f"Ошибка в fetch_and_send_offers: {e}")
            return {"success": False, "error": str(e)}

    async def send_offer_with_photo(self, offer, message):
        """Отправка акции с фотографией"""
        try:
            return await self.application.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=offer['image_url'],
                caption=message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"❌ Ошибка отправки фото: {e}")
            return await self.application.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode='HTML'
            )

    def is_valid_url(self, url):
        """Проверка валидности URL"""
        return url and isinstance(url, str) and url.startswith(('http://', 'https://'))

    def schedule_updates(self):
        """Настройка расписания обновлений"""
        for i, notification_time in enumerate(NOTIFICATION_TIMES):
            self.scheduler.add_job(
                self.scheduled_update,
                CronTrigger(hour=notification_time.hour, minute=notification_time.minute),
                id=f"update_{i}"
            )
            print(f"⏰ Запланировано обновление на {notification_time.strftime('%H:%M')}")

        self.scheduler.start()
        logger.info("✅ Планировщик запущен")

    async def scheduled_update(self):
        """Запланированное обновление"""
        logger.info(f"⏰ Запуск запланированного обновления в {datetime.now().strftime('%H:%M')}")
        result = await self.fetch_and_send_offers()

        if result["success"]:
            logger.info(f"✅ Обновление завершено. Отправлено {result['sent_offers']} акций")
        else:
            logger.error(f"❌ Ошибка обновления: {result['error']}")

    def run(self):
        """Основной метод запуска бота"""
        print("🤖 Запуск бота Lidl акций...")
        print("=" * 50)

        # Создаем приложение
        self.application = Application.builder().token(BOT_TOKEN).build()

        # Настраиваем обработчики сигналов
        self.setup_signal_handlers()

        # Добавляем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("update", self.update_offers))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("test", self.test_post))
        self.application.add_handler(CommandHandler("status", self.status))

        # Запускаем планировщик
        self.schedule_updates()

        print("✅ Бот успешно запущен!")
        print("📋 Доступные команды: /start, /status, /update, /stats, /test")
        print("⏰ Бот будет работать в фоновом режиме")
        print("🛑 Для остановки нажмите Ctrl+C")
        print("=" * 50)

        # Запускаем бота
        try:
            self.application.run_polling()
        except KeyboardInterrupt:
            print("\n🛑 Остановка бота по запросу пользователя...")
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            self.scheduler.shutdown()
            print("✅ Бот завершил работу")


def main():
    """Точка входа"""
    bot = LidlTelegramBot()
    bot.run()


if __name__ == '__main__':
    main()