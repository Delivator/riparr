# riparr
A music requester and download management system - Like Jellyseerr but for music

## Overview

Riparr is a comprehensive music request and download management system that allows users to search for and request songs, albums, and artists. It automatically downloads content from streaming services using [streamrip](https://github.com/nathom/streamrip), processes metadata with MusicBrainz Picard, and integrates with Jellyfin to show already available content.

## Features

### 🎵 Music Management
- Request songs, albums, or artists
- Search using MusicBrainz API for accurate metadata
- Automatic download from streaming services (Qobuz, Deezer, Tidal, etc.)
- Smart search with primary and fallback streaming services
- Post-processing with MusicBrainz Picard for perfect metadata
- Custom file organization with configurable path patterns

### 👥 User Management
- Local username/password authentication
- Jellyfin authentication integration
- Admin and regular user roles
- Per-user request tracking

### 📚 Jellyfin Integration
- Show already available content from Jellyfin library
- Automatic library syncing
- Prevent duplicate downloads

### ⚙️ Admin Configuration
- Configure streaming services and quality settings
- Set primary and fallback download sources
- Customize file organization patterns
- Manage user accounts

## Architecture

```
riparr/
├── backend/
│   ├── app.py                    # Main Flask application
│   ├── models.py                 # Database models (User, Request, Settings)
│   ├── config.py                 # Configuration management
│   ├── auth_service.py           # Authentication (Local + Jellyfin)
│   ├── musicbrainz_service.py    # MusicBrainz API integration
│   ├── streamrip_service.py      # Streamrip integration
│   ├── jellyfin_service.py       # Jellyfin library integration
│   └── download_service.py       # Download workflow orchestration
├── frontend/
│   ├── static/
│   │   ├── app.js                # Frontend JavaScript
│   │   └── style.css             # CSS styles
│   └── templates/
│       └── index.html            # Main HTML template
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Docker configuration
├── docker-compose.yml            # Docker Compose configuration
├── .env.example                  # Example environment variables
└── README.md                     # This file
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (optional, for containerized deployment)
- Streamrip configuration with API credentials for streaming services
- Jellyfin server (optional, but recommended)

### Environment Configuration

1. **Copy the example environment file**
   ```bash
   cp .env.example .env
   ```

2. **Edit .env with your configuration**
   ```bash
   # Required: Set a secure secret key
   SECRET_KEY=your-random-secret-key-here
   
   # Optional: Configure Jellyfin
   JELLYFIN_URL=http://your-jellyfin-server:8096
   JELLYFIN_API_KEY=your-jellyfin-api-key
   
   # Configure streaming services
   PRIMARY_STREAMING_SERVICE=qobuz
   FALLBACK_STREAMING_SERVICE=deezer
   ```

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/Delivator/riparr.git
   cd riparr
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Streamrip configuration**
   ```bash
   mkdir -p config
   # Place your streamrip.toml in the config directory
   # See: https://github.com/nathom/streamrip for configuration details
   ```

5. **Run the application**
   ```bash
   python backend/app.py
   ```

6. **Access the application**
   Open your browser and navigate to `http://localhost:5000`
   
   Default admin credentials:
   - Username: `admin`
   - Password: `admin`
   
   **⚠️ Change these immediately after first login!**

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Configure volumes in docker-compose.yml**
   ```yaml
   volumes:
     - riparr-data:/app/data                    # Database and app data
     - /path/to/music:/media/Music              # Music output directory
     - /path/to/config:/app/config              # Streamrip config
   ```

3. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

4. **Stop the application**
   ```bash
   docker-compose down
   ```

## Configuration

### Streaming Services

Riparr uses [streamrip](https://github.com/nathom/streamrip) for downloading from streaming services. You need to:

1. Create a `config/streamrip.toml` file with your streaming service credentials
2. Configure at least one streaming service (Qobuz, Deezer, Tidal, etc.)
3. See the [streamrip wiki](https://github.com/nathom/streamrip/wiki) for detailed configuration

### File Organization

Customize the output path pattern in settings or via environment variables:

```bash
MUSIC_PATH_PATTERN="{artist}/{artist} - {title}"
```

Available placeholders:
- `{artist}` - Artist name
- `{title}` - Song/album title
- `{album}` - Album name

Example patterns:
- `{artist}/{album}/{title}` → `Queen/A Night at the Opera/Bohemian Rhapsody`
- `{artist}/{artist} - {title}` → `Queen/Queen - Bohemian Rhapsody`

### Jellyfin Integration

To integrate with Jellyfin:

1. Set `JELLYFIN_URL` to your Jellyfin server URL
2. Create an API key in Jellyfin dashboard (Dashboard → API Keys)
3. Set `JELLYFIN_API_KEY` with the generated key
4. Sync library from admin panel: Settings → Sync Jellyfin Library

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (local or Jellyfin)
- `POST /api/auth/register` - Register new local user
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user info

### Music Requests
- `GET /api/requests` - Get all requests
- `POST /api/requests` - Create a new request
- `GET /api/requests/<id>` - Get specific request
- `POST /api/requests/<id>/process` - Process a request (admin)

### Search
- `GET /api/search/musicbrainz?query=<query>&type=<song|album|artist>` - Search MusicBrainz
- `GET /api/search/streaming?query=<query>&type=<track|album>` - Search streaming services
- `GET /api/search/jellyfin?query=<query>` - Search Jellyfin library

### Admin
- `GET /api/admin/settings` - Get all settings
- `PUT /api/admin/settings` - Update settings
- `POST /api/admin/jellyfin/sync` - Sync Jellyfin library
- `POST /api/admin/jellyfin/test` - Test Jellyfin connection

## Workflow

1. **User requests music**
   - Searches for song/album/artist
   - Checks if already available in Jellyfin
   - Creates request if not available

2. **Admin processes request** (or automatic with task queue)
   - Search MusicBrainz for accurate metadata
   - Find on streaming service (primary → fallback)
   - Use direct streaming URLs from MusicBrainz if available
   - Smart search with special character handling

3. **Download**
   - Download from streaming service using streamrip
   - Highest quality settings

4. **Post-process**
   - Process with MusicBrainz Picard for metadata
   - Apply tags, artwork, etc.

5. **Organize**
   - Move to final destination
   - Apply custom path pattern
   - Update Jellyfin library

## Development

### Database Models

- **User** - User accounts (local or Jellyfin)
- **MusicRequest** - Music download requests
- **Settings** - Application configuration
- **JellyfinLibrary** - Synced Jellyfin content

### Adding Features

The application is structured with service classes for each integration:
- `auth_service.py` - Authentication logic
- `musicbrainz_service.py` - MusicBrainz API
- `streamrip_service.py` - Streamrip integration
- `jellyfin_service.py` - Jellyfin API
- `download_service.py` - Download workflow

## Troubleshooting

### Streamrip Configuration Issues
- Ensure `config/streamrip.toml` exists and is valid
- Check streaming service credentials
- Run `streamrip test` to verify setup

### Jellyfin Connection Issues
- Verify `JELLYFIN_URL` is accessible from the container/host
- Ensure API key has necessary permissions
- Use the test endpoint: `POST /api/admin/jellyfin/test`

### Download Failures
- Check streaming service availability
- Verify fallback service is configured
- Check logs for specific error messages
- Ensure output directory is writable

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [streamrip](https://github.com/nathom/streamrip) - Music downloading
- [MusicBrainz](https://musicbrainz.org/) - Music metadata
- [Jellyfin](https://jellyfin.org/) - Media server
- [Jellyseerr](https://github.com/Fallenbagel/jellyseerr) - Inspiration
