// API base URL
const API_BASE = '/api';

// DOM elements
const requestForm = document.getElementById('requestForm');
const requestsContainer = document.getElementById('requestsContainer');

// Load requests on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRequests();
});

// Handle form submission
requestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        song: document.getElementById('song').value,
        artist: document.getElementById('artist').value,
        requester: document.getElementById('requester').value || 'Anonymous'
    };
    
    try {
        const response = await fetch(`${API_BASE}/requests`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        if (response.ok) {
            showMessage('Request submitted successfully!', 'success');
            requestForm.reset();
            loadRequests();
        } else {
            const error = await response.json();
            showMessage(error.error || 'Failed to submit request', 'error');
        }
    } catch (error) {
        showMessage('Network error. Please try again.', 'error');
        console.error('Error:', error);
    }
});

// Load all requests
async function loadRequests() {
    try {
        const response = await fetch(`${API_BASE}/requests`);
        const data = await response.json();
        
        displayRequests(data.requests);
    } catch (error) {
        console.error('Error loading requests:', error);
        requestsContainer.innerHTML = '<p class="no-requests">Failed to load requests</p>';
    }
}

// Display requests in the UI
function displayRequests(requests) {
    if (requests.length === 0) {
        requestsContainer.innerHTML = '<p class="no-requests">No requests yet. Be the first to request a song!</p>';
        return;
    }
    
    requestsContainer.innerHTML = requests
        .reverse()
        .map(request => `
            <div class="request-item">
                <div class="request-song">${escapeHtml(request.song)}</div>
                ${request.artist ? `<div class="request-artist">by ${escapeHtml(request.artist)}</div>` : ''}
                <div class="request-requester">Requested by ${escapeHtml(request.requester)}</div>
            </div>
        `)
        .join('');
}

// Show temporary message
function showMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.textContent = message;
    
    const form = document.querySelector('.request-form');
    form.insertBefore(messageDiv, requestForm);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 3000);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
