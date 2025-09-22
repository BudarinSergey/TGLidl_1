# stable_bot.py
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import asyncio
from datetime import datetime

from config import BOT_TOKEN, CHANNEL_ID, NOTIFICATION_TIMES
from fixed_parser import FixedLidlParser
from database import Database

# Минимальное логирование
logging.basicConfig(level=logging.ERROR)


class StableLidlBot:
    def __init__(self):
        self.parser = FixedLidlParser()
        self.db = Database("lidl_offers.db")
        self.scheduler = BackgroundScheduler()

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🤖 Бот Lidl акций работает!\n"
            "⏰ Парсинг каждый день в 7:00 утра\n\n"
            "Команды:\n"
            "/update - Обновить акции сейчас\n"
            "/stats - Статистика\n"
            "/test - Тестовая отправка\n"
            "/schedule - Текущее расписание"
        )

    async def schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущее расписание"""
        schedule_info = (
            "📅 **Расписание парсинга:**\n"
            "• Ежедневно в 7:00 утра\n"
            f"• Следующий парсинг: завтра в 07:00\n"
            f"• Текущее время: {datetime.now().strftime('%H:%M:%S')}"
        )
        await update.message.reply_text(schedule_info)

    async def update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ручное обновление акций"""
        await update.message.reply_text("🔄 Начинаю парсинг...")

        try:
            result = self.parser.parse_offers()

            if not result["success"]:
                await update.message.reply_text(f"❌ Ошибка: {result['error']}")
                return

            if result["total"] == 0:
                await update.message.reply_text("ℹ️ Акций не найдено")
                return

            # Сохраняем в базу
            self.db.save_offers(result["offers"])
            new_offers = self.db.get_new_offers()

            if not new_offers:
                await update.message.reply_text("ℹ️ Новых акций нет")
                return

            # Отправляем акции
            sent_count = 0
            for offer in new_offers[:10]:  # Ограничиваем количество
                try:
                    message = self.format_offer_message(offer)

                    # Пытаемся отправить с фото
                    if offer.get('image_url') and self.is_valid_url(offer['image_url']):
                        try:
                            await context.bot.send_photo(
                                chat_id=CHANNEL_ID,
                                photo=offer['image_url'],
                                caption=message,
                                parse_mode='HTML'
                            )
                        except:
                            # Если фото не отправляется, отправляем текст
                            await context.bot.send_message(
                                chat_id=CHANNEL_ID,
                                text=message,
                                parse_mode='HTML'
                            )
                    else:
                        await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message,
                            parse_mode='HTML'
                        )

                    self.db.mark_as_sent(offer['offer_id'], 1)
                    sent_count += 1

                    # Короткая задержка
                    await asyncio.sleep(1.5)

                except Exception as e:
                    print(f"Ошибка отправки: {e}")
                    continue

            await update.message.reply_text(
                f"✅ Готово! Найдено {result['total']} акций, отправлено {sent_count}"
            )

        except Exception as e:
            await update.message.reply_text(f"❌ Критическая ошибка: {e}")

    async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            import sqlite3
            conn = sqlite3.connect("lidl_offers.db")
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM offers")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT offer_id) FROM sent_offers")
            sent = cursor.fetchone()[0]

            # Последнее обновление
            cursor.execute("SELECT MAX(created_at) FROM offers")
            last_update = cursor.fetchone()[0]

            conn.close()

            stats_text = (
                f"📊 **Статистика бота:**\n"
                f"• Всего акций в базе: {total}\n"
                f"• Отправлено в канал: {sent}\n"
                f"• Последнее обновление: {last_update or 'Нет данных'}\n"
                f"• Текущее время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            await update.message.reply_text(stats_text)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            test_message = (
                "🔥 <b>ТЕСТ LIDL AKCIJA</b>\n\n"
                "🛍️ <b>Test proizvod</b>\n"
                "💰 <b>999 RSD</b>\n\n"
                "🛒 Lidl Serbia\n"
                "⏰ Парсинг в 7:00 ежедневно"
            )
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=test_message,
                parse_mode='HTML'
            )
            await update.message.reply_text("✅ Тест отправлен в канал!")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")

    def format_offer_message(self, offer):
        message = f"🔥 <b>LIDL AKCIJA</b>\n\n"
        message += f"🛍️ <b>{offer['name']}</b>\n"
        message += f"💰 <b>{offer['price']}</b>\n"

        if offer.get('category'):
            message += f"📦 {offer['category']}\n"

        message += f"\n🛒 Lidl Serbia\n"
        message += f"⏰ Обновление ежедневно в 7:00\n"
        message += f"#Lidl #Akcija"
        return message

    def is_valid_url(self, url):
        return url and url.startswith('http')

    def setup_scheduler(self):
        """Настройка планировщика для ежедневного парсинга в 7:00"""
        # Добавляем задание на каждый день в 7:00
        self.scheduler.add_job(
            self.daily_update,
            CronTrigger(hour=7, minute=0),  # 7:00 утра каждый день
            id='daily_7am'
        )

        self.scheduler.start()
        print("✅ Планировщик запущен: ежедневно в 7:00")

    async def daily_update(self):
        """Ежедневное автоматическое обновление в 7:00"""
        print(f"⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M')}] Запуск ежедневного парсинга...")

        try:
            result = self.parser.parse_offers()

            if not result["success"]:
                print(f"❌ Ошибка парсинга: {result['error']}")
                return

            print(f"✅ Найдено {result['total']} акций")

            # Сохраняем в базу
            self.db.save_offers(result["offers"])
            new_offers = self.db.get_new_offers()

            if not new_offers:
                print("ℹ️ Новых акций нет")
                return

            # Отправляем в канал
            bot = self.application.bot
            sent_count = 0

            for offer in new_offers[:15]:  # Ограничиваем количество
                try:
                    message = self.format_offer_message(offer)

                    if offer.get('image_url') and self.is_valid_url(offer['image_url']):
                        try:
                            await bot.send_photo(
                                chat_id=CHANNEL_ID,
                                photo=offer['image_url'],
                                caption=message,
                                parse_mode='HTML'
                            )
                        except:
                            await bot.send_message(
                                chat_id=CHANNEL_ID,
                                text=message,
                                parse_mode='HTML'
                            )
                    else:
                        await bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=message,
                            parse_mode='HTML'
                        )

                    self.db.mark_as_sent(offer['offer_id'], 1)
                    sent_count += 1
                    await asyncio.sleep(2)

                except Exception as e:
                    print(f"Ошибка отправки: {e}")
                    continue

            print(f"✅ Отправлено {sent_count} акций")

        except Exception as e:
            print(f"❌ Ошибка ежедневного обновления: {e}")

    def run(self):
        """Запуск бота"""
        print("🤖 Запуск бота Lidl акций...")
        print("⏰ Расписание: ежедневно в 7:00 утра")

        self.application = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики команд
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("update", self.update))
        self.application.add_handler(CommandHandler("stats", self.stats))
        self.application.add_handler(CommandHandler("test", self.test))
        self.application.add_handler(CommandHandler("schedule", self.schedule))

        # Настраиваем планировщик
        self.setup_scheduler()

        print("✅ Бот готов к работе")
        print("📅 Парсинг каждый день в 7:00 утра")
        print("🛑 Нажмите Ctrl+C для остановки")
        print("-" * 50)

        try:
            self.application.run_polling(drop_pending_updates=True)
        except KeyboardInterrupt:
            print("\n🛑 Остановлено пользователем")
            self.scheduler.shutdown()
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            self.scheduler.shutdown()


