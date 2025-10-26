from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import os

from models import db, User, MusicRequest, Settings, ContentType, RequestStatus, UserRole
from config import Config
from auth_service import LocalAuthService, JellyfinAuthService
from musicbrainz_service import MusicBrainzService
from streamrip_service import StreamripService
from jellyfin_service import JellyfinService
from download_service import DownloadService

app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')

# Load configuration
app.config.from_object(Config)

# Initialize extensions
CORS(app)
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()
    
    # Create default admin user if none exists
    if not User.query.filter_by(role=UserRole.ADMIN).first():
        admin, error = LocalAuthService.create_user(
            'admin',
            'admin',
            'admin@riparr.local',
            role=UserRole.ADMIN
        )
        if admin:
            print("Default admin user created: username=admin, password=admin")

@app.route('/')
def index():
    """Serve the main frontend page"""
    return render_template('index.html')

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'riparr'})

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint supporting both local and Jellyfin authentication"""
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    provider = data.get('provider', 'local')  # 'local' or 'jellyfin'
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = None
    error = None
    
    if provider == 'jellyfin':
        jellyfin_data, error = JellyfinAuthService.authenticate(username, password)
        if jellyfin_data:
            user = JellyfinAuthService.get_or_create_user(jellyfin_data)
    else:
        user, error = LocalAuthService.authenticate(username, password)
    
    if user:
        login_user(user, remember=True)
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role.value,
                'auth_provider': user.auth_provider.value
            }
        })
    
    return jsonify({'error': error or 'Invalid credentials'}), 401

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new local user"""
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user, error = LocalAuthService.create_user(username, password, email)
    
    if user:
        login_user(user)
        return jsonify({
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role.value
            }
        }), 201
    
    return jsonify({'error': error}), 400

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout current user"""
    logout_user()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/me')
@login_required
def get_current_user():
    """Get current user info"""
    return jsonify({
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'email': current_user.email,
            'role': current_user.role.value,
            'auth_provider': current_user.auth_provider.value
        }
    })

# Music request endpoints
@app.route('/api/requests', methods=['GET'])
@login_required
def get_requests():
    """Get all music requests for current user or all if admin"""
    if current_user.is_admin():
        requests = MusicRequest.query.order_by(MusicRequest.created_at.desc()).all()
    else:
        requests = MusicRequest.query.filter_by(user_id=current_user.id).order_by(MusicRequest.created_at.desc()).all()
    
    return jsonify({'requests': [r.to_dict() for r in requests]})

@app.route('/api/requests', methods=['POST'])
@login_required
def create_request():
    """Create a new music request"""
    data = request.get_json()
    
    content_type = data.get('content_type', 'song')
    title = data.get('title') or data.get('song')  # Support legacy 'song' field
    artist = data.get('artist')
    album = data.get('album')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    # Check if already available in Jellyfin
    jellyfin_service = JellyfinService(
        base_url=app.config.get('JELLYFIN_URL'),
        api_key=app.config.get('JELLYFIN_API_KEY')
    )
    if jellyfin_service.check_availability(title, artist, album):
        return jsonify({
            'message': 'Content already available in Jellyfin',
            'available': True
        }), 200
    
    # Create request
    new_request = MusicRequest(
        user_id=current_user.id,
        content_type=ContentType[content_type.upper()],
        title=title,
        artist=artist,
        album=album
    )
    
    db.session.add(new_request)
    db.session.commit()
    
    # Start processing in background (in production, use Celery or similar)
    # For now, we'll just return the request
    
    return jsonify({'request': new_request.to_dict()}), 201

@app.route('/api/requests/<int:request_id>', methods=['GET'])
@login_required
def get_request(request_id):
    """Get a specific request"""
    music_request = MusicRequest.query.get(request_id)
    
    if not music_request:
        return jsonify({'error': 'Request not found'}), 404
    
    if not current_user.is_admin() and music_request.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({'request': music_request.to_dict()})

@app.route('/api/requests/<int:request_id>/process', methods=['POST'])
@login_required
def process_request(request_id):
    """Process a music request (admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    download_service = DownloadService(
        config_path=app.config.get('STREAMRIP_CONFIG_PATH', 'config/streamrip.toml'),
        primary_service=app.config.get('PRIMARY_STREAMING_SERVICE', 'qobuz'),
        fallback_service=app.config.get('FALLBACK_STREAMING_SERVICE', 'deezer'),
        temp_path=app.config.get('TEMP_DOWNLOAD_PATH', '/tmp/riparr/downloads'),
        output_path=app.config.get('MUSIC_OUTPUT_PATH', '/media/Music'),
        path_pattern=app.config.get('MUSIC_PATH_PATTERN', '{artist}/{artist} - {title}')
    )
    success, error = download_service.process_request(request_id)
    
    if success:
        return jsonify({'message': 'Request processed successfully'})
    
    return jsonify({'error': error}), 400

# Search endpoints
@app.route('/api/search/musicbrainz')
@login_required
def search_musicbrainz():
    """Search MusicBrainz"""
    query = request.args.get('query')
    content_type = request.args.get('type', 'song')
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    mb_service = MusicBrainzService()
    
    if content_type == 'song':
        results, error = mb_service.search_song(query)
    elif content_type == 'album':
        results, error = mb_service.search_album(query)
    elif content_type == 'artist':
        results, error = mb_service.search_artist(query)
    else:
        return jsonify({'error': 'Invalid type'}), 400
    
    if error:
        return jsonify({'error': error}), 500
    
    return jsonify({'results': results})

@app.route('/api/search/streaming')
@login_required
def search_streaming():
    """Search streaming services"""
    query = request.args.get('query')
    content_type = request.args.get('type', 'track')
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    streamrip_service = StreamripService(
        config_path=app.config.get('STREAMRIP_CONFIG_PATH', 'config/streamrip.toml'),
        primary_service=app.config.get('PRIMARY_STREAMING_SERVICE', 'qobuz'),
        fallback_service=app.config.get('FALLBACK_STREAMING_SERVICE', 'deezer')
    )
    results, service, error = streamrip_service.smart_search(query, content_type)
    
    if error:
        return jsonify({'error': error}), 500
    
    return jsonify({'results': results, 'service': service})

@app.route('/api/search/jellyfin')
@login_required
def search_jellyfin():
    """Search Jellyfin library"""
    query = request.args.get('query')
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    jellyfin_service = JellyfinService(
        base_url=app.config.get('JELLYFIN_URL'),
        api_key=app.config.get('JELLYFIN_API_KEY')
    )
    results = jellyfin_service.search_library(query)
    
    return jsonify({'results': results})

# Admin endpoints
@app.route('/api/admin/settings', methods=['GET'])
@login_required
def get_settings():
    """Get all settings (admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    settings = {
        'jellyfin_url': Settings.get('jellyfin_url', ''),
        'primary_service': Settings.get('primary_service', 'qobuz'),
        'fallback_service': Settings.get('fallback_service', 'deezer'),
        'download_quality': Settings.get('download_quality', '3'),
        'output_path': Settings.get('output_path', '/media/Music'),
        'path_pattern': Settings.get('path_pattern', '{artist}/{artist} - {title}'),
    }
    
    return jsonify({'settings': settings})

@app.route('/api/admin/settings', methods=['PUT'])
@login_required
def update_settings():
    """Update settings (admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    data = request.get_json()
    
    for key, value in data.items():
        Settings.set(key, str(value))
    
    return jsonify({'message': 'Settings updated successfully'})

@app.route('/api/admin/jellyfin/sync', methods=['POST'])
@login_required
def sync_jellyfin():
    """Sync Jellyfin library (admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    jellyfin_service = JellyfinService(
        base_url=app.config.get('JELLYFIN_URL'),
        api_key=app.config.get('JELLYFIN_API_KEY')
    )
    success, message = jellyfin_service.sync_library()
    
    if success:
        return jsonify({'message': message})
    
    return jsonify({'error': message}), 500

@app.route('/api/admin/jellyfin/test', methods=['POST'])
@login_required
def test_jellyfin():
    """Test Jellyfin connection (admin only)"""
    if not current_user.is_admin():
        return jsonify({'error': 'Admin access required'}), 403
    
    jellyfin_service = JellyfinService(
        base_url=app.config.get('JELLYFIN_URL'),
        api_key=app.config.get('JELLYFIN_API_KEY')
    )
    success, result = jellyfin_service.test_connection()
    
    if success:
        return jsonify({'success': True, 'info': result})
    
    return jsonify({'success': False, 'error': result}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)

