from flask import Flask, jsonify, render_template, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__,
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Sample data for music requests
music_requests = []

@app.route('/')
def index():
    """Serve the main frontend page"""
    return render_template('index.html')

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'riparr'})

@app.route('/api/requests', methods=['GET'])
def get_requests():
    """Get all music requests"""
    return jsonify({'requests': music_requests})

@app.route('/api/requests', methods=['POST'])
def create_request():
    """Create a new music request"""
    from flask import request
    data = request.get_json()
    
    if not data or 'song' not in data:
        return jsonify({'error': 'Song name is required'}), 400
    
    new_request = {
        'id': len(music_requests) + 1,
        'song': data['song'],
        'artist': data.get('artist', ''),
        'requester': data.get('requester', 'Anonymous')
    }
    
    music_requests.append(new_request)
    return jsonify({'request': new_request}), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
