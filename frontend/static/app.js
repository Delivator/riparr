// API base URL
const API_BASE = '/api';

// State
let currentUser = null;
let currentSection = 'search';
let socket = null;

// DOM elements
const authScreen = document.getElementById('authScreen');
const mainApp = document.getElementById('mainApp');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadPreferences();
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

    // Search Service Persistence
    document.querySelectorAll('input[name="searchService"]').forEach(cb => {
        cb.addEventListener('change', savePreferences);
    });
    document.getElementById('searchType')?.addEventListener('change', savePreferences);

    // Requests
    document.getElementById('refreshRequestsBtn')?.addEventListener('click', loadRequests);

    // Admin
    document.getElementById('settingsForm')?.addEventListener('submit', handleSaveSettings);
    document.getElementById('testJellyfinBtn')?.addEventListener('click', handleTestJellyfin);
    document.getElementById('syncJellyfinBtn')?.addEventListener('click', handleSyncJellyfin);

    // Delegated listener for search results
    document.getElementById('searchResults')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.request-btn');
        if (btn) {
            requestFromSearch(
                btn.dataset.type,
                btn.dataset.title,
                btn.dataset.artist,
                btn.dataset.id,
                btn.dataset.service,
                btn.dataset.album
            );
        }
    });
}

// Auth functions
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`);
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            showMainApp();
            initSocket();
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
        if (socket) {
            socket.disconnect();
            socket = null;
        }
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

    // Get selected services
    const serviceCheckboxes = document.querySelectorAll('input[name="searchService"]:checked');
    const selectedServices = Array.from(serviceCheckboxes).map(cb => cb.value);

    if (!query) return;
    if (selectedServices.length === 0) {
        showMessage('Please select at least one service to search', 'error');
        return;
    }

    const resultsDiv = document.getElementById('searchResults');
    resultsDiv.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>Searching ${selectedServices.join(' & ')}...</p>
        </div>
    `;

    try {
        const servicesParam = selectedServices.join(',');
        const response = await fetch(`${API_BASE}/search/streaming?query=${encodeURIComponent(query)}&type=${type}&services=${servicesParam}`);
        const data = await response.json();

        if (response.ok) {
            displaySearchResults(data.results, type, selectedServices);
        } else {
            resultsDiv.innerHTML = `<p class="error-message">${data.error}</p>`;
        }
    } catch (error) {
        resultsDiv.innerHTML = '<p class="error-message">Search failed. Check your streaming service connection.</p>';
        console.error('Search error:', error);
    }
}

function displaySearchResults(results, type, searchServices) {
    const resultsDiv = document.getElementById('searchResults');
    const showSourceBadge = searchServices && searchServices.length > 1;

    if (!results || results.length === 0) {
        resultsDiv.innerHTML = `<p class="no-requests">No results found on ${searchServices.join(', ')}</p>`;
        return;
    }

    resultsDiv.innerHTML = `
        <div class="search-results-grid">
            ${results.map(result => {
        const title = result.title || result.name;
        const artist = result.artist || 'Unknown Artist';
        const album = result.album || '';
        const id = result.id;
        const service = result.service;
        const coverUrl = result.cover_url || '/static/img/default-cover.png';
        const quality = result.quality || '';
        const year = result.year || result.release_date?.substring(0, 4) || '';
        const duration = result.duration ? formatDuration(result.duration) : '';

        return `
                <div class="search-card">
                    <div class="search-card-cover">
                        <img src="${coverUrl}" alt="${escapeHtml(title)}" onerror="this.src='/static/img/default-cover.png'">
                        ${quality ? `<span class="badge badge-quality">${escapeHtml(quality)}</span>` : ''}
                    </div>
                    <div class="search-card-content">
                        <div class="search-card-header">
                            <h4 class="text-truncate" title="${escapeHtml(title)}">
                                ${showSourceBadge ? `<span class="badge-source ${service}">${service}</span>` : ''}
                                ${escapeHtml(title)}
                            </h4>
                            <p class="search-card-artist text-truncate">${escapeHtml(artist)}</p>
                        </div>
                        <div class="search-card-details">
                            ${album ? `<p class="text-truncate"><span>Album:</span> ${escapeHtml(album)}</p>` : ''}
                            <div class="search-card-meta">
                                ${year ? `<span><i class="fas fa-calendar"></i> ${year}</span>` : ''}
                                ${duration ? `<span><i class="fas fa-clock"></i> ${duration}</span>` : ''}
                                ${result.track_count ? `<span><i class="fas fa-list"></i> ${result.track_count} tracks</span>` : ''}
                            </div>
                        </div>
                        <div class="search-card-actions">
                            <button class="btn-primary btn-block request-btn" 
                                data-type="${type}"
                                data-title="${escapeHtml(title)}"
                                data-artist="${escapeHtml(artist)}"
                                data-id="${id}"
                                data-service="${service}"
                                data-album="${escapeHtml(album)}">
                                Request ${type}
                            </button>
                            ${type === 'song' && result.album_id ? `
                            <button class="btn-secondary btn-block request-btn" style="margin-top: 0.5rem;" 
                                data-type="album"
                                data-title="${escapeHtml(album)}"
                                data-artist="${escapeHtml(artist)}"
                                data-id="${result.album_id}"
                                data-service="${service}"
                                data-album="${escapeHtml(album)}">
                                Request Album
                            </button>
                            ` : ''}
                        </div>
                    </div>
                </div>
                `;
    }).join('')}
        </div>
    `;
}

