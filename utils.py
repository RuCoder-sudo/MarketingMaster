import re
from datetime import datetime
from flask import current_app
from models import Project, Log, Keyword, db

def highlight_text(text, keywords):
    """
    Highlight keywords in text with their respective colors using HTML span
    
    Args:
        text (str): The text to highlight
        keywords (list): List of Keyword objects
    
    Returns:
        str: HTML with highlighted keywords
    """
    if not text or not keywords:
        return text
    
    # Sort keywords by length (descending) to prioritize longer matches
    sorted_keywords = sorted(keywords, key=lambda k: len(k.keyword), reverse=True)
    
    # Replace keywords with highlighted versions
    result = text
    for keyword in sorted_keywords:
        # Create a regex pattern that matches whole word or part of word
        pattern = re.compile(f'({re.escape(keyword.keyword)})', re.IGNORECASE)
        replacement = f'<span style="background-color:{keyword.color};">\\1</span>'
        result = pattern.sub(replacement, result)
    
    return result

def get_active_project():
    """
    Get the currently active project from the application config
    If no active project is set, use the first available project
    
    Returns:
        Project: The active project
    """
    active_project_id = current_app.config.get('ACTIVE_PROJECT_ID')
    
    if active_project_id:
        active_project = Project.query.get(active_project_id)
        if active_project:
            return active_project
    
    # Fallback to first project
    first_project = Project.query.first()
    if first_project:
        current_app.config['ACTIVE_PROJECT_ID'] = first_project.id
        return first_project
    
    # Should never happen since we create a default project on startup
    return None

def save_log(message, level="INFO", project_id=None):
    """
    Save a log message to the database
    
    Args:
        message (str): The log message
        level (str): Log level (INFO, WARNING, ERROR)
        project_id (int, optional): Project ID. If None, use active project
    """
    if project_id is None:
        active_project = get_active_project()
        if active_project:
            project_id = active_project.id
        else:
            # If no project exists yet, don't log
            return
    
    # Create and save log
    log = Log(
        project_id=project_id,
        timestamp=datetime.utcnow(),
        level=level,
        message=message
    )
    
    db.session.add(log)
    db.session.commit()
