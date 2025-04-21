import requests
import logging
import hashlib
import time
import json
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
        
def search_telegram(project_id, keywords, start_date=None, end_date=None):
    """
    Search for mentions in Telegram channels/groups
    
    Args:
        project_id (int): Project ID
        keywords (list): List of keywords to search for
        start_date (datetime): Start date for search
        end_date (datetime): End date for search
        
    Returns:
        int: Number of new mentions found
    """
    # Get Telegram API credentials
    settings = Settings.query.filter_by(project_id=project_id).first()
    if not settings or not settings.telegram_token:
        save_log(f"Telegram API token not found for project {project_id}", level="ERROR")
        raise ValueError("Telegram API token not found")
    
    # Check if there are channels to monitor
    if not settings.telegram_channels:
        save_log(f"No Telegram channels configured for project {project_id}", level="WARNING")
        return 0
    
    try:
        telegram_token = settings.telegram_token
        found_count = 0
        
        # Get channels list (comma-separated)
        channels = [c.strip() for c in settings.telegram_channels.split(",") if c.strip()]
        
        save_log(f"Searching Telegram channels: {', '.join(channels)} for keywords: {', '.join(keywords)}", level="INFO")
        
        # For each channel
        for channel in channels:
            # Remove @ if present
            if channel.startswith('@'):
                channel = channel[1:]
            
            # Base URL for Telegram Bot API
            api_base = f"https://api.telegram.org/bot{telegram_token}"
            
            try:
                # 1. Get chat info
                response = requests.get(f"{api_base}/getChat", params={"chat_id": f"@{channel}"})
                data = response.json()
                
                if not data.get("ok"):
                    save_log(f"Error getting Telegram channel info for {channel}: {data.get('description', 'Unknown error')}", level="ERROR")
                    continue
                
                chat = data.get("result", {})
                chat_id = chat.get("id")
                chat_title = chat.get("title", channel)
                
                save_log(f"Found Telegram channel: {chat_title} (ID: {chat_id})", level="INFO")
                
                # 2. Get messages from the channel
                # Note: This is a simplified approach. Telegram Bot API has limitations on
                # retrieving messages from channels/groups. In a production environment,
                # you might need to use the Telegram API (not Bot API) or a Telegram client library.
                
                # Using getUpdates as a simple way to get recent messages
                # This will only work for new messages after the bot is added to the channel
                response = requests.get(f"{api_base}/getUpdates")
                updates = response.json()
                
                if not updates.get("ok"):
                    save_log(f"Error getting Telegram updates: {updates.get('description', 'Unknown error')}", level="ERROR")
                    continue
                
                # Process all updates (messages)
                for update in updates.get("result", []):
                    # Check if this is a channel post
                    if "channel_post" not in update:
                        continue
                    
                    message = update["channel_post"]
                    message_chat_id = message.get("chat", {}).get("id")
                    
                    # Skip if not from our target channel
                    if message_chat_id != chat_id:
                        continue
                    
                    # Skip if no text
                    text = message.get("text", "")
                    if not text:
                        continue
                    
                    # Get message date
                    message_date = datetime.fromtimestamp(message.get("date", int(time.time())))
                    
                    # Skip if outside date range
                    if start_date and message_date < start_date:
                        continue
                    if end_date and message_date > end_date:
                        continue
                    
                    # Check if message contains any of the keywords
                    for keyword in keywords:
                        if keyword.lower() in text.lower():
                            # Check if this message is already in the database
                            message_id = message.get("message_id", "")
                            
                            existing = Mention.query.filter_by(
                                project_id=project_id,
                                social_network="telegram",
                                chat_id=str(chat_id),
                                message_id=str(message_id)
                            ).first()
                            
                            if not existing:
                                # Create a new mention
                                mention = Mention(
                                    project_id=project_id,
                                    social_network="telegram",
                                    content=text,
                                    post_url=f"https://t.me/{channel}/{message_id}" if message_id else f"https://t.me/{channel}",
                                    post_date=message_date,
                                    channel_name=chat_title,
                                    chat_id=str(chat_id),
                                    message_id=str(message_id)
                                )
                                
                                db.session.add(mention)
                                found_count += 1
                            
                            break  # No need to check other keywords for this message
            
            except Exception as e:
                save_log(f"Error processing Telegram channel {channel}: {str(e)}", level="ERROR")
                # Continue with other channels
        
        # Commit all new mentions
        if found_count > 0:
            db.session.commit()
            save_log(f"Found {found_count} new mentions in Telegram channels", level="INFO")
        else:
            save_log(f"No new mentions found in Telegram channels", level="INFO")
        
        return found_count
    
    except Exception as e:
        db.session.rollback()
        save_log(f"Error during Telegram search: {str(e)}", level="ERROR")
        raise
        
