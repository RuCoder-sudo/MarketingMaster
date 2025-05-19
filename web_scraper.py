import trafilatura
import requests
import logging
from bs4 import BeautifulSoup
import time
import random
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_website_text_content(url: str) -> str:
    """
    Извлекает основной текстовый контент с веб-страницы.
    
    Args:
        url (str): URL веб-страницы для анализа
        
    Returns:
        str: Извлеченный текстовый контент
    """
    try:
        # Добавляем user-agent для имитации браузера
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Отправляем запрос к сайту
        downloaded = trafilatura.fetch_url(url, headers=headers)
        
        if not downloaded:
            logger.warning(f"Не удалось загрузить содержимое с URL: {url}")
            return ""
        
        # Извлекаем текст с помощью trafilatura
        text = trafilatura.extract(downloaded)
        
        if not text:
            logger.warning(f"Не удалось извлечь текст с URL: {url}")
            return ""
        
        return text
    
    except Exception as e:
        logger.error(f"Ошибка при извлечении текста с {url}: {str(e)}")
        return ""

def search_kwork(keyword, max_pages=3):
    """
    Осуществляет поиск проектов на Kwork.ru по ключевому слову.
    
    Args:
        keyword (str): Ключевое слово для поиска
        max_pages (int, optional): Максимальное количество страниц для поиска. По умолчанию 3.
        
    Returns:
        list: Список найденных проектов в формате словарей
    """
    results = []
    
    try:
        for page in range(1, max_pages + 1):
            # Формируем URL запроса
            search_url = f"https://kwork.ru/projects?c=41&page={page}&q={keyword}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
            }
            
            # Отправляем запрос
            response = requests.get(search_url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"Не удалось получить страницу {page} с Kwork. Код ответа: {response.status_code}")
                continue
            
            # Парсим HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Найти проекты на странице
            project_blocks = soup.select('.wants-card')
            
            if not project_blocks:
                logger.warning(f"Не найдено проектов на странице {page}")
                break
            
            for block in project_blocks:
                try:
                    # Извлекаем основную информацию
                    title_element = block.select_one('.wants-card__header-title')
                    description_element = block.select_one('.wants-card__description')
                    price_element = block.select_one('.wants-card__header-price')
                    date_element = block.select_one('.wt-break-word time')
                    link_element = block.select_one('.wants-card__header-title a')
                    
                    if not all([title_element, description_element, link_element]):
                        continue
                    
                    title = title_element.get_text(strip=True)
                    description = description_element.get_text(strip=True)
                    price = price_element.get_text(strip=True) if price_element else "Цена не указана"
                    date_text = date_element.get_text(strip=True) if date_element else ""
                    project_url = "https://kwork.ru" + link_element['href'] if link_element and 'href' in link_element.attrs else ""
                    
                    # Получаем ID проекта из URL
                    project_id = project_url.split('/')[-1] if project_url else None
                    
                    # Преобразуем относительную дату в абсолютную
                    post_date = datetime.now()  # По умолчанию текущая дата
                    if "час" in date_text:
                        hours = int(''.join(filter(str.isdigit, date_text)) or 1)
                        post_date = datetime.now().replace(hour=datetime.now().hour - hours)
                    elif "день" in date_text or "дня" in date_text or "дней" in date_text:
                        days = int(''.join(filter(str.isdigit, date_text)) or 1)
                        post_date = datetime.now().replace(day=datetime.now().day - days)
                    
                    # Формируем запись о проекте
                    project = {
                        'id': project_id,
                        'title': title,
                        'description': description,
                        'price': price,
                        'post_date': post_date,
                        'post_url': project_url,
                        'social_network': 'kwork.ru'
                    }
                    
                    results.append(project)
                except Exception as e:
                    logger.error(f"Ошибка при обработке проекта: {str(e)}")
                    continue
            
            # Делаем паузу между запросами, чтобы не нагружать сервер
            if page < max_pages:
                time.sleep(random.uniform(1.0, 3.0))
    
    except Exception as e:
        logger.error(f"Ошибка при поиске на Kwork: {str(e)}")
    
    return results

def convert_kwork_results_to_mentions(project_id, results):
    """
    Преобразует результаты поиска с Kwork в объекты упоминаний.
    
    Args:
        project_id (int): ID проекта
        results (list): Список результатов с Kwork
        
    Returns:
        list: Список упоминаний в формате для базы данных
    """
    from models import Mention
    from app import db
    
    mentions = []
    
    for result in results:
        try:
            mention = Mention(
                project_id=project_id,
                social_network='kwork.ru',
                content=f"{result['title']}\n\n{result['description']}",
                post_url=result['post_url'],
                post_date=result['post_date'],
                author_id=None,
                author_name="Заказчик на Kwork",
                channel_name="Kwork Проекты",
                found_date=datetime.now()
            )
            mentions.append(mention)
        except Exception as e:
            logger.error(f"Ошибка при создании объекта упоминания: {str(e)}")
    
    return mentions

if __name__ == "__main__":
    # Тестовый запуск
    results = search_kwork("разработка сайта")
    for i, result in enumerate(results, 1):
        print(f"Результат {i}:")
        print(f"Название: {result['title']}")
        print(f"Описание: {result['description'][:100]}...")
        print(f"Цена: {result['price']}")
        print(f"URL: {result['post_url']}")
        print("-" * 50)