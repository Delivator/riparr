import requests
from flask import current_app
from backend.models import User, AuthProvider, UserRole, db

class JellyfinAuthService:
    @staticmethod
    def authenticate(username, password, jellyfin_url=None):
        """Authenticate user against Jellyfin server"""
        url = jellyfin_url or current_app.config.get('JELLYFIN_URL')
        
        if not url:
            return None, "Jellyfin URL not configured"
        
        try:
            # Jellyfin authentication endpoint
            auth_url = f"{url.rstrip('/')}/Users/AuthenticateByName"
            
            payload = {
                "Username": username,
                "Pw": password
            }
            
            headers = {
                "Content-Type": "application/json",
                "X-Emby-Authorization": f'MediaBrowser Client="Riparr", Device="Server", DeviceId="riparr-server", Version="1.0.0"'
            }
            
            response = requests.post(auth_url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                user_data = data.get('User', {})
                
                return {
                    'user_id': user_data.get('Id'),
                    'username': user_data.get('Name'),
                    'is_admin': user_data.get('Policy', {}).get('IsAdministrator', False),
                    'access_token': data.get('AccessToken')
                }, None
            else:
                return None, "Invalid credentials"
                
        except requests.exceptions.RequestException as e:
            return None, f"Jellyfin connection error: {str(e)}"
    
    @staticmethod
    def get_or_create_user(jellyfin_user_data):
        """Get or create user from Jellyfin authentication data"""
        user = User.query.filter_by(
            auth_provider=AuthProvider.JELLYFIN,
            jellyfin_user_id=jellyfin_user_data['user_id']
        ).first()
        
        if not user:
            # Check if username exists
            existing_user = User.query.filter_by(username=jellyfin_user_data['username']).first()
            if existing_user:
                # Username conflict, append jellyfin suffix
                username = f"{jellyfin_user_data['username']}_jellyfin"
            else:
                username = jellyfin_user_data['username']
            
            user = User(
                username=username,
                auth_provider=AuthProvider.JELLYFIN,
                jellyfin_user_id=jellyfin_user_data['user_id'],
                role=UserRole.ADMIN if jellyfin_user_data['is_admin'] else UserRole.USER
            )
            db.session.add(user)
            db.session.commit()
        
        return user

class LocalAuthService:
    @staticmethod
    def create_user(username, password, email=None, role=UserRole.USER):
        """Create a local user"""
        if User.query.filter_by(username=username).first():
            return None, "Username already exists"
        
        if email and User.query.filter_by(email=email).first():
            return None, "Email already exists"
        
        user = User(
            username=username,
            email=email,
            auth_provider=AuthProvider.LOCAL,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        return user, None
    
    @staticmethod
    def authenticate(username, password):
        """Authenticate local user"""
        user = User.query.filter_by(
            username=username,
            auth_provider=AuthProvider.LOCAL
        ).first()
        
        if user and user.check_password(password):
            return user, None
        
        return None, "Invalid credentials"
