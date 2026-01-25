from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import enum

db = SQLAlchemy()

class UserRole(enum.Enum):
    USER = "user"
    ADMIN = "admin"

class AuthProvider(enum.Enum):
    LOCAL = "local"
    JELLYFIN = "jellyfin"

class RequestStatus(enum.Enum):
    PENDING = "pending"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ContentType(enum.Enum):
    SONG = "song"
    ALBUM = "album"
    ARTIST = "artist"

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    auth_provider = db.Column(db.Enum(AuthProvider), default=AuthProvider.LOCAL, nullable=False)
    jellyfin_user_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    requests = db.relationship('MusicRequest', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == UserRole.ADMIN

class MusicRequest(db.Model):
    __tablename__ = 'music_requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    content_type = db.Column(db.Enum(ContentType), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=True)
    album = db.Column(db.String(255), nullable=True)
    
    # MusicBrainz IDs
    musicbrainz_id = db.Column(db.String(255), nullable=True)
    musicbrainz_release_group_id = db.Column(db.String(255), nullable=True)
    
    # Streaming service info
    streaming_service = db.Column(db.String(50), nullable=True)
    streaming_url = db.Column(db.String(500), nullable=True)
    
    status = db.Column(db.Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    
    download_path = db.Column(db.String(500), nullable=True)
    file_size = db.Column(db.BigInteger, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'content_type': self.content_type.value,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'status': self.status.value,
            'error_message': self.error_message,
            'streaming_service': self.streaming_service,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    @staticmethod
    def get(key, default=None):
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else default
    
    @staticmethod
    def set(key, value):
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()

class JellyfinLibrary(db.Model):
    __tablename__ = 'jellyfin_library'
    
    id = db.Column(db.Integer, primary_key=True)
    jellyfin_id = db.Column(db.String(255), unique=True, nullable=False)
    content_type = db.Column(db.Enum(ContentType), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    artist = db.Column(db.String(255), nullable=True)
    album = db.Column(db.String(255), nullable=True)
    path = db.Column(db.String(500), nullable=True)
    last_synced = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'jellyfin_id': self.jellyfin_id,
            'content_type': self.content_type.value,
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
        }
