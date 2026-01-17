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
                 temp_path=None, output_path=None, path_pattern=None):
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
        self.temp_path = temp_path or '/tmp/riparr/downloads'
        self.output_path = output_path or '/media/Music'
        self.path_pattern = path_pattern or '{artist}/{artist} - {title}'
    
    def process_request(self, request_id):
        """Process a music request through the full workflow"""
        logger.info(f"Starting to process request {request_id}")
        request = MusicRequest.query.get(request_id)
        if not request:
            return False, "Request not found"
        
        try:
            # Update status to searching
            request.status = RequestStatus.SEARCHING
            db.session.commit()
            
            # Search and get metadata
            success, error = self._search_content(request)
            if not success:
                request.status = RequestStatus.FAILED
                request.error_message = error
                db.session.commit()
                return False, error
            
            # Download content
            logger.info(f"Request {request_id}: Moving to DOWNLOADING status")
            request.status = RequestStatus.DOWNLOADING
            db.session.commit()
            
            success, error = self._download_content(request)
            if not success:
                request.status = RequestStatus.FAILED
                request.error_message = error
                db.session.commit()
                return False, error
            
            # Post-process with Picard
            if current_app.config.get('PICARD_ENABLED', True):
                request.status = RequestStatus.PROCESSING
                db.session.commit()
                
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
                return False, error
            
            # Mark as completed
            request.status = RequestStatus.COMPLETED
            request.completed_at = datetime.utcnow()
            db.session.commit()
            
            return True, None
        
        except Exception as e:
            logger.exception(f"Unexpected error processing request {request_id}")
            request.status = RequestStatus.FAILED
            request.error_message = str(e)
            db.session.commit()
            return False, str(e)
    
    def _search_content(self, request):
        """Search for content using MusicBrainz and streaming services"""
        # If we already have streaming URL from MusicBrainz, use it
        if request.streaming_url:
            return True, None
        
        # Search on streaming services using smart search
        query = f"{request.title}"
        if request.artist:
            query += f" {request.artist}"
        
        content_type = 'track' if request.content_type.value == 'song' else 'album'
        
        results, service, error = self.streamrip_service.smart_search(query, content_type)
        
        if not results:
            return False, error or "No results found"
        
        # Use the first result
        best_match = results[0]
        request.streaming_service = service
        request.streaming_url = best_match.get('id')  # Store the ID for download
        db.session.commit()
        
        return True, None
    
    def _download_content(self, request):
        """Download content from streaming service"""
        if not request.streaming_service or not request.streaming_url:
            return False, "No streaming source available"
        
        # Create temp directory
        abs_temp_path = os.path.abspath(self.temp_path)
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
            # Build destination path using pattern
            dest_path = self._build_destination_path(request)
            
            # Create destination directory
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Move files
            if os.path.isdir(request.download_path):
                # Move entire directory
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.move(request.download_path, dest_path)
            else:
                # Move single file
                shutil.move(request.download_path, dest_path)
            
            request.download_path = dest_path
            
            # Calculate file size
            if os.path.isdir(dest_path):
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(dest_path)
                    for filename in filenames
                )
                request.file_size = total_size
            else:
                request.file_size = os.path.getsize(dest_path)
            
            db.session.commit()
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _build_destination_path(self, request):
        """Build destination path using pattern"""
        pattern = self.path_pattern
        
        # Replace placeholders
        replacements = {
            '{artist}': request.artist or 'Unknown Artist',
            '{title}': request.title,
            '{album}': request.album or '',
        }
        
        for placeholder, value in replacements.items():
            pattern = pattern.replace(placeholder, self._sanitize_path(value))
        
        return os.path.join(self.output_path, pattern)
    
    def _sanitize_path(self, path):
        """Sanitize path component"""
        # Remove invalid characters
        invalid_chars = '<>:"|?*'
        for char in invalid_chars:
            path = path.replace(char, '')
        
        # Remove leading/trailing spaces and dots
        path = path.strip('. ')
        
        return path
