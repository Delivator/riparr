import requests
from models import JellyfinLibrary, ContentType, db
from datetime import datetime

class JellyfinService:
    def __init__(self, base_url=None, api_key=None):
        """
        Initialize JellyfinService with optional configuration.
        If parameters are None, they will be loaded from Flask config on first use.
        """
        self.base_url = base_url
        self.api_key = api_key
    
    def _get_headers(self):
        """Get headers for Jellyfin API requests"""
        return {
            'X-Emby-Token': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def test_connection(self):
        """Test connection to Jellyfin server"""
        if not self.base_url or not self.api_key:
            return False, "Jellyfin URL or API key not configured"
        
        try:
            url = f"{self.base_url.rstrip('/')}/System/Info"
            response = requests.get(url, headers=self._get_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return True, {
                    'server_name': data.get('ServerName'),
                    'version': data.get('Version')
                }
            else:
                return False, f"HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, str(e)
    
    def sync_library(self):
        """Sync Jellyfin music library to local database"""
        if not self.base_url or not self.api_key:
            return False, "Jellyfin not configured"
        
        try:
            # Get all music items from Jellyfin
            url = f"{self.base_url.rstrip('/')}/Items"
            params = {
                'IncludeItemTypes': 'Audio,MusicAlbum,MusicArtist',
                'Recursive': 'true',
                'Fields': 'Path,Artists,Album'
            }
            
            response = requests.get(url, headers=self._get_headers(), params=params, timeout=30)
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            
            items = response.json().get('Items', [])
            synced_count = 0
            
            for item in items:
                content_type = self._map_jellyfin_type(item.get('Type'))
                if not content_type:
                    continue
                
                jellyfin_id = item.get('Id')
                
                # Check if already exists
                library_item = JellyfinLibrary.query.filter_by(jellyfin_id=jellyfin_id).first()
                
                if library_item:
                    # Update existing item
                    library_item.title = item.get('Name', '')
                    library_item.artist = ', '.join(item.get('Artists', [])) if item.get('Artists') else None
                    library_item.album = item.get('Album')
                    library_item.path = item.get('Path')
                    library_item.last_synced = datetime.utcnow()
                else:
                    # Create new item
                    library_item = JellyfinLibrary(
                        jellyfin_id=jellyfin_id,
                        content_type=content_type,
                        title=item.get('Name', ''),
                        artist=', '.join(item.get('Artists', [])) if item.get('Artists') else None,
                        album=item.get('Album'),
                        path=item.get('Path')
                    )
                    db.session.add(library_item)
                
                synced_count += 1
            
            db.session.commit()
            
            return True, f"Synced {synced_count} items"
        except Exception as e:
            return False, str(e)
    
    def search_library(self, query, content_type=None):
        """Search local synced Jellyfin library"""
        query_filter = JellyfinLibrary.query.filter(
            db.or_(
                JellyfinLibrary.title.ilike(f'%{query}%'),
                JellyfinLibrary.artist.ilike(f'%{query}%'),
                JellyfinLibrary.album.ilike(f'%{query}%')
            )
        )
        
        if content_type:
            query_filter = query_filter.filter_by(content_type=content_type)
        
        results = query_filter.limit(50).all()
        return [item.to_dict() for item in results]
    
    def check_availability(self, title, artist=None, album=None):
        """Check if content is available in Jellyfin library"""
        query = JellyfinLibrary.query.filter(JellyfinLibrary.title.ilike(f'%{title}%'))
        
        if artist:
            query = query.filter(JellyfinLibrary.artist.ilike(f'%{artist}%'))
        
        if album:
            query = query.filter(JellyfinLibrary.album.ilike(f'%{album}%'))
        
        return query.first() is not None
    
    def get_play_url(self, jellyfin_id):
        """Get streaming URL for a Jellyfin item"""
        if not self.base_url:
            return None
        
        return f"{self.base_url.rstrip('/')}/Audio/{jellyfin_id}/stream?static=true&api_key={self.api_key}"
    
    def _map_jellyfin_type(self, jellyfin_type):
        """Map Jellyfin item type to ContentType"""
        type_map = {
            'Audio': ContentType.SONG,
            'MusicAlbum': ContentType.ALBUM,
            'MusicArtist': ContentType.ARTIST
        }
        return type_map.get(jellyfin_type)
