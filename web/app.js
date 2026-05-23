const scanButton = document.querySelector('#scan-button');
const fileInput = document.querySelector('#qr-file');
const manualInput = document.querySelector('#manual-text');
const manualButton = document.querySelector('#manual-button');
const readerElement = document.querySelector('#qr-reader');
const statusElement = document.querySelector('#status');
const totalVillasElement = document.querySelector('#total-villas');
const representedVillasElement = document.querySelector('#represented-villas');
const representationPctElement = document.querySelector('#representation-pct');
const representationBarElement = document.querySelector('#representation-bar');
const attendeeCountElement = document.querySelector('#attendee-count');
const attendeeListElement = document.querySelector('#attendee-list');
const dashboardUpdatedElement = document.querySelector('#dashboard-updated');
const refreshDashboardButton = document.querySelector('#refresh-dashboard');

let html5QrCode = null;
let scanning = false;
let submitting = false;

window.AttendanceCallbacks = window.AttendanceCallbacks || {};

function getApiUrl() {
  const config = window.AttendanceConfig || {};
  return String(config.apiUrl || '').trim();
}

function isConfigured() {
  const apiUrl = getApiUrl();
  return apiUrl && !apiUrl.includes('PASTE_APPS_SCRIPT_WEB_APP_URL_HERE');
}

function setStatus(type, title, copy, resident) {
  statusElement.className = `status ${type || ''}`.trim();
  const residentHtml = resident ? `
    <div class="resident">
      ${fieldHtml('Name', resident.Name)}
      ${fieldHtml('Flat', resident.Flat)}
      ${fieldHtml('User Type', resident['User Type'])}
      ${fieldHtml('Status', resident.Status)}
    </div>
  ` : '';

  statusElement.innerHTML = `
    <p class="status-title">${escapeHtml(title)}</p>
    <p class="status-copy">${escapeHtml(copy || '')}</p>
    ${residentHtml}
  `;
}

function setDashboardLoading(message = 'Loading attendance dashboard...') {
  dashboardUpdatedElement.textContent = message;
}

function renderDashboard(data) {
  const totalVillas = Number(data && data.totalVillas ? data.totalVillas : 0);
  const representedVillas = Number(data && data.representedVillas ? data.representedVillas : 0);
  const representationPct = Number(data && data.representationPct ? data.representationPct : 0);
  const attendees = Array.isArray(data && data.attendees) ? data.attendees : [];

  totalVillasElement.textContent = formatInt(totalVillas);
  representedVillasElement.textContent = formatInt(representedVillas);
  representationPctElement.textContent = `${formatPct(representationPct)}%`;
  representationBarElement.style.width = `${Math.max(0, Math.min(100, representationPct))}%`;
  attendeeCountElement.textContent = formatInt(attendees.length);
  attendeeListElement.innerHTML = attendees.length
    ? attendees.map(attendeeRowHtml).join('')
    : '<p class="empty-list">No attendance marked yet.</p>';
  dashboardUpdatedElement.textContent = `Updated ${new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`;
}

function attendeeRowHtml(attendee) {
  return `
    <div class="attendee-row" role="listitem">
      <span>
        <strong>${escapeHtml(attendee.name || '-')}</strong>
        <small>${escapeHtml(attendee.userType || '')}</small>
      </span>
      <span class="villa-tag">${escapeHtml(attendee.flat || '-')}</span>
    </div>
  `;
}

function formatInt(value) {
  return Math.round(Number(value || 0)).toLocaleString('en-IN');
}

