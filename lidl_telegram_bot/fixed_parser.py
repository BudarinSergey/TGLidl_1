# fixed_parser.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import re
import json
from datetime import datetime
import hashlib
from urllib.parse import urljoin


class FixedLidlParser:
    def __init__(self):
        self.driver = None

    def setup_driver(self):
        """Настройка и запуск WebDriver"""
        try:
            if self.driver:
                self.driver.quit()

            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--log-level=3")  # Убираем логи Selenium

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска WebDriver: {e}")
            return False

    def parse_offers(self):
        """Парсинг акций"""
        try:
            print("🔄 Запуск парсера...")

            # Запускаем драйвер
            if not self.setup_driver():
                return {"success": False, "error": "Не удалось запустить браузер"}

            self.driver.get("https://www.lidl.rs")
            time.sleep(5)

            # Прокрутка
            self.scroll_page()

            offers = []
            offers.extend(self.extract_data_from_images())

            # Закрываем драйвер сразу после использования
            self.driver.quit()
            self.driver = None

            valid_offers = [offer for offer in offers if self.validate_offer(offer)]
            unique_offers = self.remove_duplicates(valid_offers)

            print(f"✅ Найдено предложений: {len(unique_offers)}")

            return {
                "success": True,
                "offers": unique_offers,
                "total": len(unique_offers),
                "parsed_at": datetime.now().isoformat()
            }

        except Exception as e:
            # Всегда закрываем драйвер при ошибке
            if self.driver:
                self.driver.quit()
                self.driver = None
            return {"success": False, "error": str(e)}

    def scroll_page(self):
        """Прокрутка страницы"""
        for i in range(2):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

    def extract_data_from_images(self):
        """Извлечение данных из изображений"""
        offers = []

        try:
            images = self.driver.find_elements(By.TAG_NAME, "img")
            print(f"📷 Всего изображений: {len(images)}")

            for img in images:
                try:
                    alt_text = img.get_attribute('alt') or ''
                    src = img.get_attribute('src') or ''

                    if 'ceni' in alt_text.lower() or 'price' in alt_text.lower():
                        offer_data = self.parse_alt_text(alt_text, src)
                        if offer_data:
                            offers.append(offer_data)
                            print(f"✅ Найдена акция: {offer_data['name']}")

                except:
                    continue

        except Exception as e:
            print(f"Ошибка извлечения изображений: {e}")

        return offers

    def parse_alt_text(self, alt_text, image_src):
        """Парсим текст из атрибута alt"""
        try:
            # Ищем цену
            price_match = re.search(r'(\d+[.,]\d{2,3})', alt_text)
            if not price_match:
                return None

            price = price_match.group(1).replace(',', '.')

            # Извлекаем название
            name = self.extract_product_name(alt_text)
            if not name:
                return None

            # Обрабатываем URL изображения
            if image_src.startswith('/'):
                image_url = urljoin('https://www.lidl.rs', image_src)
            else:
                image_url = image_src

            offer_id = hashlib.md5(f"{name}_{price}".encode()).hexdigest()

            return {
                'offer_id': offer_id,
                'name': name,
                'price': f"{price} RSD",
                'image_url': image_url,
                'category': self.detect_category(name),
                'source': 'image_alt'
            }

        except:
            return None

    def extract_product_name(self, alt_text):
        """Извлекаем название продукта"""
        # Удаляем цену и техническую информацию
        text = re.sub(r'po ceni od[\s\d.,]+', '', alt_text, flags=re.IGNORECASE)
        text = re.sub(r'[\d.,]+\s*(RSD|дин|din|€)?', '', text)
        text = re.sub(r',\s*\d+g|\d+ml|\d+kg', '', text)
        text = text.replace(',', '').strip()

        # Удаляем лишние слова
        words = [word for word in text.split() if word.lower() not in ['sa', 'od', 'po', 'za']]
        name = ' '.join(words)

        return name if len(name) > 2 else None

    def detect_category(self, product_name):
        name_lower = product_name.lower()
        categories = {
            'mleko': 'Mlečni proizvodi',
            'sir': 'Mlečni proizvodi',
            'maslac': 'Mlečni proizvodi',
            'jogurt': 'Mlečni proizvodi',
            'meso': 'Meso',
            'kobasica': 'Meso',
            'sunka': 'Meso',
            'riba': 'Riba',
            'hleb': 'Pekara',
            'voce': 'Voće',
            'povrce': 'Povrće',
            'kafa': 'Piće',
            'sok': 'Piće'
        }

        for keyword, category in categories.items():
            if keyword in name_lower:
                return category

        return 'Ostalo'

    def validate_offer(self, offer):
        return (offer.get('name') and
                offer.get('price') and
                len(offer['name']) > 2)

    def remove_duplicates(self, offers):
        seen = set()
        unique_offers = []

        for offer in offers:
            identifier = (offer['name'].lower().strip(), offer['price'])
            if identifier not in seen:
                seen.add(identifier)
                unique_offers.append(offer)

        return unique_offers

    def __del__(self):
        """Деструктор - закрываем драйвер при удалении объекта"""
        if self.driver:
            self.driver.quit()