function formatDuration(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

async function requestFromSearch(type, title, artist, serviceId, serviceName, album) {
    const formData = {
        content_type: type,
        title: title,
        artist: artist,
        album: album,
        streaming_service: serviceName,
        streaming_url: serviceId // We store the ID in streaming_url for now
    };

    // Show loading state on button
    const btn = event.target;
    const originalText = btn.innerText;
    btn.disabled = true;
    btn.innerText = 'Requesting...';

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
                btn.innerText = 'Available';
            } else {
                showMessage('Request submitted successfully!', 'success');
                btn.innerText = 'Requested';
                loadRequests();
            }
        } else {
            showMessage(data.error || 'Request failed', 'error');
            btn.innerText = originalText;
            btn.disabled = false;
        }
    } catch (error) {
        showMessage('Network error', 'error');
        btn.innerText = originalText;
        btn.disabled = false;
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
    try {
        const response = await fetch(`${API_BASE}/requests`);
        const data = await response.json();

        if (response.ok) {
            displayRequests(data.requests, 'adminRequestsList');
        }
    } catch (error) {
        console.error('Failed to load all requests:', error);
    }
}

function displayRequests(requests, containerId) {
    const container = document.getElementById(containerId);

    if (!requests || requests.length === 0) {
        container.innerHTML = '<p class="no-requests">No requests yet</p>';
        return;
    }

    container.innerHTML = requests.map(req => `
        <div class="request-item">
            <div class="request-main">
                <div class="request-header">
                    <span class="request-title">${escapeHtml(req.title)}</span>
                    <span class="request-status status-${req.status}">${req.status}</span>
                </div>
                <div class="request-details">
                    ${req.artist ? `<span><i class="fas fa-user"></i> ${escapeHtml(req.artist)}</span>` : ''}
                    ${req.album ? `<span><i class="fas fa-compact-disc"></i> ${escapeHtml(req.album)}</span>` : ''}
                    <span><i class="fas fa-tag"></i> ${req.content_type}</span>
                </div>
                <div class="request-date">${new Date(req.created_at).toLocaleString()}</div>
            </div>
            <div class="request-actions">
                 ${currentUser?.role === 'admin' && req.status === 'pending' ? `
                    <button class="btn-secondary" onclick="processRequest(${req.id})">Process</button>
                ` : ''}
            </div>
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
    if (!text) return '';
    return text
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Socket.io Functions
function initSocket() {
    if (socket) return;

    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity
    });

    socket.on('connect', () => {
        console.log('Socket.io connected');
    });

    socket.on('disconnect', () => {
        console.log('Socket.io disconnected');
    });

    socket.on('request_update', (data) => {
        console.log('Request status updated via socket:', data);
        // Refresh the appropriate list depending on current view
        if (currentSection === 'requests') {
            loadRequests();
        } else if (currentSection === 'admin') {
            loadAllRequests();
        }
    });

    socket.on('error', (error) => {
        console.error('Socket.io error:', error);
    });
}

// Persistence
function savePreferences() {
    const type = document.getElementById('searchType').value;
    const services = Array.from(document.querySelectorAll('input[name="searchService"]:checked'))
        .map(cb => cb.value);

    const preferences = {
        searchType: type,
        searchServices: services
    };

    localStorage.setItem('riparr_preferences', JSON.stringify(preferences));
}

function loadPreferences() {
    const stored = localStorage.getItem('riparr_preferences');
    if (!stored) return;

    try {
        const prefs = JSON.parse(stored);

        if (prefs.searchType) {
            const typeSelect = document.getElementById('searchType');
            if (typeSelect) typeSelect.value = prefs.searchType;
        }

        if (prefs.searchServices) {
            document.querySelectorAll('input[name="searchService"]').forEach(cb => {
                cb.checked = prefs.searchServices.includes(cb.value);
            });
        }
    } catch (e) {
        console.error('Failed to load preferences', e);
    }
}

// Make functions globally available
window.requestFromSearch = requestFromSearch;
window.processRequest = processRequest;
