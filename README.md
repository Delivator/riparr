# riparr
A music requester app - A simple Python web application with backend and frontend

## Features

- 🎵 Request music tracks with song name, artist, and requester information
- 📋 View all music requests in real-time
- 🎨 Modern, responsive UI with gradient design
- 🐳 Docker support for easy deployment
- 🚀 RESTful API backend built with Flask

## Project Structure

```
riparr/
├── backend/
│   └── app.py              # Flask backend application
├── frontend/
│   ├── static/
│   │   ├── app.js          # Frontend JavaScript
│   │   └── style.css       # CSS styles
│   └── templates/
│       └── index.html      # Main HTML template
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
└── README.md              # This file
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose (optional, for containerized deployment)

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

4. **Run the application**
   ```bash
   python backend/app.py
   ```

5. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

2. **Access the application**
   Open your browser and navigate to `http://localhost:5000`

3. **Stop the application**
   ```bash
   docker-compose down
   ```

### Alternative: Build Docker image manually

1. **Build the Docker image**
   ```bash
   docker build -t riparr:latest .
   ```

2. **Run the container**
   ```bash
   docker run -p 5000:5000 riparr:latest
   ```

## API Endpoints

- `GET /` - Serve the main frontend page
- `GET /api/health` - Health check endpoint
- `GET /api/requests` - Get all music requests
- `POST /api/requests` - Create a new music request

### Example API Usage

**Create a music request:**
```bash
curl -X POST http://localhost:5000/api/requests \
  -H "Content-Type: application/json" \
  -d '{
    "song": "Bohemian Rhapsody",
    "artist": "Queen",
    "requester": "John Doe"
  }'
```

**Get all requests:**
```bash
curl http://localhost:5000/api/requests
```

## Development

### Adding New Features

1. Backend: Modify `backend/app.py` to add new API endpoints
2. Frontend: Update files in `frontend/` directory
   - `templates/index.html` for HTML structure
   - `static/style.css` for styling
   - `static/app.js` for JavaScript functionality

### Environment Variables

- `PORT` - Port number for the application (default: 5000)

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
