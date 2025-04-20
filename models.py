from datetime import datetime
from app import db

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    settings = db.relationship('Settings', backref='project', lazy=True, cascade="all, delete-orphan")
    keywords = db.relationship('Keyword', backref='project', lazy=True, cascade="all, delete-orphan")
    mentions = db.relationship('Mention', backref='project', lazy=True, cascade="all, delete-orphan")
    logs = db.relationship('Log', backref='project', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Project {self.name}>'

class Settings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    
    # API Tokens
    vk_token = db.Column(db.String(255))
    ok_token = db.Column(db.String(255))
    ok_public_key = db.Column(db.String(255))
    ok_private_key = db.Column(db.String(255))
    
    # Communities to monitor
    vk_communities = db.Column(db.Text)  # Comma-separated community IDs
    ok_communities = db.Column(db.Text)  # Comma-separated community IDs
    
    # Search settings
    search_interval = db.Column(db.Integer, default=3600)  # Seconds between automatic searches
    
    def __repr__(self):
        return f'<Settings for Project {self.project_id}>'

class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    keyword = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default='#ffff00')  # Default yellow highlight
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Keyword {self.keyword} for Project {self.project_id}>'

class Mention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    
    # Source information
    social_network = db.Column(db.String(20), nullable=False)  # 'vk' or 'ok'
    
    # Content information
    content = db.Column(db.Text, nullable=False)
    post_url = db.Column(db.String(255))
    post_date = db.Column(db.DateTime)
    
    # Author information
    author_id = db.Column(db.String(50))
    author_name = db.Column(db.String(100))
    
    # Metadata
    found_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Mention {self.id} from {self.social_network}>'

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(10), default='INFO')  # INFO, WARNING, ERROR
    message = db.Column(db.Text, nullable=False)
    
    def __repr__(self):
        return f'<Log {self.id}: {self.level} - {self.message[:20]}>'
