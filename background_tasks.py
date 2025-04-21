import threading
import time
import logging
from datetime import datetime, timedelta
from flask import current_app

class BackgroundSearcher:
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 3600  # Default: 1 hour
    
    def is_running(self):
        """Check if background search is running"""
        return self.running and self.thread and self.thread.is_alive()
    
    def start_search(self, project_id, interval=None):
        """
        Start background search thread for a project
        
        Args:
            project_id (int): Project ID
            interval (int, optional): Search interval in seconds
        """
        # Don't start if already running
        if self.is_running():
            return False
        
        # Set interval if provided
        if interval:
            self.interval = interval
        
        # Set running flag and start thread
        self.running = True
        self.thread = threading.Thread(
            target=self._search_loop,
            args=(project_id,),
            daemon=True  # Daemon threads exit when the main program exits
        )
        self.thread.start()
        return True
    
    def stop_search(self):
        """Stop background search"""
        self.running = False
        # Thread will exit on next loop iteration when it checks self.running
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)  # Wait up to 1 second for thread to exit
        return True
    
    def _search_loop(self, project_id):
        """
        Background search loop
        
        Args:
            project_id (int): Project ID
        """
        from social_api import search_vk, search_ok, search_telegram, search_instagram
        from models import Settings, Keyword, Mention
        from utils import save_log
        from notifications import send_notifications
        import flask
        
        logging.info(f"Starting background search for project {project_id}")
        
        # Create app context for database operations
        with current_app.app_context():
            # Initial delay before first search (5 seconds)
            time.sleep(5)
            
            while self.running:
                try:
                    # Get project settings
                    settings = Settings.query.filter_by(project_id=project_id).first()
                    if not settings:
                        save_log(f"No settings found for project {project_id}, stopping background search", 
                                level="ERROR")
                        self.running = False
                        break
                    
                    # Get keywords
                    keywords = Keyword.query.filter_by(project_id=project_id).all()
                    if not keywords:
                        save_log(f"No keywords found for project {project_id}, skipping search iteration", 
                                level="WARNING")
                        time.sleep(self.interval)
                        continue
                    
                    keyword_strings = [k.keyword for k in keywords]
                    
                    # Search VK
                    if settings.vk_token:
                        # Поиск по сообществам, если они указаны
                        if settings.vk_communities and settings.vk_communities.strip():
                            vk_communities = settings.vk_communities.split(',')
                            for community_id in vk_communities:
                                if community_id.strip():
                                    try:
                                        save_log(f"Поиск в сообществе ВК {community_id}")
                                        search_vk(project_id, community_id.strip(), keyword_strings)
                                    except Exception as e:
                                        save_log(f"Ошибка поиска в сообществе ВК {community_id}: {str(e)}", 
                                                level="ERROR")
                        else:
                            # Поиск по всему ВКонтакте
                            try:
                                save_log(f"Поиск по всему ВКонтакте")
                                search_vk(project_id, "", keyword_strings)
                            except Exception as e:
                                save_log(f"Ошибка поиска по всему ВКонтакте: {str(e)}", 
                                        level="ERROR")
                    
                    # Search OK
                    if settings.ok_token and settings.ok_communities:
                        ok_communities = settings.ok_communities.split(',')
                        for community_id in ok_communities:
                            if community_id.strip():
                                try:
                                    save_log(f"Поиск в сообществе Одноклассники {community_id}")
                                    search_ok(project_id, community_id.strip(), keyword_strings)
                                except Exception as e:
                                    save_log(f"Ошибка поиска в сообществе Одноклассники {community_id}: {str(e)}", 
                                            level="ERROR")
                    
                    # Search Telegram
                    if settings.telegram_token and settings.telegram_channels:
                        try:
                            save_log(f"Поиск в каналах/группах Telegram")
                            search_telegram(project_id, keyword_strings)
                        except Exception as e:
                            save_log(f"Ошибка поиска в Telegram: {str(e)}", level="ERROR")
                    
                    # Search Instagram
                    if settings.instagram_token and settings.instagram_accounts:
                        try:
                            save_log(f"Поиск в аккаунтах Instagram")
                            search_instagram(project_id, keyword_strings)
                        except Exception as e:
                            save_log(f"Ошибка поиска в Instagram: {str(e)}", level="ERROR")
                    
                    # Check if we need to send notifications for new mentions
                    if settings.enable_email_notifications or settings.enable_telegram_notifications:
                        try:
                            # Get mentions found in the last minute (new mentions from this search)
                            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
                            new_mentions = Mention.query.filter(
                                Mention.project_id == project_id,
                                Mention.found_date >= one_minute_ago
                            ).all()
                            
                            if new_mentions:
                                save_log(f"Sending notifications for {len(new_mentions)} new mentions")
                                notification_result = send_notifications(project_id, new_mentions)
                                
                                # Log notification results
                                if notification_result["email"]:
                                    save_log("Email notification sent successfully")
                                elif settings.enable_email_notifications:
                                    save_log("Failed to send email notification", level="WARNING")
                                    
                                if notification_result["telegram"]:
                                    save_log("Telegram notification sent successfully")
                                elif settings.enable_telegram_notifications:
                                    save_log("Failed to send Telegram notification", level="WARNING")
                        except Exception as e:
                            save_log(f"Error sending notifications: {str(e)}", level="ERROR")
                    
                    # Wait for next iteration
                    save_log(f"Background search completed, next run in {self.interval} seconds")
                    
                except Exception as e:
                    save_log(f"Unexpected error in background search: {str(e)}", level="ERROR")
                
                # Sleep until next iteration
                # Use small sleep chunks to check self.running more frequently
                for _ in range(int(self.interval / 5)):
                    if not self.running:
                        break
                    time.sleep(5)
        
        logging.info(f"Stopped background search for project {project_id}")
