# Deploying Riparr on TrueNAS

TrueNAS (specifically SCALE) uses Docker/Kubernetes under the hood. You can deploy Riparr either via the "Custom App" feature or by using `podman compose` / `docker-compose` if you have shell access and a compatible environment.

## 1. Prerequisites
- A TrueNAS SCALE installation.
- A dataset for your music library (e.g., `/mnt/pool/media/Music`).
- A dataset for Riparr data and configuration (e.g., `/mnt/pool/apps/riparr`).

## 2. Configuration via Custom App (TrueNAS Dashboard)

When creating a "Custom App" for Riparr:

### Image Settings
- **Image Repository**: `riparr` (you'll need to build and push this to a registry or use a local build).
- **Image Tag**: `latest`

### Port Forwarding
- **Container Port**: `5000`
- **Node Port**: Pick an available port (e.g., `30050`).

### Environment Variables
Set the following variables:
- `SECRET_KEY`: A strong random string.
- `DATABASE_URL`: `sqlite:////app/data/riparr.db`
- `PRIMARY_STREAMING_SERVICE`: (e.g., `qobuz`)
- `FALLBACK_STREAMING_SERVICE`: (e.g., `deezer`)
- `MUSIC_OUTPUT_PATH`: `/media/Music`

### Storage/Volumes
Map your TrueNAS datasets to the container:
- **Mount Path**: `/app/data` -> Your Riparr data dataset (e.g., `/mnt/pool/apps/riparr/data`).
- **Mount Path**: `/app/config` -> Your Riparr config dataset (e.g., `/mnt/pool/apps/riparr/config`).
- **Mount Path**: `/media/Music` -> Your Music library dataset (e.g., `/mnt/pool/media/Music`).

## 3. Deployment via CLI (docker-compose)

If you prefer using the command line:

1.  Copy the `docker-compose.yml` to your TrueNAS server.
2.  Update the volume paths to match your TrueNAS datasets:
    ```yaml
    volumes:
      - /mnt/pool/apps/riparr/data:/app/data
      - /mnt/pool/media/Music:/media/Music
      - /mnt/pool/apps/riparr/config:/app/config
    ```
3.  Run the deployment:
    ```bash
    docker-compose up -d
    ```
4.  Initialize the database:
    ```bash
    docker-compose exec app flask init-db
    ```

## 4. Troubleshooting
- **Permissions**: Ensure the user running the container has write access to your datasets.
- **Logs**: Check app logs via the TrueNAS UI or `docker-compose logs -f`.
