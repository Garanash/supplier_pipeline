import requests
from bs4 import BeautifulSoup
import whois
from datetime import datetime
import re
import aiosqlite
from typing import List, Dict, Optional
import asyncio

# Список агрегаторов, которые нужно игнорировать
AGGREGATORS = [
    'alibaba.com', 'ebay.com', 'amazon.com', 'walmart.com',
    'aliexpress.com', 'globalsources.com', 'made-in-china.com',
    'tradekey.com', 'ec21.com', 'dhgate.com'
]

# Регионы для поиска с соответствующими доменами Google
REGIONS = {
    'europe': 'google.de',  # Германия как центральная Европа
    'north_america': 'google.com',
    'south_america': 'google.com.br',  # Бразилия
    'russia': 'google.ru',
    'asia': 'google.co.jp'  # Япония
}


async def search_suppliers(article_code: str, min_suppliers: int = 7) -> List[Dict]:
    """Поиск поставщиков по артикулу в разных регионах"""
    suppliers = []
    tasks = []

    # Создаем задачи для каждого региона
    for region, domain in REGIONS.items():
        task = asyncio.create_task(search_in_region(article_code, domain, region))
        tasks.append(task)

    # Ждем завершения всех задач
    results = await asyncio.gather(*tasks)

    # Собираем всех поставщиков
    for region_suppliers in results:
        suppliers.extend(region_suppliers)

    # Удаляем дубликаты
    unique_suppliers = []
    seen_websites = set()

    for supplier in suppliers:
        if supplier['website'] not in seen_websites:
            seen_websites.add(supplier['website'])
            unique_suppliers.append(supplier)

    return unique_suppliers[:min_suppliers]


async def search_in_region(article_code: str, google_domain: str, region: str) -> List[Dict]:
    """Поиск поставщиков в конкретном регионе"""
    suppliers = []
    search_query = f"{article_code} supplier -site:{' -site:'.join(AGGREGATORS)}"
    url = f"https://{google_domain}/search?q={search_query}&num=10"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        results = soup.find_all('div', class_='g')

        for result in results[:10]:  # Ограничиваем первые 10 результатов
            link = result.find('a')
            if not link:
                continue

            website_url = link['href']
            if not website_url.startswith('http'):
                continue

            # Извлекаем домен
            domain = extract_domain(website_url)
            if not domain or any(agg in domain for agg in AGGREGATORS):
                continue

            # Получаем название компании из заголовка
            title = result.find('h3')
            company_name = title.text if title else domain

            # Получаем информацию WHOIS
            whois_info = await get_whois_info(domain)
            country = whois_info.get('country', 'Unknown')
            email = await extract_contact_email(website_url) if whois_info else None

            suppliers.append({
                'name': company_name,
                'website': website_url,
                'email': email,
                'country': country,
                'region': region
            })

    except Exception as e:
        print(f"Error searching in {google_domain}: {e}")

    return suppliers


async def get_whois_info(domain: str) -> Dict:
    """Получение информации WHOIS о домене"""
    try:
        info = whois.whois(domain)
        return {
            'country': info.country if isinstance(info.country, str) else info.country[
                0] if info.country else 'Unknown',
            'emails': info.emails if hasattr(info, 'emails') else None
        }
    except Exception as e:
        print(f"Error getting WHOIS info for {domain}: {e}")
        return {}


async def extract_contact_email(website_url: str) -> Optional[str]:
    """Извлечение email с веб-сайта"""
    try:
        response = requests.get(website_url, timeout=10)
        response.raise_for_status()

        # Ищем email в тексте страницы
        email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_regex, response.text)

        # Фильтруем служебные email
        for email in emails:
            if not any(word in email.lower() for word in ['noreply', 'no-reply', 'support', 'info']):
                return email

        return None
    except Exception as e:
        print(f"Error extracting email from {website_url}: {e}")
        return None


def extract_domain(url: str) -> Optional[str]:
    """Извлечение домена из URL"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc
        return None
    except Exception:
        return None