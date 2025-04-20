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
        from social_api import search_vk, search_ok
        from models import Settings, Keyword
        from utils import save_log
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
                    if settings.vk_token and settings.vk_communities:
                        vk_communities = settings.vk_communities.split(',')
                        for community_id in vk_communities:
                            try:
                                save_log(f"Searching VK community {community_id}")
                                search_vk(project_id, community_id, keyword_strings)
                            except Exception as e:
                                save_log(f"Error searching VK community {community_id}: {str(e)}", 
                                        level="ERROR")
                    
                    # Search OK
                    if settings.ok_token and settings.ok_communities:
                        ok_communities = settings.ok_communities.split(',')
                        for community_id in ok_communities:
                            try:
                                save_log(f"Searching OK community {community_id}")
                                search_ok(project_id, community_id, keyword_strings)
                            except Exception as e:
                                save_log(f"Error searching OK community {community_id}: {str(e)}", 
                                        level="ERROR")
                    
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
