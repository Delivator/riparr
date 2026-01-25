import os
import shutil
from flask import current_app
from backend.models import MusicRequest, RequestStatus, db
from backend.musicbrainz_service import MusicBrainzService
from backend.streamrip_service import StreamripService
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DownloadService:
    def __init__(self, config_path=None, primary_service=None, fallback_service=None, 
                 temp_path=None, output_path=None, path_pattern=None, socketio=None):
        """
        Initialize DownloadService with optional configuration.
        If parameters are None, they will be loaded from Flask config on first use.
        """
        self.mb_service = MusicBrainzService()
        self.streamrip_service = StreamripService(
            config_path=config_path,
            primary_service=primary_service,
            fallback_service=fallback_service
        )
        self.temp_path = temp_path
        self.output_path = output_path
        self.path_pattern = path_pattern
        self.socketio = socketio

    def _get_temp_path(self):
        if self.temp_path: return self.temp_path
        try:
            return current_app.config.get('TEMP_DOWNLOAD_PATH')
        except:
            return './downloads/temp'

    def _get_output_path(self):
        if self.output_path: return self.output_path
        try:
            return current_app.config.get('MUSIC_OUTPUT_PATH')
        except:
            return './music'

    def _get_path_pattern(self):
        if self.path_pattern: return self.path_pattern
        try:
            return current_app.config.get('MUSIC_PATH_PATTERN')
        except:
            return '{artist}/{artist} - {title}'

    def _emit_status_update(self, request):
        """Emit status update via WebSocket"""
        if self.socketio:
            try:
                self.socketio.emit('request_update', request.to_dict())
                logger.info(f"Emitted status update for request {request.id}: {request.status.value}")
            except Exception as e:
                logger.error(f"Failed to emit status update: {e}")
    
    def process_request(self, request_id):
        """Process a music request through the full workflow"""
        logger.info(f"Starting to process request {request_id}")
        request = MusicRequest.query.get(request_id)
        if not request:
            return False, "Request not found"
        
        try:
            # Update status to searching
            request.status = RequestStatus.SEARCHING
            request.error_message = None
            db.session.commit()
            self._emit_status_update(request)
            
            # Search and get metadata
            success, error = self._search_content(request)
            if not success:
                request.status = RequestStatus.FAILED
                request.error_message = error
                db.session.commit()
                self._emit_status_update(request)
                return False, error
            
            # Download content
            logger.info(f"Request {request_id}: Moving to DOWNLOADING status")
            request.status = RequestStatus.DOWNLOADING
            db.session.commit()
            self._emit_status_update(request)
            
            success, error = self._download_content(request)
            if not success:
                request.status = RequestStatus.FAILED
                request.error_message = error
                db.session.commit()
                self._emit_status_update(request)
                return False, error
            
            # Post-process with Picard
            if current_app.config.get('PICARD_ENABLED', True):
                request.status = RequestStatus.PROCESSING
                db.session.commit()
                self._emit_status_update(request)
                
                success, error = self._process_metadata(request)
                if not success:
                    # Continue even if metadata processing fails
                    print(f"Metadata processing warning: {error}")
            
            # Move to final destination
            success, error = self._move_to_destination(request)
            if not success:
                request.status = RequestStatus.FAILED
                request.error_message = error
                db.session.commit()
                self._emit_status_update(request)
                return False, error
            
            # Mark as completed
            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            db.session.commit()
            self._emit_status_update(request)
            
            return True, None
        
        except Exception as e:
            logger.exception(f"Unexpected error processing request {request_id}")
            request.status = RequestStatus.FAILED
            request.error_message = str(e)
            db.session.commit()
            self._emit_status_update(request)
            return False, str(e)
    
    def _search_content(self, request):
        """Search for content using streaming services and match with MusicBrainz"""
        # 1. Ensure we have a streaming URL and service
        if not request.streaming_url or not request.streaming_service:
            # Search on streaming services using smart search
            query = f"{request.title}"
            if request.artist:
                query += f" {request.artist}"
            
            content_type = 'track' if request.content_type.value == 'song' else 'album'
            
            logger.info(f"Searching streaming services for: {query}")
            results, service, error = self.streamrip_service.smart_search(query, content_type)
            
            if not results:
                return False, error or "No results found on streaming services"
            
            # Use the first result
            best_match = results[0]
            request.streaming_service = service
            request.streaming_url = best_match.get('id')
            
            # Update metadata from search result if missing
            if not request.title and best_match.get('title'):
                request.title = best_match.get('title')
            if not request.artist and best_match.get('artist'):
                request.artist = best_match.get('artist')
            if not request.album and best_match.get('album'):
                request.album = best_match.get('album')
            
            db.session.commit()

        # 2. Try to match with MusicBrainz for better tagging if IDs are missing
        if not request.musicbrainz_id and not request.musicbrainz_release_group_id:
            logger.info(f"Attempting to match {request.title} - {request.artist} with MusicBrainz")
            try:
                if request.content_type.value == 'song':
                    mb_results, mb_error = self.mb_service.search_song(request.title, request.artist, limit=1)
                    if mb_results:
                        request.musicbrainz_id = mb_results[0]['id']
                        logger.info(f"Found MusicBrainz match for song: {request.musicbrainz_id}")
                else:  # album
                    mb_results, mb_error = self.mb_service.search_album(request.title, request.artist, limit=1)
                    if mb_results:
                        request.musicbrainz_release_group_id = mb_results[0]['id']
                        logger.info(f"Found MusicBrainz match for album: {request.musicbrainz_release_group_id}")
                
                db.session.commit()
            except Exception as e:
                logger.warning(f"MusicBrainz matching failed: {e}")
        
        return True, None
    
    def _download_content(self, request):
        """Download content from streaming service"""
        if not request.streaming_service or not request.streaming_url:
            return False, "No streaming source available"
        
        # Create temp directory
        abs_temp_path = os.path.abspath(self._get_temp_path())
        os.makedirs(abs_temp_path, exist_ok=True)
        
        temp_download_path = os.path.join(abs_temp_path, f"request_{request.id}")
        os.makedirs(temp_download_path, exist_ok=True)
        
        # Download based on content type
        if request.content_type.value == 'song':
            success, error = self.streamrip_service.download_track(
                request.streaming_url,
                request.streaming_service,
                temp_download_path
            )
        else:  # album
            success, error = self.streamrip_service.download_album(
                request.streaming_url,
                request.streaming_service,
                temp_download_path
            )
        
        if not success:
            return False, error
        
        # Check if files were actually produced
        has_files = False
        for root, dirs, filenames in os.walk(temp_download_path):
            if filenames:
                has_files = True
                break
        
        if not has_files:
            return False, "Download succeeded but no files were produced (likely skipped by streaming service)"
        
        request.download_path = temp_download_path
        db.session.commit()
        
        return True, None
    
    def _process_metadata(self, request):
        """Process metadata using MusicBrainz Picard"""
        if not request.download_path or not os.path.exists(request.download_path):
            return False, "Download path not found"
        
        try:
            # This is a simplified version. In production, you would use the
            # picard library to actually process the files
            # For now, we'll just pass through
            
            # from picard import Picard, File
            # picard = Picard()
            # for file in files_in_download_path:
            #     picard.load(file)
            #     picard.analyze()
            #     picard.save()
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _move_to_destination(self, request):
        """Move downloaded files to final destination with custom path pattern"""
        if not request.download_path or not os.path.exists(request.download_path):
            return False, "Download path not found"
        
        try:
            # Check if the downloader already created a folder structure (common for albums)
            # If so, we want to NOT nest it inside our own pattern.
            has_subfolders = False
            top_level_items = os.listdir(request.download_path)
            for item in top_level_items:
                if os.path.isdir(os.path.join(request.download_path, item)):
                    has_subfolders = True
                    break

            if has_subfolders and request.content_type.value == 'album':
                logger.info("Detected pre-structured album download. Moving contents using pattern.")
                dest_path = self._build_destination_path(request)
                
                # If Streamrip created a single album folder inside our temp dir,
                # we want to move its CONTENTS into dest_path to avoid "music/Artist/Album/Album"
                folders = [i for i in top_level_items if os.path.isdir(os.path.join(request.download_path, i))]
                
                if len(folders) == 1:
                    album_src = os.path.join(request.download_path, folders[0])
                    os.makedirs(dest_path, exist_ok=True)
                    for item in os.listdir(album_src):
                        src = os.path.join(album_src, item)
                        dst = os.path.join(dest_path, item)
                        if os.path.isdir(src) and os.path.exists(dst):
                            self._merge_directories(src, dst)
                        else:
                            shutil.move(src, dst)
                else:
                    # Move everything from download_path to dest_path
                    os.makedirs(dest_path, exist_ok=True)
                    for item in top_level_items:
                        src = os.path.join(request.download_path, item)
                        dst = os.path.join(dest_path, item)
                        if os.path.isdir(src) and os.path.exists(dst):
                            self._merge_directories(src, dst)
                        else:
                            shutil.move(src, dst)
                
                request.download_path = dest_path
            else:
                # Build destination path using pattern for tracks or unstructured albums
                dest_path = self._build_destination_path(request)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                if os.path.isdir(request.download_path):
                    if os.path.exists(dest_path):
                        shutil.rmtree(dest_path)
                    shutil.move(request.download_path, dest_path)
                else:
                    shutil.move(request.download_path, dest_path)
                
                request.download_path = dest_path
            
            # Calculate file size
            if os.path.isdir(request.download_path):
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(request.download_path)
                    for filename in filenames
                )
                request.file_size = total_size
            else:
                request.file_size = os.path.getsize(request.download_path)
            
            db.session.commit()
            return True, None
        except Exception as e:
            logger.exception("Failed to move files to destination")
            return False, str(e)

    def _merge_directories(self, src, dst):
        """Recursively merge directories from src to dst"""
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                if os.path.exists(d):
                    self._merge_directories(s, d)
                else:
                    shutil.move(s, d)
            else:
                if os.path.exists(d):
                    os.remove(d)
                shutil.move(s, d)
    
    def _build_destination_path(self, request):
        """Build destination path using pattern"""
        pattern = self._get_path_pattern()
        
        # Replace placeholders
        replacements = {
            '{artist}': request.artist or 'Unknown Artist',
            '{title}': request.title,
            '{album}': request.album or '',
        }
        
        for placeholder, value in replacements.items():
            pattern = pattern.replace(placeholder, self._sanitize_path(value))
        
        return os.path.join(self._get_output_path(), pattern)
    
    def _sanitize_path(self, path):
        """Sanitize path component"""
        # Remove invalid characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            path = path.replace(char, '')
        
        # Remove leading/trailing spaces and dots
        path = path.strip('. ')
        
        return path
