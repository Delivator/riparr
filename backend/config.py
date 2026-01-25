import os
from datetime import timedelta


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Project root (one level up from backend/)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Database
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default to instance/riparr.db in project root
        instance_dir = os.path.join(BASE_DIR, 'instance')
        os.makedirs(instance_dir, exist_ok=True)
        db_path = os.path.join(instance_dir, 'riparr.db')
        db_url = f'sqlite:///{db_path}'
    elif db_url.startswith('sqlite:///instance/'):
        # Convert relative instance path to absolute
        db_path = os.path.join(BASE_DIR, 'instance', db_url.replace('sqlite:///instance/', ''))
        db_url = f'sqlite:///{db_path}'
    
    SQLALCHEMY_DATABASE_URI = db_url
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
    TEMP_DOWNLOAD_PATH = os.environ.get('TEMP_DOWNLOAD_PATH', os.path.join(BASE_DIR, 'downloads', 'temp'))
    MUSIC_OUTPUT_PATH = os.environ.get('MUSIC_OUTPUT_PATH', os.path.join(BASE_DIR, 'music'))
    MUSIC_PATH_PATTERN = os.environ.get('MUSIC_PATH_PATTERN', '{artist}/{artist} - {title}')
    
    # MusicBrainz
    MUSICBRAINZ_USER_AGENT = os.environ.get('MUSICBRAINZ_USER_AGENT', 'Riparr/1.0.0')
    
    # Picard
    PICARD_ENABLED = os.environ.get('PICARD_ENABLED', 'true').lower() == 'true'
