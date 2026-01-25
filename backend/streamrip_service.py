import os
import asyncio
import logging
import shutil
import copy
import re
from contextlib import nullcontext

logger = logging.getLogger(__name__)
logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)

# --- MONKEYPATCHES (Apply BEFORE any other streamrip imports) ---
import streamrip.media.semaphore
import streamrip.media.artwork

# 1. Monkeypatch streamrip's global semaphore to be loop-local and thread-safe
_loop_semaphores = {}

def patched_global_download_semaphore(c):
    try:
        loop = asyncio.get_running_loop()
        if loop not in _loop_semaphores:
            if c.concurrency:
                max_connections = c.max_connections if c.max_connections > 0 else 1
            else:
                max_connections = 1
                
            if max_connections <= 0:
                return nullcontext()
            _loop_semaphores[loop] = asyncio.Semaphore(max_connections)
        return _loop_semaphores[loop]
    except RuntimeError:
        return nullcontext()

streamrip.media.semaphore.global_download_semaphore = patched_global_download_semaphore

# 2. Patch artwork cleanup to be a no-op to prevent race conditions
streamrip.media.artwork.remove_artwork_tempdirs = lambda: None

# Now we can safely import other streamrip modules
from streamrip.client import QobuzClient, DeezerClient, TidalClient
from streamrip.config import Config as StreamripConfig
from streamrip.db import Database, Downloads, Failed, Dummy
from streamrip.media.track import PendingSingle
from streamrip.media.album import PendingAlbum
from streamrip.media import remove_artwork_tempdirs # This is now our no-op