def main():
    bot = StableLidlBot()
    bot.run()


if __name__ == '__main__':
    main()

# # stable_bot.py
# from telegram import Update
# from telegram.ext import Application, CommandHandler, ContextTypes
# import logging
# import asyncio
# from datetime import datetime
#
# from config import BOT_TOKEN, CHANNEL_ID
# from fixed_parser import FixedLidlParser  # Используем исправленный парсер
# from database import Database
#
# # Минимальное логирование
# logging.basicConfig(level=logging.ERROR)
#
#
# class StableLidlBot:
#     def __init__(self):
#         self.parser = FixedLidlParser()
#         self.db = Database("lidl_offers.db")
#
#     async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         await update.message.reply_text(
#             "🤖 Бот Lidl акций работает!\n"
#             "Команды: /update, /stats, /test"
#         )
#
#     async def update(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         await update.message.reply_text("🔄 Начинаю парсинг...")
#
#         try:
#             # Парсим с обработкой ошибок
#             result = self.parser.parse_offers()
#
#             if not result["success"]:
#                 await update.message.reply_text(f"❌ Ошибка: {result['error']}")
#                 return
#
#             if result["total"] == 0:
#                 await update.message.reply_text("ℹ️ Акций не найдено")
#                 return
#
#             # Сохраняем в базу
#             self.db.save_offers(result["offers"])
#             new_offers = self.db.get_new_offers()
#
#             if not new_offers:
#                 await update.message.reply_text("ℹ️ Новых акций нет")
#                 return
#
#             # Отправляем акции
#             sent_count = 0
#             for offer in new_offers[:8]:  # Ограничиваем количество
#                 try:
#                     message = self.format_offer_message(offer)
#
#                     # Пытаемся отправить с фото
#                     if offer.get('image_url') and self.is_valid_url(offer['image_url']):
#                         try:
#                             await context.bot.send_photo(
#                                 chat_id=CHANNEL_ID,
#                                 photo=offer['image_url'],
#                                 caption=message,
#                                 parse_mode='HTML'
#                             )
#                         except:
#                             # Если фото не отправляется, отправляем текст
#                             await context.bot.send_message(
#                                 chat_id=CHANNEL_ID,
#                                 text=message,
#                                 parse_mode='HTML'
#                             )
#                     else:
#                         await context.bot.send_message(
#                             chat_id=CHANNEL_ID,
#                             text=message,
#                             parse_mode='HTML'
#                         )
#
#                     self.db.mark_as_sent(offer['offer_id'], 1)
#                     sent_count += 1
#
#                     # Короткая задержка
#                     await asyncio.sleep(1.5)
#
#                 except Exception as e:
#                     print(f"Ошибка отправки: {e}")
#                     continue
#
#             await update.message.reply_text(
#                 f"✅ Готово! Отправлено {sent_count} акций"
#             )
#
#         except Exception as e:
#             await update.message.reply_text(f"❌ Критическая ошибка: {e}")
#
#     async def stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         try:
#             import sqlite3
#             conn = sqlite3.connect("lidl_offers.db")
#             cursor = conn.cursor()
#
#             cursor.execute("SELECT COUNT(*) FROM offers")
#             total = cursor.fetchone()[0]
#
#             cursor.execute("SELECT COUNT(DISTINCT offer_id) FROM sent_offers")
#             sent = cursor.fetchone()[0]
#
#             conn.close()
#
#             await update.message.reply_text(
#                 f"📊 Статистика:\n"
#                 f"Акций в базе: {total}\n"
#                 f"Отправлено: {sent}\n"
#                 f"Время: {datetime.now().strftime('%H:%M')}"
#             )
#         except Exception as e:
#             await update.message.reply_text(f"❌ Ошибка: {e}")
#
#     async def test(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
#         try:
#             test_message = "🔥 <b>TEST LIDL AKCIJA</b>\n\nTest proizvod - 999 RSD\n\n🛒 Lidl Serbia"
#             await context.bot.send_message(
#                 chat_id=CHANNEL_ID,
#                 text=test_message,
#                 parse_mode='HTML'
#             )
#             await update.message.reply_text("✅ Тест отправлен!")
#         except Exception as e:
#             await update.message.reply_text(f"❌ Ошибка: {e}")
#
#     def format_offer_message(self, offer):
#         message = f"🔥 <b>LIDL AKCIJA</b>\n\n"
#         message += f"🛍️ <b>{offer['name']}</b>\n"
#         message += f"💰 <b>{offer['price']}</b>\n"
#
#         if offer.get('category'):
#             message += f"📦 {offer['category']}\n"
#
#         message += f"\n🛒 Lidl Serbia\n#Akcija"
#         return message
#
#     def is_valid_url(self, url):
#         return url and url.startswith('http')
#
#     def run(self):
#         """Запуск бота"""
#         print("🤖 Запуск стабильного бота...")
#
#         app = Application.builder().token(BOT_TOKEN).build()
#
#         app.add_handler(CommandHandler("start", self.start))
#         app.add_handler(CommandHandler("update", self.update))
#         app.add_handler(CommandHandler("stats", self.stats))
#         app.add_handler(CommandHandler("test", self.test))
#
#         print("✅ Бот готов к работе")
#         print("🛑 Нажмите Ctrl+C для остановки")
#
#         try:
#             app.run_polling(drop_pending_updates=True)
#         except KeyboardInterrupt:
#             print("\n🛑 Остановлено")
#         except Exception as e:
#             print(f"❌ Ошибка: {e}")
#
#
# def main():
#     bot = StableLidlBot()
#     bot.run()
#
#
# if __name__ == '__main__':
#     main()