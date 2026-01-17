// API base URL
const API_BASE = '/api';

// State
let currentUser = null;
let currentSection = 'search';
let refreshInterval = null;

// DOM elements
const authScreen = document.getElementById('authScreen');
const mainApp = document.getElementById('mainApp');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Auth tabs
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => switchAuthTab(tab.dataset.tab));
    });

    // Auth forms
    loginForm.addEventListener('submit', handleLogin);
    registerForm.addEventListener('submit', handleRegister);

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', handleLogout);

    // Navigation tabs
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchSection(tab.dataset.section));
    });

    // Search
    document.getElementById('searchBtn')?.addEventListener('click', handleSearch);
    document.getElementById('quickRequestForm')?.addEventListener('submit', handleQuickRequest);

    // Requests
    document.getElementById('refreshRequestsBtn')?.addEventListener('click', loadRequests);

    // Admin
    document.getElementById('settingsForm')?.addEventListener('submit', handleSaveSettings);
    document.getElementById('testJellyfinBtn')?.addEventListener('click', handleTestJellyfin);
    document.getElementById('syncJellyfinBtn')?.addEventListener('click', handleSyncJellyfin);
}

// Auth functions
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`);
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            showMainApp();
            startPolling();
        } else {
            showAuthScreen();
        }
    } catch (error) {
        showAuthScreen();
    }
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

    if (tab === 'login') {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
    } else {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const formData = {
        username: document.getElementById('loginUsername').value,
        password: document.getElementById('loginPassword').value,
        provider: document.getElementById('loginProvider').value
    };

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            showMainApp();
        } else {
            const error = await response.json();
            showError('loginError', error.error || 'Login failed');
        }
    } catch (error) {
        showError('loginError', 'Network error. Please try again.');
    }
}

async function handleRegister(e) {
    e.preventDefault();

    const password = document.getElementById('registerPassword').value;
    const confirm = document.getElementById('registerPasswordConfirm').value;

    if (password !== confirm) {
        showError('registerError', 'Passwords do not match');
        return;
    }

    const formData = {
        username: document.getElementById('registerUsername').value,
        email: document.getElementById('registerEmail').value,
        password: password
    };

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            showMainApp();
        } else {
            const error = await response.json();
            showError('registerError', error.error || 'Registration failed');
        }
    } catch (error) {
        showError('registerError', 'Network error. Please try again.');
    }
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST' });
        currentUser = null;
        stopPolling();
        showAuthScreen();
    } catch (error) {
        console.error('Logout error:', error);
    }
}

function showAuthScreen() {
    authScreen.style.display = 'flex';
    mainApp.style.display = 'none';
}

function showMainApp() {
    authScreen.style.display = 'none';
    mainApp.style.display = 'flex';

    document.getElementById('userName').textContent = currentUser.username;

    // Show admin sections if user is admin
    if (currentUser.role === 'admin') {
        document.querySelectorAll('.admin-only').forEach(el => el.style.display = '');
    }

    // Load initial data
    loadRequests();
}

// Navigation
function switchSection(section) {
    currentSection = section;

    document.querySelectorAll('.nav-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelector(`[data-section="${section}"]`).classList.add('active');

    document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
    document.getElementById(`${section}Section`).classList.add('active');

    // Load section-specific data
    if (section === 'admin') {
        loadSettings();
        loadAllRequests();
    }
}

// Search functions
async function handleSearch() {
    const query = document.getElementById('searchQuery').value;
    const type = document.getElementById('searchType').value;

    if (!query) return;

    const resultsDiv = document.getElementById('searchResults');
    resultsDiv.innerHTML = '<p>Searching...</p>';

    try {
        const response = await fetch(`${API_BASE}/search/musicbrainz?query=${encodeURIComponent(query)}&type=${type}`);
        const data = await response.json();

        if (response.ok) {
            displaySearchResults(data.results, type);
        } else {
            resultsDiv.innerHTML = `<p class="error-message">${data.error}</p>`;
        }
    } catch (error) {
        resultsDiv.innerHTML = '<p class="error-message">Search failed</p>';
    }
}

function displaySearchResults(results, type) {
    const resultsDiv = document.getElementById('searchResults');

    if (!results || results.length === 0) {
        resultsDiv.innerHTML = '<p class="no-requests">No results found</p>';
        return;
    }

    resultsDiv.innerHTML = results.map(result => `
        <div class="search-result-item">
            <div class="search-result-info">
                <h4>${escapeHtml(result.title || result.name)}</h4>
                <p>${escapeHtml(result.artist || result.type || '')}</p>
            </div>
            <button class="btn-primary" onclick="requestFromSearch('${type}', '${escapeHtml(result.title || result.name)}', '${escapeHtml(result.artist || '')}', '${result.id}')">
                Request
            </button>
        </div>
    `).join('');
}

async function requestFromSearch(type, title, artist, mbId) {
    const formData = {
        content_type: type,
        title: title,
        artist: artist,
        musicbrainz_id: mbId
    };

    try {
        const response = await fetch(`${API_BASE}/requests`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            if (data.available) {
                showMessage('Content already available in Jellyfin!', 'success');
            } else {
                showMessage('Request submitted successfully!', 'success');
                loadRequests();
            }
        } else {
            showMessage(data.error || 'Request failed', 'error');
        }
    } catch (error) {
        showMessage('Network error', 'error');
    }
}

async function handleQuickRequest(e) {
    e.preventDefault();

    const formData = {
        content_type: document.getElementById('requestType').value,
        title: document.getElementById('requestTitle').value,
        artist: document.getElementById('requestArtist').value,
        album: document.getElementById('requestAlbum').value
    };

    try {
        const response = await fetch(`${API_BASE}/requests`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (response.ok) {
            if (data.available) {
                showMessage('Content already available in Jellyfin!', 'success');
            } else {
                showMessage('Request submitted successfully!', 'success');
                document.getElementById('quickRequestForm').reset();
                loadRequests();
            }
        } else {
            showMessage(data.error || 'Request failed', 'error');
        }
    } catch (error) {
        showMessage('Network error', 'error');
    }
}

// Requests functions
async function loadRequests() {
    try {
        const response = await fetch(`${API_BASE}/requests`);
        const data = await response.json();

        if (response.ok) {
            displayRequests(data.requests, 'requestsList');
        }
    } catch (error) {
        console.error('Failed to load requests:', error);
    }
}

async function loadAllRequests() {
    // In admin view, this would load all requests
    loadRequests();
    displayRequests([], 'adminRequestsList');
}

function displayRequests(requests, containerId) {
    const container = document.getElementById(containerId);

    if (!requests || requests.length === 0) {
        container.innerHTML = '<p class="no-requests">No requests yet</p>';
        return;
    }

    container.innerHTML = requests.map(req => `
        <div class="request-item">
            <div class="request-header">
                <span class="request-title">${escapeHtml(req.title)}</span>
                <span class="request-status status-${req.status}">${req.status}</span>
            </div>
            ${req.artist ? `<div class="request-details">Artist: ${escapeHtml(req.artist)}</div>` : ''}
            ${req.album ? `<div class="request-details">Album: ${escapeHtml(req.album)}</div>` : ''}
            <div class="request-details">Type: ${req.content_type}</div>
            ${req.streaming_service ? `<div class="request-details">Service: ${req.streaming_service}</div>` : ''}
            <div class="request-date">Requested: ${new Date(req.created_at).toLocaleString()}</div>
            ${currentUser?.role === 'admin' && req.status === 'pending' ? `
                <button class="btn-secondary" onclick="processRequest(${req.id})">Process</button>
            ` : ''}
        </div>
    `).join('');
}

async function processRequest(requestId) {
    console.log(`Processing request ${requestId}...`);
    // Removed confirm for debugging

    try {
        console.log('Sending POS request...');
        const response = await fetch(`${API_BASE}/requests/${requestId}/process`, {
            method: 'POST'
        });
        console.log('Response received:', response.status);

        if (response.ok) {
            showMessage('Request processing started', 'success');
            loadRequests();
        } else {
            const data = await response.json().catch(() => ({}));
            const errorMsg = data.error || `Server returned ${response.status}: ${response.statusText}`;
            showMessage(errorMsg, 'error');
            console.error('Process error:', errorMsg);
        }
    } catch (error) {
        showMessage('Network error: ' + error.message, 'error');
        console.error('Network error:', error);
    }
}

// Admin functions
async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE}/admin/settings`);
        const data = await response.json();

        if (response.ok) {
            const settings = data.settings;
            document.getElementById('jellyfinUrl').value = settings.jellyfin_url || '';
            document.getElementById('primaryService').value = settings.primary_service || 'qobuz';
            document.getElementById('fallbackService').value = settings.fallback_service || 'deezer';
            document.getElementById('downloadQuality').value = settings.download_quality || '3';
            document.getElementById('outputPath').value = settings.output_path || '/media/Music';
            document.getElementById('pathPattern').value = settings.path_pattern || '{artist}/{artist} - {title}';
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();

    const settings = {
        jellyfin_url: document.getElementById('jellyfinUrl').value,
        primary_service: document.getElementById('primaryService').value,
        fallback_service: document.getElementById('fallbackService').value,
        download_quality: document.getElementById('downloadQuality').value,
        output_path: document.getElementById('outputPath').value,
        path_pattern: document.getElementById('pathPattern').value
    };

    try {
        const response = await fetch(`${API_BASE}/admin/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            showMessage('Settings saved successfully', 'success');
        } else {
            showMessage('Failed to save settings', 'error');
        }
    } catch (error) {
        showMessage('Network error', 'error');
    }
}

async function handleTestJellyfin() {
    try {
        const response = await fetch(`${API_BASE}/admin/jellyfin/test`, {
            method: 'POST'
        });
        const data = await response.json();

        if (data.success) {
            showMessage(`Jellyfin connected: ${data.info.server_name} v${data.info.version}`, 'success');
        } else {
            showMessage(`Jellyfin connection failed: ${data.error}`, 'error');
        }
    } catch (error) {
        showMessage('Network error', 'error');
    }
}

async function handleSyncJellyfin() {
    if (!confirm('Sync Jellyfin library? This may take a while.')) return;

    try {
        const response = await fetch(`${API_BASE}/admin/jellyfin/sync`, {
            method: 'POST'
        });
        const data = await response.json();

        if (response.ok) {
            showMessage(data.message, 'success');
        } else {
            showMessage(data.error || 'Sync failed', 'error');
        }
    } catch (error) {
        showMessage('Network error', 'error');
    }
}

// Utility functions
function showError(elementId, message) {
    const errorDiv = document.getElementById(elementId);
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => errorDiv.style.display = 'none', 5000);
}

function showMessage(message, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    messageDiv.textContent = message;
    messageDiv.style.position = 'fixed';
    messageDiv.style.top = '20px';
    messageDiv.style.right = '20px';
    messageDiv.style.zIndex = '9999';
    messageDiv.style.maxWidth = '400px';

    document.body.appendChild(messageDiv);

    setTimeout(() => messageDiv.remove(), 5000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function startPolling() {
    if (refreshInterval) return;
    refreshInterval = setInterval(() => {
        if (currentUser) {
            loadRequests();
        }
    }, 5000);
}

function stopPolling() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Make functions globally available
window.requestFromSearch = requestFromSearch;
window.processRequest = processRequest;
