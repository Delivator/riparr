# riparr

A music requester and download management system — **Like Jellyseerr but for music.**

Riparr allows users to search for and request songs, albums, and artists. It leverages [streamrip](https://github.com/nathom/streamrip) for automated downloading, with planned features for advanced metadata processing and Jellyfin library integration.

---

## 🚀 Features

- **Music Search & Request**: Search via MusicBrainz API for accurate metadata.
- **Automatic Downloading**: Seamlessly fetch music via Qobuz, Deezer, or Tidal.
- **Jellyfin Integration**: (Planned) Sync your existing library to prevent duplicate downloads.
- **Smart Metadata**: (Planned) Integrated post-processing with MusicBrainz Picard for perfect tags.
- **User Roles**: Separate admin and user accounts.

> **Note**: Post-processing and Jellyfin library integration are currently in development and not yet fully implemented.

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
- **Storage**: Customize how music is organized (e.g., `{artist}/{album}/{title}`) in the web settings.

---

## 🙏 Acknowledgments

This project relies heavily on the incredible work of the [streamrip](https://github.com/nathom/streamrip) project. Huge thanks to **nathom** and all the **streamrip contributors** for building the core engine that makes Riparr possible.

---

## ⚖️ Disclaimer & Warning

### ⚠️ Vibecoded
This project has been almost **100% vibecoded** with the help of **GitHub Copilot** and **Antigravity**. It is provided "as is", and I take no responsibility for any harm, data loss, or emotional distress caused by its use.

### ⚖️ Legal Disclaimer
Riparr is for educational and private use only. I cannot be held responsible for how this software is used. By using this software, you agree to comply with the Terms of Service of the streaming services you access. You are responsible for your own actions and any consequences that may arise from using this software.
