# config.py
import os
from datetime import time

# Токен бота Telegram (получить у @BotFather)
BOT_TOKEN = "8304679501:AAFqZNub_-_-IizYQkDhCJP3H9_aRAPVDXc"

# ID канала (например, @your_channel -> -1001234567890)
CHANNEL_ID = "@temu_best_discounts"  # или числовой ID: -1001234567890

# Парсинг 1 раз в день в 7:00 утра
NOTIFICATION_TIMES = [
    time(7, 0)   # 7:00 утра
]

# Настройки базы данных
DB_PATH = "lidl_offers.db"
