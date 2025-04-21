import requests
import logging
import hashlib
import time
from datetime import datetime
from flask import current_app
from models import Mention, Settings, Keyword, db
from utils import save_log

def search_vk(project_id, community_id, keywords, start_date=None, end_date=None):
    """
    Search for mentions in VK community posts or across all VK
    
    Args:
        project_id (int): Project ID
        community_id (str): VK community ID (может быть пустым для поиска по всему ВК)
        keywords (list): List of keywords to search for
        start_date (datetime): Start date for search
        end_date (datetime): End date for search
    """
    # Get VK API token
    settings = Settings.query.filter_by(project_id=project_id).first()
    if not settings or not settings.vk_token:
        save_log(f"VK API token not found for project {project_id}", level="ERROR")
        raise ValueError("ВК API токен не найден")
    
    try:
        vk_token = settings.vk_token
        found_count = 0
        
        # Если community_id не указан или пуст, ищем по всему ВК через newsfeed.search
        if not community_id or community_id.strip() == '':
            save_log(f"Поиск по всему ВКонтакте для ключевых слов: {', '.join(keywords)}", level="INFO")
            
            for keyword in keywords:
                # Параметры API для поиска по всей ленте новостей
                api_url = "https://api.vk.com/method/newsfeed.search"
                params = {
                    "q": keyword,
                    "count": 100,  # Запрашиваем до 100 постов
                    "access_token": vk_token,
                    "v": "5.131"  # Версия API
                }
                
                # Добавляем параметры даты если указаны
                if start_date:
                    params["start_time"] = int(start_date.timestamp())
                if end_date:
                    params["end_time"] = int(end_date.timestamp())
                
                response = requests.get(api_url, params=params)
                data = response.json()
                
                if 'error' in data:
                    error_msg = f"ВК API ошибка: {data['error']['error_msg']}"
                    save_log(error_msg, level="ERROR")
                    raise ValueError(error_msg)
                
                if 'response' not in data or 'items' not in data['response']:
                    save_log(f"Неожиданная структура ответа ВК API", level="ERROR")
                    continue
                
                # Обрабатываем найденные посты
                for post in data['response']['items']:
                    post_text = post.get('text', '')
                    
                    # Проверяем, содержит ли пост ключевое слово
                    if keyword.lower() in post_text.lower():
                        # Проверяем, есть ли уже это упоминание
                        existing = Mention.query.filter_by(
                            project_id=project_id,
                            social_network='vk',
                            author_id=str(post.get('from_id', post.get('owner_id'))),
                            post_url=f"https://vk.com/wall{post['owner_id']}_{post['id']}"
                        ).first()
                        
                        if not existing:
                            # Создаем новое упоминание
                            mention = Mention(
                                project_id=project_id,
                                social_network='vk',
                                content=post_text,
                                post_url=f"https://vk.com/wall{post['owner_id']}_{post['id']}",
                                post_date=datetime.fromtimestamp(post['date']),
                                author_id=str(post.get('from_id', post.get('owner_id'))),
                                author_name="Пользователь VK"  # Для детального имени нужен доп. запрос
                            )
                            db.session.add(mention)
                            found_count += 1
        else:
            # Поиск по конкретному сообществу
            save_log(f"Поиск по сообществу VK {community_id} для ключевых слов: {', '.join(keywords)}", level="INFO")
            
            # Make sure community_id starts with "-" for groups
            if not community_id.startswith('-') and community_id.isdigit():
                community_id = f"-{community_id}"
            
            # Use VK API to get wall posts
            api_url = "https://api.vk.com/method/wall.get"
            params = {
                "owner_id": community_id,
                "count": 100,  # Get up to 100 posts
                "access_token": vk_token,
                "v": "5.131"  # API version
            }
            
            response = requests.get(api_url, params=params)
            data = response.json()
            
            if 'error' in data:
                error_msg = f"ВК API ошибка: {data['error']['error_msg']}"
                save_log(error_msg, level="ERROR")
                raise ValueError(error_msg)
            
            if 'response' not in data or 'items' not in data['response']:
                save_log(f"Неожиданная структура ответа ВК API", level="ERROR")
                raise ValueError("Неожиданная структура ответа ВК API")
            
            # Process the posts
            for post in data['response']['items']:
                post_text = post.get('text', '')
                post_date = datetime.fromtimestamp(post['date'])
                
                # Фильтруем по дате, если указаны даты
                if (start_date and post_date < start_date) or (end_date and post_date > end_date):
                    continue
                
                # Check if post contains any of the keywords
                for keyword in keywords:
                    if keyword.lower() in post_text.lower():
                        # Check if we already have this mention
                        existing = Mention.query.filter_by(
                            project_id=project_id,
                            social_network='vk',
                            author_id=str(post.get('from_id', post.get('owner_id'))),
                            post_url=f"https://vk.com/wall{post['owner_id']}_{post['id']}"
                        ).first()
                        
                        if not existing:
                            # Create new mention
                            mention = Mention(
                                project_id=project_id,
                                social_network='vk',
                                content=post_text,
                                post_url=f"https://vk.com/wall{post['owner_id']}_{post['id']}",
                                post_date=post_date,
                                author_id=str(post.get('from_id', post.get('owner_id'))),
                                author_name="Пользователь VK"  # Would need additional API call to get name
                            )
                            db.session.add(mention)
                            found_count += 1
                        
                        break  # No need to check other keywords for this post
        
        # Commit all new mentions
        if found_count > 0:
            db.session.commit()
            save_log(f"Найдено {found_count} новых упоминаний в ВКонтакте")
        else:
            save_log(f"Новых упоминаний не найдено в ВКонтакте")
        
        return found_count
    
    except Exception as e:
        save_log(f"Ошибка во время поиска ВК: {str(e)}", level="ERROR")
        raise

