import os
from datetime import timedelta

class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///riparr.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask-Login
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    
    # Jellyfin
    JELLYFIN_URL = os.environ.get('JELLYFIN_URL', '')
    JELLYFIN_API_KEY = os.environ.get('JELLYFIN_API_KEY', '')
    
    # Streamrip
    STREAMRIP_CONFIG_PATH = os.environ.get('STREAMRIP_CONFIG_PATH', 'config/streamrip.toml')
    PRIMARY_STREAMING_SERVICE = os.environ.get('PRIMARY_STREAMING_SERVICE', 'qobuz')
    FALLBACK_STREAMING_SERVICE = os.environ.get('FALLBACK_STREAMING_SERVICE', 'deezer')
    
    # Download settings
    DOWNLOAD_QUALITY = os.environ.get('DOWNLOAD_QUALITY', '3')  # Highest quality
    TEMP_DOWNLOAD_PATH = os.environ.get('TEMP_DOWNLOAD_PATH', '/tmp/riparr/downloads')
    MUSIC_OUTPUT_PATH = os.environ.get('MUSIC_OUTPUT_PATH', '/media/Music')
    MUSIC_PATH_PATTERN = os.environ.get('MUSIC_PATH_PATTERN', '{artist}/{artist} - {title}')
    
    # MusicBrainz
    MUSICBRAINZ_USER_AGENT = os.environ.get('MUSICBRAINZ_USER_AGENT', 'Riparr/1.0.0')
    
    # Picard
    PICARD_ENABLED = os.environ.get('PICARD_ENABLED', 'true').lower() == 'true'