# Also explicitly patch the references in track and album modules
import streamrip.media.track
import streamrip.media.album
streamrip.media.track.global_download_semaphore = patched_global_download_semaphore
streamrip.media.album.global_download_semaphore = patched_global_download_semaphore
# -----------------------------------------------------------------

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
        current_loop = None
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if not self._config_loaded or (current_loop and getattr(self, '_loop', None) != current_loop):
            self._load_config()
            self._init_db()
            self._config_loaded = True
            self._loop = current_loop
            # No need to manually reset semaphore anymore since it's patched

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
        
        self._fix_config()

    def _fix_config(self):
        """Automatically fix common configuration issues"""
        if not self.config:
            return
            
        # 1. Qobuz MD5 Password Hashing
        try:
            import re
            import hashlib
            c = self.config.session.qobuz
            if not c.use_auth_token and c.password_or_token:
                # Check if it's a 32-character hex string (MD5)
                if not re.match(r'^[a-fA-F0-9]{32}$', str(c.password_or_token)):
                    logger.info("Qobuz password provided in cleartext. Hashing it for compatibility.")
                    hashed = hashlib.md5(c.password_or_token.encode('utf-8')).hexdigest()
                    c.password_or_token = hashed
        except Exception as e:
            logger.warning(f"Failed to auto-fix Qobuz config: {e}")
    
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
    
    async def _get_client(self, service, config=None):
        """Create the appropriate client for the streaming service"""
        self._ensure_config_loaded()
        use_config = config or self.config
        
        if service == 'qobuz':
            client = QobuzClient(use_config)
        elif service == 'deezer':
            client = DeezerClient(use_config)
        elif service == 'tidal':
            client = TidalClient(use_config)
        else:
            raise ValueError(f"Unsupported service: {service}")
            
        # Login
        try:
            await client.login()
        except Exception as e:
            error_msg = str(e)
            if service == 'qobuz' and 'AuthenticationError' in error_msg:
                error_msg = ("Qobuz authentication failed. Please check your email and password. "
                            "Note: Passwords must be exactly as set on Qobuz. "
                            "If you believe they are correct, please try clearing the app_id and secrets in your config.")
            elif service == 'deezer' and 'arl' in error_msg.lower():
                 error_msg = "Deezer authentication failed. Your ARL token might be invalid or expired."
            
            logger.error(f"Login failed for {service}: {error_msg}")
            raise Exception(error_msg)
            
        return client
    
    async def search_track_async(self, query, service=None, limit=10):
        """Search for a track on a streaming service"""
        service = service or self.primary_service
        client = None
        try:
            client = await self._get_client(service)
            results = await client.search('track', query, limit=limit)
            
            tracks = []
            for item in results:
                tracks.append(self._normalize_track(item, service)) # Changed to _normalize_track
            
            return tracks, None
        except Exception as e:
            logger.exception("Track search failed")
            return None, str(e)
        finally:
            if client and hasattr(client, 'session'):
                await client.session.close()
            
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

        # Extract explicit info
        explicit = item.get('explicit_lyrics') or item.get('parental_warning') or item.get('explicit')
        if explicit is None and isinstance(item.get('album'), dict):
            explicit = item['album'].get('explicit_lyrics') or item['album'].get('parental_warning')
            
        return {
            'id': str(item.get('id')),
            'title': item.get('title') or item.get('name'),
            'artist': self._extract_artist(item),
            'artist_id': self._extract_artist_id(item),
            'album': self._extract_album_title(item),
            'album_id': str(item.get('album', {}).get('id')) if isinstance(item.get('album'), dict) else None,
            'duration': item.get('duration'),
            'duration_ms': item.get('duration') * 1000 if isinstance(item.get('duration'), (int, float)) else None,
            'quality': quality_label,
            'explicit': bool(explicit),
            'version': item.get('version'),
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
        # Try direct artist field
        if 'artist' in result:
            artist = result['artist']
            if isinstance(artist, dict):
                return artist.get('name', '')
            return str(artist)
            
        # Try performer field (common in Qobuz for tracks)
        if 'performer' in result:
            performer = result['performer']
            if isinstance(performer, dict):
                return performer.get('name', '')
            return str(performer)
            
        # Try artists list
        if 'artists' in result and result['artists']:
            if isinstance(result['artists'][0], dict):
                return result['artists'][0].get('name', '')
            return str(result['artists'][0])
            
        # Fallback to album artist if track has no artist
        if 'album' in result and isinstance(result['album'], dict):
            album_artist = result['album'].get('artist')
            if isinstance(album_artist, dict):
                return album_artist.get('name', '')
            if album_artist:
                return str(album_artist)

        return 'Unknown Artist'

    def _extract_artist_id(self, result):
        if 'artist' in result:
            artist = result['artist']
            if isinstance(artist, dict):
                return str(artist.get('id', ''))
            return None
        
        if 'performer' in result:
            performer = result['performer']
            if isinstance(performer, dict):
                return str(performer.get('id', ''))
            return None
            
        if 'artists' in result and result['artists']:
            if isinstance(result['artists'][0], dict):
                return str(result['artists'][0].get('id', ''))
            
        if 'album' in result and isinstance(result['album'], dict):
            album_artist = result['album'].get('artist')
            if isinstance(album_artist, dict):
                return str(album_artist.get('id', ''))
                
        return None

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
        """Search for an album on a streaming service"""
        service = service or self.primary_service
        client = None
        try:
            client = await self._get_client(service)
            results = await client.search('album', query, limit=limit)
            
            # Since client.search might return pages or items depending on implementation, 
            # we need to be careful. In streamrip v2, search() usually returns a list of results 
            # for some clients or a list of pages for others. 
            # Actually, streamrip v2's Client._paginate returns a list of pages.
            
            albums = []
            for page in results:
                items = self._extract_search_items(page, service, 'album')
                for item in items:
                    albums.append(self._normalize_album(item, service))
            
            return albums[:limit], None
        except Exception as e:
            logger.exception("Album search failed")
            return None, str(e)
        finally:
            if client and hasattr(client, 'session'):
                await client.session.close()

    def search_album(self, query, service=None, limit=10):
        return asyncio.run(self.search_album_async(query, service, limit))

    async def get_artist_albums_async(self, artist_id, service=None, limit=50):
        """Fetch all albums/singles for an artist from a streaming service"""
        service = service or self.primary_service
        client = None
        try:
            client = await self._get_client(service)
            resp = await client.get_metadata(artist_id, 'artist')
            
            items = []
            if service == 'qobuz':
                items = resp.get('albums', {}).get('items', [])
            elif service == 'deezer':
                items = resp.get('albums', [])
            elif service == 'tidal':
                items = resp.get('albums', [])
            else:
                return None, f"Discovery not supported for {service}"
                
            albums = []
            for item in items:
                albums.append(self._normalize_album(item, service))
            
            return albums[:limit], None
        except Exception as e:
            logger.exception(f"Artist albums fetch failed for {service}")
            return None, str(e)
        finally:
            if client and hasattr(client, 'session'):
                await client.session.close()

    def get_artist_albums(self, artist_id, service=None, limit=50):
        return asyncio.run(self.get_artist_albums_async(artist_id, service, limit))

    def _normalize_album(self, item, service):
        """Extract album info consistently"""
        # Robust date/year extraction
        date_str = item.get('release_date') or item.get('release_date_original') or item.get('released_at')
        year = item.get('year')
        if not year and date_str and len(str(date_str)) >= 4:
            year = str(date_str)[:4]

        # Extract quality info
        quality = item.get('maximum_bit_depth') or item.get('quality')
        sampling_rate = item.get('maximum_sampling_rate')
        quality_label = str(quality) if quality else "Unknown"
        if quality and sampling_rate:
            quality_label = f"{quality}B-{sampling_rate}kHz"

        # Extract explicit info
        explicit = item.get('explicit_lyrics') or item.get('parental_warning') or item.get('explicit')

        return {
            'id': str(item.get('id')),
            'title': item.get('title') or item.get('name'),
            'artist': self._extract_artist(item),
            'artist_id': self._extract_artist_id(item),
            'year': year,
            'track_count': item.get('track_count') or item.get('tracks_count') or item.get('nb_tracks'),
            'quality': quality_label,
            'explicit': bool(explicit),
            'version': item.get('version'),
            'service': service,
            'cover_url': self._extract_cover_url(item, service),
            'release_date': date_str,
        }

    async def download_track_async(self, track_id, service, output_path):
        """Download a track from a streaming service"""
        try:
            self._ensure_config_loaded()
            # Deep copy config to be thread-safe/loop-safe
            local_config = copy.deepcopy(self.config)
            
            client = await self._get_client(service, local_config)
            # Ensure absolute path for output
            abs_output_path = os.path.abspath(output_path)
            
            # Override output folder in local session config
            local_config.session.downloads.folder = abs_output_path
            logger.info(f"Targeting download folder: {abs_output_path}")
            
            # Force download even if in DB
            force_db = Database(Dummy(), self.db.failed)
            
            try:
                pending = PendingSingle(
                    id=str(track_id),
                    client=client,
                    config=local_config,
                    db=force_db
                )
                
                track_obj = await pending.resolve()
                if not track_obj:
                    return False, "Failed to resolve track metadata (resolve returned None)"
                    
                await track_obj.rip()
                
                # Verify that the file was actually produced
                if not os.path.exists(track_obj.download_path):
                    return False, "Download failed (output file missing)"
                
                # Manual cleanup of __artwork folder if it exists in track folder
                artwork_dir = os.path.join(track_obj.folder, "__artwork")
                if os.path.exists(artwork_dir):
                    try:
                        shutil.rmtree(artwork_dir)
                        logger.debug(f"Cleaned up {artwork_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {artwork_dir}: {e}")
                    
                return True, None
            finally:
                if client and hasattr(client, 'session'):
                    await client.session.close()
            
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
            self._ensure_config_loaded()
            # Deep copy config to be thread-safe/loop-safe
            local_config = copy.deepcopy(self.config)
            
            client = await self._get_client(service, local_config)
            abs_output_path = os.path.abspath(output_path)
            local_config.session.downloads.folder = abs_output_path
            local_config.session.downloads.source_subdirectories = False
            
            # Force download even if in DB
            force_db = Database(Dummy(), self.db.failed)
            
            try:
                pending = PendingAlbum(
                    id=str(album_id),
                    client=client,
                    config=local_config,
                    db=force_db
                )
                
                album_obj = await pending.resolve()
                if not album_obj:
                    return False, "Failed to resolve album metadata (resolve returned None)"
                    
                expected_tracks = len(album_obj.tracks)
                await album_obj.rip()
                
                # Check for files in the album folder
                actual_files = 0
                for root, dirs, filenames in os.walk(album_obj.folder):
                    for f in filenames:
                        if f.lower().endswith(('.flac', '.mp3', '.m4a', '.alac', '.ogg', '.wav', '.wma', '.aac', '.opus')):
                            actual_files += 1
                
                if actual_files == 0:
                    return False, "Album download failed (no files produced)"
                elif actual_files < expected_tracks:
                    return False, f"Incomplete download: {actual_files}/{expected_tracks} tracks saved"
                
                # Manual cleanup of __artwork folder if it exists in album folder
                artwork_dir = os.path.join(album_obj.folder, "__artwork")
                if os.path.exists(artwork_dir):
                    try:
                        shutil.rmtree(artwork_dir)
                        logger.debug(f"Cleaned up {artwork_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to cleanup {artwork_dir}: {e}")
                    
                return True, None
            finally:
                if client and hasattr(client, 'session'):
                    await client.session.close()
            
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
