import os
import asyncio
import logging
from streamrip.client import QobuzClient, DeezerClient, TidalClient
from streamrip.config import Config as StreamripConfig
from streamrip.db import Database, Downloads, Failed, Dummy
from streamrip.media.track import PendingSingle
from streamrip.media.album import PendingAlbum
from streamrip.media import remove_artwork_tempdirs

logger = logging.getLogger(__name__)

class StreamripService:
    def __init__(self, config_path=None, primary_service=None, fallback_service=None):
        """
        Initialize StreamripService with optional configuration.
        """
        # Ensure we use an absolute path for the config
        if config_path:
            self.config_path = os.path.abspath(config_path)
        else:
            # Default to project-relative path, but make it absolute
            self.config_path = os.path.abspath(os.path.join(os.getcwd(), 'config/streamrip.toml'))
            
        self.primary_service = primary_service or 'qobuz'
        self.fallback_service = fallback_service or 'deezer'
        self.config = None
        self.db = None
        self._config_loaded = False
        self._clients = {}
    
    def _ensure_config_loaded(self):
        """Ensure configuration and database are loaded before use"""
        if not self._config_loaded:
            self._load_config()
            self._init_db()
            self._config_loaded = True
    
    def _load_config(self):
        """Load streamrip configuration"""
        try:
            if os.path.exists(self.config_path):
                logger.info(f"Loading streamrip config from: {self.config_path}")
                self.config = StreamripConfig(self.config_path)
            else:
                logger.warning(f"Config not found at {self.config_path}, using defaults")
                self.config = StreamripConfig.defaults()
        except Exception as e:
            logger.error(f"Error loading streamrip config: {e}")
            self.config = StreamripConfig.defaults()
    
    def _init_db(self):
        """Initialize streamrip database"""
        try:
            # We use the paths from the LOADED config
            db_path = self.config.session.database.downloads_path
            failed_db_path = self.config.session.database.failed_downloads_path
            
            # Ensure directories exist
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
            os.makedirs(os.path.dirname(os.path.abspath(failed_db_path)), exist_ok=True)
            
            self.db = Database(
                downloads=Downloads(db_path),
                failed=Failed(failed_db_path)
            )
        except Exception as e:
            logger.error(f"Error initializing streamrip database: {e}")
            raise
    
    async def _get_client(self, service):
        """Create the appropriate client for the streaming service"""
        self._ensure_config_loaded()
        
        if service == 'qobuz':
            client = QobuzClient(self.config)
        elif service == 'deezer':
            client = DeezerClient(self.config)
        elif service == 'tidal':
            client = TidalClient(self.config)
        else:
            raise ValueError(f"Unsupported service: {service}")
            
        # Login
        await client.login()
        return client
    
    async def search_track_async(self, query, service=None, limit=10):
        """Search for a track on a streaming service"""
        service = service or self.primary_service
        
        try:
            client = await self._get_client(service)
            pages = await client.search('track', query, limit=limit)
            
            tracks = []
            for page in pages:
                items = self._extract_search_items(page, service, 'track')
                for item in items:
                    tracks.append(self._normalize_track(item, service))
            
            return tracks[:limit], None
        except Exception as e:
            logger.exception("Track search failed")
            return None, str(e)
            
    def _extract_search_items(self, page, service, media_type):
        if service == 'qobuz':
            key = media_type + 's'
            return page.get(key, {}).get('items', [])
        elif service == 'deezer':
            key = media_type + 's' if media_type == 'track' else media_type
            if 'data' in page: return page['data']
            return page.get(key, {}).get('data', [])
        elif service == 'tidal':
            key = media_type + 's'
            return page.get(key, {}).get('items', [])
        return []

    def _normalize_track(self, item, service):
        # Extract quality info
        quality = item.get('maximum_bit_depth') or item.get('quality')
        sampling_rate = item.get('maximum_sampling_rate')
        
        quality_label = str(quality) if quality else "Unknown"
        if quality and sampling_rate:
            quality_label = f"{quality}B-{sampling_rate}kHz"

        return {
            'id': str(item.get('id')),
            'title': item.get('title') or item.get('name'),
            'artist': self._extract_artist(item),
            'album': self._extract_album_title(item),
            'duration': item.get('duration'),
            'duration_ms': item.get('duration') * 1000 if isinstance(item.get('duration'), (int, float)) else None,
            'quality': quality_label,
            'service': service,
            'cover_url': self._extract_cover_url(item, service),
            'release_date': item.get('release_date') or item.get('release_date_original'),
        }

    def _extract_album_title(self, item):
        album = item.get('album')
        if isinstance(album, dict):
            return album.get('title')
        return str(album) if album else None

    def _extract_artist(self, result):
        if 'artist' in result:
            artist = result['artist']
            if isinstance(artist, dict):
                return artist.get('name', '')
            return str(artist)
        elif 'artists' in result and result['artists']:
            if isinstance(result['artists'][0], dict):
                return result['artists'][0].get('name', '')
            return str(result['artists'][0])
        return 'Unknown Artist'

    def _extract_cover_url(self, item, service):
        """Extract cover image URL based on service response structure"""
        if service == 'qobuz':
            # Qobuz usually has image[ 'small', 'thumbnail', 'large' ]
            image = item.get('image') or (item.get('album', {}).get('image') if isinstance(item.get('album'), dict) else None)
            if isinstance(image, dict):
                return image.get('large') or image.get('small') or image.get('thumbnail')
        elif service == 'deezer':
            # Deezer usually has album['cover_medium'] or cover_medium
            album = item.get('album')
            if isinstance(album, dict):
                return album.get('cover_big') or album.get('cover_medium')
            return item.get('cover_big') or item.get('cover_medium')
        elif service == 'tidal':
            # Tidal usually has cover or album['cover']
            # Note: Tidal IDs are often used with a base URL
            pass
        return None
    
    async def parallel_search(self, query, services, content_type='track', limit=10):
        """Search multiple services in parallel"""
        tasks = []
        for service in services:
            if content_type == 'track':
                tasks.append(self.search_track_async(query, service, limit))
            else:
                tasks.append(self.search_album_async(query, service, limit))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_results = []
        errors = []
        
        for i, res in enumerate(results):
            service = services[i]
            if isinstance(res, Exception):
                logger.error(f"Search failed for {service}: {res}")
                errors.append(f"{service}: {str(res)}")
            else:
                service_results, error = res
                if service_results:
                    # Results are already normalized in the search_async methods
                    all_results.extend(service_results)
                if error:
                    errors.append(f"{service}: {error}")
        
        # Sort results by relevance (if score is available) or just interleaved
        # For now, let's just return the combined list.
        
        return all_results, None if not errors else "; ".join(errors)

    def search_track(self, query, service=None, limit=10):
        return asyncio.run(self.search_track_async(query, service, limit))
    
    async def search_album_async(self, query, service=None, limit=10):
        service = service or self.primary_service
        try:
            client = await self._get_client(service)
            pages = await client.search('album', query, limit=limit)
            
            albums = []
            for page in pages:
                items = self._extract_search_items(page, service, 'album')
                for item in items:
                    # Extract quality info
                    quality = item.get('maximum_bit_depth') or item.get('quality')
                    sampling_rate = item.get('maximum_sampling_rate')
                    quality_label = str(quality) if quality else "Unknown"
                    if quality and sampling_rate:
                        quality_label = f"{quality}B-{sampling_rate}kHz"

                    albums.append({
                        'id': str(item.get('id')),
                        'title': item.get('title') or item.get('name'),
                        'artist': self._extract_artist(item),
                        'year': item.get('year') or (item.get('release_date', '')[:4] if item.get('release_date') else None),
                        'track_count': item.get('tracks_count') or item.get('nb_tracks'),
                        'quality': quality_label,
                        'service': service,
                        'cover_url': self._extract_cover_url(item, service),
                        'release_date': item.get('release_date') or item.get('release_date_original'),
                    })
            
            return albums[:limit], None
        except Exception as e:
            logger.exception("Album search failed")
            return None, str(e)
    
    def search_album(self, query, service=None, limit=10):
        return asyncio.run(self.search_album_async(query, service, limit))
    
    async def download_track_async(self, track_id, service, output_path):
        """Download a track from a streaming service"""
        try:
            client = await self._get_client(service)
            # Ensure absolute path for output
            abs_output_path = os.path.abspath(output_path)
            
            # Override output folder in session config
            self.config.session.downloads.folder = abs_output_path
            logger.info(f"Targeting download folder: {abs_output_path}")
            
            # Force download even if in DB by bypassing the skip check in resolve()
            # We pass a temporary Database instance with a Dummy downloads interface.
            force_db = Database(Dummy(), self.db.failed)
            
            try:
                pending = PendingSingle(
                    id=str(track_id),
                    client=client,
                    config=self.config,
                    db=force_db
                )
                
                track_obj = await pending.resolve()
                if not track_obj:
                    return False, "Failed to resolve track metadata (resolve returned None)"
                    
                await track_obj.rip()
                # Clean up temporary artwork folders
                remove_artwork_tempdirs()
                return True, None
            finally:
                pass # No need to restore since we used a temporary Database object
            
        except Exception as e:
            # Fallback check: if it failed because it was already there
            if "already downloaded" in str(e).lower() or "marked as downloaded" in str(e).lower():
                return True, None
            logger.exception("Track download failed")
            return False, str(e)
    
    def download_track(self, track_id, service, output_path):
        return asyncio.run(self.download_track_async(track_id, service, output_path))
    
    async def download_album_async(self, album_id, service, output_path):
        try:
            client = await self._get_client(service)
            abs_output_path = os.path.abspath(output_path)
            self.config.session.downloads.folder = abs_output_path
            
            # Force download even if in DB
            force_db = Database(Dummy(), self.db.failed)
            
            try:
                pending = PendingAlbum(
                    id=str(album_id),
                    client=client,
                    config=self.config,
                    db=force_db
                )
                
                album_obj = await pending.resolve()
                if not album_obj:
                    return False, "Failed to resolve album metadata (resolve returned None)"
                    
                await album_obj.rip()
                # Clean up temporary artwork folders
                remove_artwork_tempdirs()
                return True, None
            finally:
                pass
            
        except Exception as e:
            if "already downloaded" in str(e).lower() or "marked as downloaded" in str(e).lower():
                return True, None
            logger.exception("Album download failed")
            return False, str(e)
    
    def download_album(self, album_id, service, output_path):
        return asyncio.run(self.download_album_async(album_id, service, output_path))
    
    def smart_search(self, query, content_type='track', use_fallback=True):
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
        
        return None, None, error or "No results found on any streaming service"
