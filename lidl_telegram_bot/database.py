import sqlite3
import json
from datetime import datetime


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id TEXT UNIQUE,
                name TEXT NOT NULL,
                price TEXT,
                old_price TEXT,
                category TEXT,
                image_url TEXT,
                valid_from TEXT,
                valid_to TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id TEXT,
                message_id INTEGER,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def save_offers(self, offers):
        """Сохранение акций в базу данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for offer in offers:
            cursor.execute('''
                INSERT OR REPLACE INTO offers 
                (offer_id, name, price, old_price, category, image_url, valid_from, valid_to, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                offer.get('offer_id'),
                offer.get('name'),
                offer.get('price'),
                offer.get('old_price'),
                offer.get('category'),
                offer.get('image_url'),
                offer.get('valid_from'),
                offer.get('valid_to'),
                True
            ))

        conn.commit()
        conn.close()

    # database.py - добавьте эти методы в класс Database

    def get_total_offers_count(self):
        """Получение общего количества акций в базе"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM offers")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_sent_offers_count(self):
        """Получение количества отправленных акций"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT offer_id) FROM sent_offers")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_new_offers(self):
        """Получение новых акций, которые еще не отправлялись"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT o.* FROM offers o
            LEFT JOIN sent_offers s ON o.offer_id = s.offer_id
            WHERE s.offer_id IS NULL AND o.is_active = TRUE
            ORDER BY o.created_at DESC
        ''')

        offers = []
        for row in cursor.fetchall():
            offers.append({
                'offer_id': row[1],
                'name': row[2],
                'price': row[3],
                'old_price': row[4],
                'category': row[5],
                'image_url': row[6],
                'valid_from': row[7],
                'valid_to': row[8]
            })

        conn.close()
        return offers

    def mark_as_sent(self, offer_id, message_id):
        """Помечаем акцию как отправленную"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO sent_offers (offer_id, message_id)
            VALUES (?, ?)
        ''', (offer_id, message_id))

        conn.commit()
        conn.close()