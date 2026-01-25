import re

import musicbrainzngs as mb


class MusicBrainzService:
    def __init__(self):
        # Initialize MusicBrainz API
        mb.set_useragent("Riparr", "1.0.0", "https://github.com/Delivator/riparr")
    
    def search_song(self, title, artist=None, limit=10):
        """Search for a song/recording in MusicBrainz"""
        try:
            query_parts = [f'recording:"{title}"']
            if artist:
                query_parts.append(f'artist:"{artist}"')
            
            query = ' AND '.join(query_parts)
            
            result = mb.search_recordings(query=query, limit=limit)
            
            recordings = []
            for recording in result.get('recording-list', []):
                artist_name = None
                if recording.get('artist-credit'):
                    artist_name = recording['artist-credit'][0]['artist']['name']
                
                # Extract streaming URLs from relations
                streaming_urls = self._extract_streaming_urls(recording.get('url-relation-list', []))
                
                recordings.append({
                    'id': recording['id'],
                    'title': recording.get('title'),
                    'artist': artist_name,
                    'score': recording.get('ext:score', 0),
                    'streaming_urls': streaming_urls,
                    'length': recording.get('length'),  # in milliseconds
                })
            
            return recordings, None
        except Exception as e:
            return None, str(e)
    
    def search_album(self, title, artist=None, limit=10):
        """Search for an album/release-group in MusicBrainz"""
        try:
            query_parts = [f'releasegroup:"{title}"']
            if artist:
                query_parts.append(f'artist:"{artist}"')
            
            query = ' AND '.join(query_parts)
            
            result = mb.search_release_groups(query=query, limit=limit)
            
            albums = []
            for rg in result.get('release-group-list', []):
                artist_name = None
                if rg.get('artist-credit'):
                    artist_name = rg['artist-credit'][0]['artist']['name']
                
                # Get detailed info to find streaming URLs
                streaming_urls = {}
                try:
                    detailed = mb.get_release_group_by_id(
                        rg['id'], 
                        includes=['url-rels']
                    )
                    streaming_urls = self._extract_streaming_urls(
                        detailed.get('release-group', {}).get('url-relation-list', [])
                    )
                except:
                    pass
                
                albums.append({
                    'id': rg['id'],
                    'title': rg.get('title'),
                    'artist': artist_name,
                    'type': rg.get('type'),
                    'score': rg.get('ext:score', 0),
                    'streaming_urls': streaming_urls,
                    'first_release_date': rg.get('first-release-date'),
                })
            
            return albums, None
        except Exception as e:
            return None, str(e)
    
    def search_artist(self, name, limit=10):
        """Search for an artist in MusicBrainz"""
        try:
            result = mb.search_artists(artist=name, limit=limit)
            
            artists = []
            for artist in result.get('artist-list', []):
                artists.append({
                    'id': artist['id'],
                    'name': artist.get('name'),
                    'sort_name': artist.get('sort-name'),
                    'score': artist.get('ext:score', 0),
                    'type': artist.get('type'),
                    'country': artist.get('country'),
                })
            
            return artists, None
        except Exception as e:
            return None, str(e)
    
    def get_artist_releases(self, artist_id, limit=50):
        """Get all release groups (albums, singles, etc.) for an artist from MusicBrainz"""
        try:
            # We use browse_release_groups because search is better for text, 
            # browse is better for linking to an entity
            result = mb.browse_release_groups(artist=artist_id, limit=limit)
            
            release_groups = []
            for rg in result.get('release-group-list', []):
                release_groups.append({
                    'id': rg['id'],
                    'title': rg.get('title'),
                    'type': rg.get('type'),
                    'primary_type': rg.get('primary-type'),
                    'secondary_types': rg.get('secondary-type-list', []),
                    'first_release_date': rg.get('first-release-date'),
                })
            
            # Sort by date descending
            release_groups.sort(key=lambda x: x.get('first_release_date') or '', reverse=True)
            
            return release_groups, None
        except Exception as e:
            return None, str(e)
    
    def get_recording_details(self, recording_id):
        """Get detailed information about a recording"""
        try:
            result = mb.get_recording_by_id(
                recording_id,
                includes=['artists', 'releases', 'url-rels']
            )
            recording = result.get('recording', {})
            
            artist_name = None
            if recording.get('artist-credit'):
                artist_name = recording['artist-credit'][0]['artist']['name']
            
            streaming_urls = self._extract_streaming_urls(recording.get('url-relation-list', []))
            
            return {
                'id': recording['id'],
                'title': recording.get('title'),
                'artist': artist_name,
                'length': recording.get('length'),
                'streaming_urls': streaming_urls,
            }, None
        except Exception as e:
            return None, str(e)
    
    def get_release_group_details(self, release_group_id):
        """Get detailed information about a release group (album)"""
        try:
            result = mb.get_release_group_by_id(
                release_group_id,
                includes=['artists', 'url-rels']
            )
            rg = result.get('release-group', {})
            
            artist_name = None
            if rg.get('artist-credit'):
                artist_name = rg['artist-credit'][0]['artist']['name']
            
            streaming_urls = self._extract_streaming_urls(rg.get('url-relation-list', []))
            
            return {
                'id': rg['id'],
                'title': rg.get('title'),
                'artist': artist_name,
                'type': rg.get('type'),
                'streaming_urls': streaming_urls,
                'first_release_date': rg.get('first-release-date'),
            }, None
        except Exception as e:
            return None, str(e)
    
    def _extract_streaming_urls(self, url_relations):
        """Extract streaming service URLs from MusicBrainz URL relations"""
        streaming_urls = {}
        
        if not url_relations:
            return streaming_urls
        
        # Map of MusicBrainz relation types to service names
        service_patterns = {
            'qobuz': r'qobuz\.com',
            'deezer': r'deezer\.com',
            'tidal': r'tidal\.com',
            'spotify': r'spotify\.com',
            'youtube': r'youtube\.com|youtu\.be',
            'soundcloud': r'soundcloud\.com',
        }
        
        for relation in url_relations:
            url = relation.get('target', '')
            
            for service, pattern in service_patterns.items():
                if re.search(pattern, url, re.IGNORECASE):
                    streaming_urls[service] = url
                    break
        
        return streaming_urls
    
    @staticmethod
    def clean_search_query(query):
        """Clean search query by removing special characters"""
        # Remove special characters but keep spaces and alphanumeric
        cleaned = re.sub(r'[^\w\s-]', '', query)
        # Remove extra spaces
        cleaned = ' '.join(cleaned.split())
        return cleaned