def search_instagram(project_id, keywords, start_date=None, end_date=None):
    """
    Search for mentions in Instagram posts
    
    Args:
        project_id (int): Project ID
        keywords (list): List of keywords to search for
        start_date (datetime): Start date for search
        end_date (datetime): End date for search
        
    Returns:
        int: Number of new mentions found
    """
    # Get Instagram API credentials
    settings = Settings.query.filter_by(project_id=project_id).first()
    if not settings or not settings.instagram_token:
        save_log(f"Instagram API token not found for project {project_id}", level="ERROR")
        raise ValueError("Instagram API token not found")
    
    # Check if there are accounts to monitor
    if not settings.instagram_accounts:
        save_log(f"No Instagram accounts configured for project {project_id}", level="WARNING")
        return 0
    
    try:
        instagram_token = settings.instagram_token
        found_count = 0
        
        # Get accounts list (comma-separated)
        accounts = [a.strip() for a in settings.instagram_accounts.split(",") if a.strip()]
        
        save_log(f"Searching Instagram accounts: {', '.join(accounts)} for keywords: {', '.join(keywords)}", level="INFO")
        
        # For each account
        for account in accounts:
            try:
                # Base URL for Instagram Graph API
                graph_api_base = "https://graph.instagram.com/v17.0"
                
                # 1. Get account info (will need the actual user ID first)
                # This is a simplified example - in reality, the proper flow would include:
                # - Get the page ID from the Facebook Page associated with the Instagram account
                # - Get the Instagram Business Account ID
                # - Use that ID to get media
                
                # For this example, we'll use a simplified approach that assumes we already have
                # the Instagram Business Account ID in the 'account' variable
                
                # Get user's media
                response = requests.get(
                    f"{graph_api_base}/me/media",
                    params={
                        "fields": "id,caption,media_type,media_url,permalink,timestamp",
                        "access_token": instagram_token
                    }
                )
                data = response.json()
                
                if "error" in data:
                    error_message = data.get("error", {}).get("message", "Unknown error")
                    save_log(f"Error fetching Instagram media for {account}: {error_message}", level="ERROR")
                    continue
                
                media_items = data.get("data", [])
                
                for media in media_items:
                    # Get info from media
                    media_id = media.get("id")
                    caption = media.get("caption", "")
                    permalink = media.get("permalink", "")
                    media_type = media.get("media_type", "")
                    
                    # Skip if no caption
                    if not caption:
                        continue
                    
                    # Get post date
                    timestamp_str = media.get("timestamp")
                    post_date = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")) if timestamp_str else datetime.now()
                    
                    # Skip if outside date range
                    if start_date and post_date < start_date:
                        continue
                    if end_date and post_date > end_date:
                        continue
                    
                    # Check if post contains any of the keywords
                    for keyword in keywords:
                        if keyword.lower() in caption.lower():
                            # Check if this post is already in the database
                            existing = Mention.query.filter_by(
                                project_id=project_id,
                                social_network="instagram",
                                author_id=account,
                                message_id=str(media_id)
                            ).first()
                            
                            if not existing:
                                # Create a new mention
                                mention = Mention(
                                    project_id=project_id,
                                    social_network="instagram",
                                    content=caption,
                                    post_url=permalink,
                                    post_date=post_date,
                                    author_id=account,
                                    author_name=account,
                                    message_id=str(media_id)
                                )
                                
                                db.session.add(mention)
                                found_count += 1
                            
                            break  # No need to check other keywords for this post
                    
            except Exception as e:
                save_log(f"Error processing Instagram account {account}: {str(e)}", level="ERROR")
                # Continue with other accounts
        
        # Commit all new mentions
        if found_count > 0:
            db.session.commit()
            save_log(f"Found {found_count} new mentions in Instagram accounts", level="INFO")
        else:
            save_log(f"No new mentions found in Instagram accounts", level="INFO")
        
        return found_count
    
    except Exception as e:
        db.session.rollback()
        save_log(f"Error during Instagram search: {str(e)}", level="ERROR")
        raise