def search_ok(project_id, community_id, keywords, start_date=None, end_date=None):
    """
    Search for mentions in Odnoklassniki community posts
    
    Args:
        project_id (int): Project ID
        community_id (str): OK community ID
        keywords (list): List of keywords to search for
        start_date (datetime): Start date for search
        end_date (datetime): End date for search
    """
    # Get OK API credentials
    settings = Settings.query.filter_by(project_id=project_id).first()
    if (not settings or not settings.ok_token or 
        not settings.ok_public_key or not settings.ok_private_key):
        save_log(f"OK API credentials not found for project {project_id}", level="ERROR")
        raise ValueError("OK API credentials not found")
    
    try:
        ok_token = settings.ok_token
        ok_public_key = settings.ok_public_key
        ok_private_key = settings.ok_private_key
        
        # Use OK API to get group posts
        api_url = "https://api.ok.ru/fb.do"
        
        # Prepare parameters
        method = "group.getDiscussions"
        application_key = ok_public_key
        
        # Generate signature
        sig_params = {
            "application_key": application_key,
            "format": "json",
            "method": method,
            "gid": community_id,
            "count": "100"  # Get up to 100 discussions
        }
        
        # Sort parameters alphabetically by key
        sorted_params = sorted(sig_params.items(), key=lambda x: x[0])
        
        # Create sig string
        sig_string = "".join([f"{k}={v}" for k, v in sorted_params])
        sig_string += ok_private_key
        
        # MD5 hash
        sig = hashlib.md5(sig_string.encode('utf-8')).hexdigest().lower()
        
        # Final parameters
        params = {
            "application_key": application_key,
            "format": "json",
            "method": method,
            "gid": community_id,
            "count": "100",  # Get up to 100 discussions
            "access_token": ok_token,
            "sig": sig
        }
        
        response = requests.get(api_url, params=params)
        data = response.json()
        
        if 'error_code' in data:
            error_msg = f"OK API error: {data.get('error_msg', data['error_code'])}"
            save_log(error_msg, level="ERROR")
            raise ValueError(error_msg)
        
        # Process the posts
        found_count = 0
        discussions = data.get('discussions', [])
        
        # Log the response for debugging
        save_log(f"OK API response: found {len(discussions)} discussions", level="INFO")
        
        for discussion in discussions:
            # Extract the text content from the discussion
            discussion_text = discussion.get('title', '') + ' ' + discussion.get('description', '')
            
            # Check if post contains any of the keywords
            for keyword in keywords:
                if keyword.lower() in discussion_text.lower():
                    # Check if we already have this mention
                    topic_id = discussion.get('id', '')
                    author_id = discussion.get('author_uid', '')
                    
                    existing = Mention.query.filter_by(
                        project_id=project_id,
                        social_network='ok',
                        author_id=author_id,
                        post_url=f"https://ok.ru/group/{community_id}/topic/{topic_id}"
                    ).first()
                    
                    if not existing:
                        # Create new mention
                        mention = Mention(
                            project_id=project_id,
                            social_network='ok',
                            content=discussion_text,
                            post_url=f"https://ok.ru/group/{community_id}/topic/{topic_id}",
                            post_date=datetime.fromtimestamp(int(discussion.get('creation_date', time.time()))/1000),
                            author_id=author_id,
                            author_name=discussion.get('author_name', 'OK User')
                        )
                        db.session.add(mention)
                        found_count += 1
                    
                    break  # No need to check other keywords for this post
        
        # Commit all new mentions
        if found_count > 0:
            db.session.commit()
            save_log(f"Found {found_count} new mentions in OK community {community_id}")
        else:
            save_log(f"No new mentions found in OK community {community_id}")
        
        return found_count
    
    except Exception as e:
        save_log(f"Error during OK search: {str(e)}", level="ERROR")
        raise
