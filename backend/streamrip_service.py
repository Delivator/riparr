import os
import asyncio
from flask import current_app
from streamrip import Streamrip
from streamrip.config import Config as StreamripConfig

class StreamripService:
    def __init__(self):
        self.config_path = current_app.config.get('STREAMRIP_CONFIG_PATH')
        self.primary_service = current_app.config.get('PRIMARY_STREAMING_SERVICE', 'qobuz')
        self.fallback_service = current_app.config.get('FALLBACK_STREAMING_SERVICE', 'deezer')
    
    async def search_track_async(self, query, service=None, limit=10):
        """Search for a track on a streaming service"""
        service = service or self.primary_service
        
        try:
            # Initialize Streamrip with config
            config = StreamripConfig.from_toml(self.config_path) if os.path.exists(self.config_path) else StreamripConfig()
            
            client = Streamrip(config)
            
            # Search for tracks
            results = await client.search(service, query, 'track', limit=limit)
            
            tracks = []
            for result in results:
                tracks.append({
                    'id': result.get('id'),
                    'title': result.get('title'),
                    'artist': result.get('artist'),
                    'album': result.get('album'),
                    'duration': result.get('duration'),
                    'quality': result.get('quality'),
                    'service': service,
                })
            
            return tracks, None
        except Exception as e:
            return None, str(e)
    
    def search_track(self, query, service=None, limit=10):
        """Synchronous wrapper for track search"""
        return asyncio.run(self.search_track_async(query, service, limit))
    
    async def search_album_async(self, query, service=None, limit=10):
        """Search for an album on a streaming service"""
        service = service or self.primary_service
        
        try:
            config = StreamripConfig.from_toml(self.config_path) if os.path.exists(self.config_path) else StreamripConfig()
            client = Streamrip(config)
            
            results = await client.search(service, query, 'album', limit=limit)
            
            albums = []
            for result in results:
                albums.append({
                    'id': result.get('id'),
                    'title': result.get('title'),
                    'artist': result.get('artist'),
                    'year': result.get('year'),
                    'track_count': result.get('track_count'),
                    'quality': result.get('quality'),
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
            config = StreamripConfig.from_toml(self.config_path) if os.path.exists(self.config_path) else StreamripConfig()
            
            # Set output path
            config.session.downloads.folder = output_path
            
            client = Streamrip(config)
            
            # Download track
            await client.download_track(service, track_id)
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def download_track(self, track_id, service, output_path):
        """Synchronous wrapper for track download"""
        return asyncio.run(self.download_track_async(track_id, service, output_path))
    
    async def download_album_async(self, album_id, service, output_path):
        """Download an album from a streaming service"""
        try:
            config = StreamripConfig.from_toml(self.config_path) if os.path.exists(self.config_path) else StreamripConfig()
            
            # Set output path
            config.session.downloads.folder = output_path
            
            client = Streamrip(config)
            
            # Download album
            await client.download_album(service, album_id)
            
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
