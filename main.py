import requests


def check_site_availability():
    base_url = "https://www.lidl.rs"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(base_url, headers=headers, timeout=10)
        print(f"Статус главной страницы: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка доступа к сайту: {e}")
        return False


if check_site_availability():
    print("Сайт доступен, ищем API...")
else:
    print("Сайт не доступен")

from bs4 import BeautifulSoup
import requests


def parse_lidl_offers_directly():
    """Прямой парсинг HTML страницы с акциями"""
    url = "https://www.lidl.rs"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Ищем разделы с акциями (адаптируйте селекторы под конкретный сайт)
            offers = []

            # Попробуем разные возможные селекторы
            selectors_to_try = [
                '.product-grid',
                '.offers-grid',
                '[class*="product"]',
                '[class*="offer"]',
                '.promotion',
                '.item'
            ]

            for selector in selectors_to_try:
                elements = soup.select(selector)
                if elements:
                    print(f"Найдены элементы с селектором: {selector}")
                    print(f"Количество: {len(elements)}")

                    # Покажем первые 3 элемента для примера
                    for i, element in enumerate(elements[:3]):
                        print(f"Элемент {i + 1}:")
                        print(element.get_text(strip=True)[:100] + "...")
                        print("---")

            # Ищем ссылки на акции
            offer_links = soup.find_all('a', href=True)
            offer_urls = [link['href'] for link in offer_links if
                          any(keyword in link['href'].lower() for keyword in ['akcij', 'offer', 'promo', 'action'])]

            print("Найдены ссылки на акции:")
            for offer_url in offer_urls[:5]:
                if offer_url.startswith('/'):
                    full_url = url + offer_url
                else:
                    full_url = offer_url
                print(f"  - {full_url}")

    except Exception as e:
        print(f"Ошибка при парсинге: {e}")


# Запускаем поиск
parse_lidl_offers_directly()
