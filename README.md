# riparr

A music requester and download management system — **Like Jellyseerr but for music.**

Riparr allows users to search for and request songs, albums, and artists. It automatically downloads content using [streamrip](https://github.com/nathom/streamrip), processes metadata, and integrates with Jellyfin to avoid duplicate requests.

---

## 🚀 Features

- **Music Search & Request**: Search via MusicBrainz API for accurate metadata.
- **Automatic Downloading**: Seamlessly fetch music via Qobuz, Deezer, or Tidal.
- **Jellyfin Integration**: Sync your existing library to prevent duplicate downloads and show "Already Available" status.
- **Smart Metadata**: Integrated post-processing for perfect tags and artwork.
- **User Roles**: Separate admin and user accounts with Jellyfin OAuth support.

---

## 🛠️ Setup & Configuration

### 1. Credentials & Environment
Before running, you need to set up your environment:
```bash
cp .env.example .env
# Edit .env and set a secure SECRET_KEY
```

### 2. Streamrip Config
Create a `config` directory and add your `streamrip.toml` (requires valid streaming service accounts):
```bash
mkdir -p config
# Place your streamrip.toml in config/
```
*Refer to the [streamrip documentation](https://github.com/nathom/streamrip) for configuration details.*

---

## 💻 Development

### Local with `uv`
The recommended way to run the backend locally:
```bash
uv sync
uv run flask --app backend/app.py run --debug
```

### Containerized Environment
Running with the development overwrite allows for hot-reloading and easy dependency management:
```bash
# Using Podman (or docker compose)
podman compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

---

## 🏠 Production & NAS Deployment

For a stable service on a NAS or server, use the standard compose file.

### 1. Run the service
```bash
podman compose up -d
```

### 2. Initialize the Database
On your first deployment, run the initialization command:
```bash
podman compose exec app flask init-db
```

### 3. Example `docker-compose.yml` Structure
```yaml
services:
  app:
    image: riparr:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data                # Database and app state
      - /volume1/music:/media/Music      # Your music library path
      - ./config:/app/config             # streamrip.toml location
    environment:
      - SECRET_KEY=your_secret_here
      - MUSIC_OUTPUT_PATH=/media/Music
```

---

## ⚙️ Administration

- **Default Admin**: `admin` / `admin` (Change this immediately!)
- **Jellyfin**: Enter your `JELLYFIN_URL` and `JELLYFIN_API_KEY` in the admin settings to enable library syncing.
- **File Patterns**: Customize how music is organized (e.g., `{artist}/{album}/{title}`) in the web settings.

---

## 📄 License
MIT - Created by [Delivator](https://github.com/Delivator)
