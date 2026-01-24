# Riparr Setup Guide

This guide will walk you through setting up Riparr for the first time.

## Prerequisites

- Python 3.11 and [uv](https://docs.astral.sh/uv/) installed (or Podman)
- At least one streaming service account (Qobuz, Deezer, or Tidal)
- (Optional) Jellyfin server for library integration

## Quick Start with Podman

1. **Clone the repository**
   ```bash
   git clone https://github.com/Delivator/riparr.git
   cd riparr
   ```

2. **Configure Streamrip**
   ```bash
   cp config/streamrip.toml.example config/streamrip.toml
   # Edit config/streamrip.toml with your streaming service credentials
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Seed DB on first run**
   ```bash
   podman compose run --rm riparr flask init-db
   ```

4. **Start the application**
   ```bash
   podman compose up -d
   ```

5. **Access the application**
   - Open http://localhost:5000
   - Login with default credentials: `admin` / `admin`
   - **Important**: Change the admin password immediately!

## Detailed Setup

### 1. Streaming Service Configuration

Riparr uses [streamrip](https://github.com/nathom/streamrip) v2.1.0 to download music. You need to configure at least one streaming service:

#### Qobuz (Recommended for quality)
1. Sign up at https://www.qobuz.com/
2. Add your email and password to `config/streamrip.toml`:
   ```toml
   [session.qobuz]
   email_or_userid = "YOUR_EMAIL"
   password_or_token = "YOUR_PASSWORD"
   quality = 3
   ```
3. Set quality to 3 for highest quality (24bit/96kHz FLAC)

#### Deezer (Good fallback)
1. Login to Deezer in your browser
2. Open browser developer tools → Application → Cookies
3. Find the `arl` cookie value
4. Add to `config/streamrip.toml`:
   ```toml
   [session.deezer]
   arl = "YOUR_ARL_TOKEN"
   quality = 2
   ```

#### Tidal (Alternative)
1. Sign up at https://tidal.com/
2. Get your user ID and access token
3. Add to `config/streamrip.toml`:
   ```toml
   [session.tidal]
   user_id = "YOUR_USER_ID"
   access_token = "YOUR_ACCESS_TOKEN"
   quality = 3
   ```

### 2. Jellyfin Integration (Optional but Recommended)

If you have a Jellyfin server:

1. **Get your API Key**
   - Login to Jellyfin
   - Go to Dashboard → API Keys
   - Create a new API key for Riparr

2. **Configure in Riparr**
   - Set `JELLYFIN_URL` in `.env` or configure in admin panel
   - Set `JELLYFIN_API_KEY` in `.env`
   
3. **Sync Library**
   - Login to Riparr as admin
   - Go to Admin tab
   - Click "Test Connection" to verify
   - Click "Sync Library" to import existing content

### 3. Configure File Organization

Set up where and how music files should be organized:

**Output Path** (where files are stored):
```
MUSIC_OUTPUT_PATH=/media/Music
```

**Path Pattern** (how files are organized):
```
MUSIC_PATH_PATTERN={artist}/{artist} - {title}
```

Common patterns:
- `{artist}/{album}/{title}` → `Queen/A Night at the Opera/Bohemian Rhapsody`
- `{artist}/{artist} - {title}` → `Queen/Queen - Bohemian Rhapsody`
- `{artist}/{artist} - {album} - {title}` → `Queen/Queen - A Night at the Opera - Bohemian Rhapsody`

### 4. Streaming Service Priority

Configure primary and fallback streaming services:

```env
PRIMARY_STREAMING_SERVICE=qobuz
FALLBACK_STREAMING_SERVICE=deezer
```

Riparr will:
1. Try to find content on primary service
2. Fall back to secondary if not found
3. Use smart search (removing special characters if needed)

## Usage Workflow

### For Users

1. **Login**
   - Use local account or Jellyfin credentials
   
2. **Search for Music**
   - Go to "Search & Request" tab
   - Enter song, album, or artist name
   - View MusicBrainz results
   - Click "Request" on desired item

3. **Or Make Quick Request**
   - Fill in the quick request form
   - System checks if already available
   - Creates request if not found

4. **Track Your Requests**
   - Go to "My Requests" tab
   - See status of all your requests
   - Watch progress: Pending → Searching → Downloading → Processing → Completed

### For Admins

1. **Configure Settings**
   - Go to Admin tab
   - Set up Jellyfin connection
   - Configure streaming services
   - Set quality and path patterns
   - Save settings

2. **Process Requests**
   - View all pending requests
   - Click "Process" to start download
   - System will:
     - Search MusicBrainz for metadata
     - Find on streaming service
     - Download highest quality
     - Process with Picard (if enabled)
     - Move to organized location

3. **Manage Library**
   - Sync Jellyfin library regularly
   - Test connections
   - Monitor request status

## Troubleshooting

### Streamrip Not Working
```bash
# Test streamrip configuration
uv run python -c "from backend.streamrip_service import StreamripService; s = StreamripService(); print(s.search_track('test'))"
```

### Jellyfin Connection Failed
- Verify URL is accessible from container
- Check API key has correct permissions
- Ensure Jellyfin is running
- Test from admin panel

### Downloads Not Starting
- Check streaming service credentials
- Verify streamrip.toml is correct
- Check logs: `docker-compose logs -f`
- Ensure output directory is writable

### Authentication Issues
- Default admin: `admin` / `admin`
- Reset database if needed: delete `data/riparr.db` (will lose data!)
- For Jellyfin auth, verify server is accessible

## Advanced Configuration

### Environment Variables

See `.env.example` for all available options:

- `SECRET_KEY` - Flask secret (change in production!)
- `DATABASE_URL` - Database connection string
- `JELLYFIN_URL` - Jellyfin server URL
- `JELLYFIN_API_KEY` - Jellyfin API key
- `PRIMARY_STREAMING_SERVICE` - Primary download source
- `FALLBACK_STREAMING_SERVICE` - Fallback source
- `DOWNLOAD_QUALITY` - Quality setting (1-3)
- `MUSIC_OUTPUT_PATH` - Final file destination
- `MUSIC_PATH_PATTERN` - File organization pattern

### Docker Volumes

Configure in `docker-compose.yml`:

```yaml
volumes:
  - riparr-data:/app/data              # Database and app data
  - /your/music/path:/media/Music      # Music output directory
  - ./config:/app/config               # Streamrip configuration
```

### Production Deployment

For production use:

1. **Change secret key**
   ```env
   SECRET_KEY=your-strong-random-key-here
   ```

2. **Use external database**
   ```env
   DATABASE_URL=postgresql://user:pass@host:5432/riparr
   ```

3. **Set up reverse proxy** (nginx, Caddy, etc.)
   ```nginx
   location / {
       proxy_pass http://localhost:5000;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

4. **Enable HTTPS**

5. **Set up automated backups** of `/app/data`

## Support

- Issues: https://github.com/Delivator/riparr/issues
- Streamrip docs: https://github.com/nathom/streamrip/wiki
- MusicBrainz: https://musicbrainz.org/
- Jellyfin: https://jellyfin.org/docs/

## Security Notes

- Change default admin password immediately
- Use strong, unique passwords
- Keep streaming service credentials secure
- Use HTTPS in production
- Regularly update dependencies
- Backup database regularly
