import os
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables if they exist
load_dotenv(override=False)


class Config:
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Project root (one level up from backend/)
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    # Database
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default to /app/config/riparr.db if in docker, or instance/riparr.db locally
        if os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER'):
            db_dir = '/app/config'
        else:
            db_dir = os.path.join(BASE_DIR, 'instance')
            
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError:
            # This might happen in some environments (like local tests)
            # We'll let it fail later when actually trying to write if it's still an issue
            pass
        db_path = os.path.join(db_dir, 'riparr.db')
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
    # Default to /app/config/streamrip.toml if in docker
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
    default_streamrip_config = '/app/config/streamrip.toml' if is_docker else 'config/streamrip.toml'
    STREAMRIP_CONFIG_PATH = os.environ.get('STREAMRIP_CONFIG_PATH', default_streamrip_config)
    PRIMARY_STREAMING_SERVICE = os.environ.get('PRIMARY_STREAMING_SERVICE', 'qobuz')
    FALLBACK_STREAMING_SERVICE = os.environ.get('FALLBACK_STREAMING_SERVICE', 'deezer')
    
    # Download settings
    DOWNLOAD_QUALITY = os.environ.get('DOWNLOAD_QUALITY', '3')  # Highest quality
    
    # Default to /tmp/riparr/downloads and /media/Music
    default_temp_path = '/tmp/riparr/downloads' if is_docker else os.path.join(BASE_DIR, 'downloads', 'temp')
    default_music_path = '/media/Music' if is_docker else os.path.join(BASE_DIR, 'music')
    
    TEMP_DOWNLOAD_PATH = os.environ.get('TEMP_DOWNLOAD_PATH', default_temp_path)
    MUSIC_OUTPUT_PATH = os.environ.get('MUSIC_OUTPUT_PATH', default_music_path)
    MUSIC_PATH_PATTERN = os.environ.get('MUSIC_PATH_PATTERN', '{artist}/{artist} - {title}')
    
    # MusicBrainz
    MUSICBRAINZ_USER_AGENT = os.environ.get('MUSICBRAINZ_USER_AGENT', 'Riparr/1.0.0')
    
    # Picard
    PICARD_ENABLED = os.environ.get('PICARD_ENABLED', 'true').lower() == 'true'