function formatPct(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function fieldHtml(label, value) {
  return `
    <div class="field">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || '-')}</strong>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function toggleScanner() {
  if (scanning) {
    await stopScanner();
    return;
  }

  if (!isConfigured()) {
    setStatus('error', 'Backend not configured', 'Paste the Apps Script web app URL into web/config.js first.');
    return;
  }

  if (!window.Html5Qrcode) {
    setStatus('error', 'Scanner unavailable', 'The QR scanner library did not load. Please refresh and try again.');
    return;
  }

  try {
    setStatus('', 'Opening camera', 'Allow camera access when your browser asks.');
    readerElement.classList.add('active');
    html5QrCode = new Html5Qrcode('qr-reader');
    await html5QrCode.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: getQrBox },
      onScanSuccess,
      () => {}
    );
    scanning = true;
    scanButton.querySelector('span').textContent = 'Stop Scan';
    setStatus('', 'Scanning', 'Point your camera at the MyGate QR code.');
  } catch (error) {
    readerElement.classList.remove('active');
    setStatus('error', 'Camera blocked', error && error.message ? error.message : 'Could not open the camera.');
  }
}

function getQrBox(viewfinderWidth, viewfinderHeight) {
  const edge = Math.floor(Math.min(viewfinderWidth, viewfinderHeight) * 0.76);
  return {
    width: Math.max(180, edge),
    height: Math.max(180, edge),
  };
}

async function stopScanner() {
  if (!html5QrCode || !scanning) return;
  await html5QrCode.stop();
  await html5QrCode.clear();
  html5QrCode = null;
  scanning = false;
  readerElement.classList.remove('active');
  scanButton.querySelector('span').textContent = 'Scan QR';
}

async function onScanSuccess(decodedText) {
  await stopScanner();
  submitQr(decodedText, 'camera');
}

async function scanFile(file) {
  if (!file) return;
  if (!isConfigured()) {
    setStatus('error', 'Backend not configured', 'Paste the Apps Script web app URL into web/config.js first.');
    return;
  }

  if (!window.Html5Qrcode) {
    setStatus('error', 'Upload unavailable', 'The QR scanner library did not load. Please refresh and try again.');
    return;
  }

  try {
    setStatus('', 'Reading screenshot', 'Looking for a QR code in the uploaded image.');
    readerElement.classList.add('active');
    const scanner = new Html5Qrcode('qr-reader');
    const decodedText = await scanner.scanFile(file, true);
    await scanner.clear();
    readerElement.classList.remove('active');
    submitQr(decodedText, 'upload');
  } catch (error) {
    readerElement.classList.remove('active');
    setStatus('error', 'QR not found', 'Please upload a clear screenshot with the full MyGate QR visible.');
  } finally {
    fileInput.value = '';
  }
}

function submitManual() {
  const value = manualInput.value.trim();
  if (!value) {
    setStatus('warning', 'Nothing to submit', 'Paste the QR text or passcode first.');
    return;
  }
  submitQr(value, 'manual');
}

function submitQr(qrRawData, source) {
  if (submitting) return;
  if (!isConfigured()) {
    setStatus('error', 'Backend not configured', 'Paste the Apps Script web app URL into web/config.js first.');
    return;
  }

  submitting = true;
  setStatus('', 'Marking attendance', 'Checking the resident master sheet.');

  jsonpRequest({
    action: 'markAttendance',
    qrRawData,
    source,
  })
    .then((response) => {
      submitting = false;
      if (!response || !response.ok) {
        setStatus('error', 'Could not mark attendance', response && response.message ? response.message : 'Please try again.');
        return;
      }

      const title = response.duplicate ? 'Already marked' : 'Attendance marked';
      const type = response.duplicate ? 'warning' : 'success';
      setStatus(type, title, response.message, response.resident);
      manualInput.value = '';
      loadDashboard();
    })
    .catch((error) => {
      submitting = false;
      setStatus('error', 'Something went wrong', error && error.message ? error.message : 'Please try again.');
    });
}

function loadDashboard() {
  if (!isConfigured()) return;
  setDashboardLoading('Refreshing attendance dashboard...');
  jsonpRequest({ action: 'dashboard' })
    .then((response) => {
      if (!response || !response.ok) {
        setDashboardLoading(response && response.message ? response.message : 'Could not refresh dashboard.');
        return;
      }
      if (!Object.prototype.hasOwnProperty.call(response, 'totalVillas')) {
        setDashboardLoading('Deploy the updated Apps Script backend to load dashboard data.');
        return;
      }
      renderDashboard(response);
    })
    .catch((error) => {
      setDashboardLoading(error && error.message ? error.message : 'Could not refresh dashboard.');
    });
}

function jsonpRequest(params) {
  return new Promise((resolve, reject) => {
    const callbackName = `cb_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const script = document.createElement('script');
    const url = new URL(getApiUrl());

    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, value == null ? '' : String(value));
    });
    url.searchParams.set('callback', `AttendanceCallbacks.${callbackName}`);

    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error('The attendance server did not respond in time.'));
    }, 60000);

    window.AttendanceCallbacks[callbackName] = (payload) => {
      cleanup();
      resolve(payload);
    };

    script.onerror = () => {
      cleanup();
      reject(new Error('Could not reach the attendance server.'));
    };

    function cleanup() {
      window.clearTimeout(timeout);
      delete window.AttendanceCallbacks[callbackName];
      script.remove();
    }

    script.src = url.toString();
    document.body.appendChild(script);
  });
}

scanButton.addEventListener('click', toggleScanner);
fileInput.addEventListener('change', (event) => scanFile(event.target.files[0]));
manualButton.addEventListener('click', submitManual);
refreshDashboardButton.addEventListener('click', loadDashboard);
manualInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    submitManual();
  }
});

if (!isConfigured()) {
  setStatus('warning', 'Setup needed', 'Paste the Apps Script web app URL into web/config.js before sharing this page.');
  setDashboardLoading('Backend not configured.');
} else {
  loadDashboard();
}
