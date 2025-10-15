import os
import asyncio
from flask import current_app
from streamrip.client import QobuzClient, DeezerClient, TidalClient
from streamrip.config import Config as StreamripConfig

class StreamripService:
    def __init__(self):
        self.config_path = current_app.config.get('STREAMRIP_CONFIG_PATH', 'config/streamrip.toml')
        self.primary_service = current_app.config.get('PRIMARY_STREAMING_SERVICE', 'qobuz')
        self.fallback_service = current_app.config.get('FALLBACK_STREAMING_SERVICE', 'deezer')
        self.config = None
        self._load_config()
    
    def _load_config(self):
        """Load streamrip configuration"""
        try:
            if os.path.exists(self.config_path):
                self.config = StreamripConfig.from_toml(self.config_path)
            else:
                self.config = StreamripConfig.defaults()
        except Exception as e:
            print(f"Error loading streamrip config: {e}")
            self.config = StreamripConfig.defaults()
    
    def _get_client(self, service):
        """Get the appropriate client for the streaming service"""
        if not self.config:
            self._load_config()
        
        if service == 'qobuz':
            return QobuzClient(self.config)
        elif service == 'deezer':
            return DeezerClient(self.config)
        elif service == 'tidal':
            return TidalClient(self.config)
        else:
            raise ValueError(f"Unsupported service: {service}")
    
    async def search_track_async(self, query, service=None, limit=10):
        """Search for a track on a streaming service"""
        service = service or self.primary_service
        
        try:
            client = self._get_client(service)
            
            # Login if needed
            if not await client.logged_in():
                await client.login()
            
            # Search for tracks
            results = await client.search('track', query, limit=limit)
            
            tracks = []
            for result in results:
                tracks.append({
                    'id': result.get('id'),
                    'title': result.get('title') or result.get('name'),
                    'artist': self._extract_artist(result),
                    'album': result.get('album', {}).get('title') if isinstance(result.get('album'), dict) else result.get('album'),
                    'duration': result.get('duration'),
                    'quality': result.get('maximum_bit_depth') or result.get('quality'),
                    'service': service,
                })
            
            return tracks, None
        except Exception as e:
            return None, str(e)
    
    def _extract_artist(self, result):
        """Extract artist name from result"""
        if 'artist' in result:
            artist = result['artist']
            if isinstance(artist, dict):
                return artist.get('name', '')
            return str(artist)
        elif 'artists' in result and result['artists']:
            if isinstance(result['artists'][0], dict):
                return result['artists'][0].get('name', '')
            return str(result['artists'][0])
        return ''
    
    def search_track(self, query, service=None, limit=10):
        """Synchronous wrapper for track search"""
        return asyncio.run(self.search_track_async(query, service, limit))
    
    async def search_album_async(self, query, service=None, limit=10):
        """Search for an album on a streaming service"""
        service = service or self.primary_service
        
        try:
            client = self._get_client(service)
            
            # Login if needed
            if not await client.logged_in():
                await client.login()
            
            # Search for albums
            results = await client.search('album', query, limit=limit)
            
            albums = []
            for result in results:
                albums.append({
                    'id': result.get('id'),
                    'title': result.get('title') or result.get('name'),
                    'artist': self._extract_artist(result),
                    'year': result.get('year') or result.get('release_date', '')[:4] if result.get('release_date') else None,
                    'track_count': result.get('tracks_count') or result.get('nb_tracks'),
                    'quality': result.get('maximum_bit_depth') or result.get('quality'),
                    'service': service,
                })
            
            return albums, None
        except Exception as e:
            return None, str(e)
    
    def search_album(self, query, service=None, limit=10):
        """Synchronous wrapper for album search"""
        return asyncio.run(self.search_album_async(query, service, limit))
    
    async def download_track_async(self, track_id, service, output_path):
        """Download a track from a streaming service"""
        try:
            client = self._get_client(service)
            
            # Login if needed
            if not await client.logged_in():
                await client.login()
            
            # Set output path in config
            if self.config:
                self.config.session.downloads.folder = output_path
            
            # Download track
            await client.download_track(track_id)
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def download_track(self, track_id, service, output_path):
        """Synchronous wrapper for track download"""
        return asyncio.run(self.download_track_async(track_id, service, output_path))
    
    async def download_album_async(self, album_id, service, output_path):
        """Download an album from a streaming service"""
        try:
            client = self._get_client(service)
            
            # Login if needed
            if not await client.logged_in():
                await client.login()
            
            # Set output path in config
            if self.config:
                self.config.session.downloads.folder = output_path
            
            # Download album
            await client.download_album(album_id)
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def download_album(self, album_id, service, output_path):
        """Synchronous wrapper for album download"""
        return asyncio.run(self.download_album_async(album_id, service, output_path))
    
    def smart_search(self, query, content_type='track', use_fallback=True):
        """
        Smart search with primary and fallback services.
        Tries various search strategies if initial search fails.
        """
        from backend.musicbrainz_service import MusicBrainzService
        
        # Try primary service first
        if content_type == 'track':
            results, error = self.search_track(query, self.primary_service)
        else:
            results, error = self.search_album(query, self.primary_service)
        
        if results and len(results) > 0:
            return results, self.primary_service, None
        
        # Try cleaned query on primary service
        cleaned_query = MusicBrainzService.clean_search_query(query)
        if cleaned_query != query:
            if content_type == 'track':
                results, error = self.search_track(cleaned_query, self.primary_service)
            else:
                results, error = self.search_album(cleaned_query, self.primary_service)
            
            if results and len(results) > 0:
                return results, self.primary_service, None
        
        # Try fallback service if enabled
        if use_fallback and self.fallback_service:
            if content_type == 'track':
                results, error = self.search_track(query, self.fallback_service)
            else:
                results, error = self.search_album(query, self.fallback_service)
            
            if results and len(results) > 0:
                return results, self.fallback_service, None
            
            # Try cleaned query on fallback
            if cleaned_query != query:
                if content_type == 'track':
                    results, error = self.search_track(cleaned_query, self.fallback_service)
                else:
                    results, error = self.search_album(cleaned_query, self.fallback_service)
                
                if results and len(results) > 0:
                    return results, self.fallback_service, None
        
        return None, None, "No results found on any streaming service"
