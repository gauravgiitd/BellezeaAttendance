const scanButton = document.querySelector('#scan-button');
const fileInput = document.querySelector('#qr-file');
const manualInput = document.querySelector('#manual-text');
const manualButton = document.querySelector('#manual-button');
const manualAttendanceForm = document.querySelector('#manual-attendance-form');
const manualUserIdInput = document.querySelector('#manual-user-id');
const manualHouseIdInput = document.querySelector('#manual-house-id');
const manualNameInput = document.querySelector('#manual-name');
const readerElement = document.querySelector('#qr-reader');
const statusElement = document.querySelector('#status');
const totalVillasElement = document.querySelector('#total-villas');
const representedVillasElement = document.querySelector('#represented-villas');
const representationPctElement = document.querySelector('#representation-pct');
const quorumRequiredElement = document.querySelector('#quorum-required');
const quorumStatusElement = document.querySelector('#quorum-status');
const representationBarElement = document.querySelector('#representation-bar');
const attendeeCountElement = document.querySelector('#attendee-count');
const attendeeListElement = document.querySelector('#attendee-list');
const attendeeSearchInput = document.querySelector('#attendee-search');
const dashboardUpdatedElement = document.querySelector('#dashboard-updated');
const refreshDashboardButton = document.querySelector('#refresh-dashboard');
const refreshElectionsButton = document.querySelector('#refresh-elections');
const electionSelect = document.querySelector('#election-select');
const electionForm = document.querySelector('#election-form');
const electionTitleInput = document.querySelector('#election-title');
const electionDescriptionInput = document.querySelector('#election-description');
const electionQuorumInput = document.querySelector('#election-quorum');
const electionStatusSelect = document.querySelector('#election-status');
const includeDefaultersQuorumInput = document.querySelector('#include-defaulters-quorum');
const allowDefaultersVoteInput = document.querySelector('#allow-defaulters-vote');
const questionForm = document.querySelector('#question-form');
const questionTextInput = document.querySelector('#question-text');
const choiceOneInput = document.querySelector('#choice-one');
const choiceTwoInput = document.querySelector('#choice-two');
const passingRuleSelect = document.querySelector('#passing-rule');
const passingThresholdInput = document.querySelector('#passing-threshold');
const questionListElement = document.querySelector('#question-list');
const activeElectionStatusElement = document.querySelector('#active-election-status');
const headerQuorumElement = document.querySelector('#header-quorum');
const activeElectionView = document.querySelector('#active-election-view');
const selectedElectionTitleElement = document.querySelector('#selected-election-title');
const stageListElement = document.querySelector('#stage-list');
const stageActionButton = document.querySelector('#stage-action-button');
const modeTabs = Array.from(document.querySelectorAll('.mode-tab'));
const appViews = Array.from(document.querySelectorAll('.app-view'));
const manageStatusElement = document.querySelector('#manage-status');
const newElectionButton = document.querySelector('#new-election-button');
const deleteElectionButton = document.querySelector('#delete-election-button');
const saveElectionButton = document.querySelector('#save-election-button');
const proxyForm = document.querySelector('#proxy-form');
const proxyGrantorHouseIdInput = document.querySelector('#proxy-grantor-house-id');
const proxyHolderUserIdInput = document.querySelector('#proxy-holder-user-id');
const proxyNotesInput = document.querySelector('#proxy-notes');
const proxyListElement = document.querySelector('#proxy-list');

const DEFAULT_API_URL = 'https://bellezea-elections-api.onrender.com';
const ACTIVE_ELECTION_KEY = 'bellezea-active-election-id';
const ACTIVE_MODE_KEY = 'bellezea-officer-mode';
const ELECTION_FLOW = [
  { status: 'draft', label: 'Setup' },
  { status: 'attendance_open', label: 'Attendance' },
  { status: 'discussion', label: 'Discussion' },
  { status: 'voting_open', label: 'Voting' },
  { status: 'voting_closed', label: 'Closed' },
  { status: 'results_published', label: 'Results' },
];
const STAGE_ACTIONS = {
  draft: { label: 'Start Attendance', nextStatus: 'attendance_open' },
  attendance_open: { label: 'Start Discussion', nextStatus: 'discussion' },
  discussion: { label: 'Open Voting', nextStatus: 'voting_open', requiresQuorum: true },
  voting_open: { label: 'Close Voting', nextStatus: 'voting_closed' },
  voting_closed: { label: 'Publish Results', nextStatus: 'results_published' },
};
const ATTENDANCE_STATUSES = new Set(['attendance_open', 'discussion', 'voting_open', 'voting_closed', 'results_published']);

let html5QrCode = null;
let scanning = false;
let submitting = false;
let elections = [];
let activeElection = null;
let activeElectionDetail = null;
let dashboardAttendees = [];
let proxies = [];
let editingNewElection = false;

function getApiUrl() {
  const config = window.AttendanceConfig || {};
  return String(config.apiUrl || DEFAULT_API_URL).trim().replace(/\/+$/, '');
}

function switchMode(mode) {
  const target = mode || 'manage';
  modeTabs.forEach((tab) => {
    const active = tab.dataset.mode === target;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  appViews.forEach((view) => {
    view.classList.toggle('active', view.id === `${target}-view`);
  });
  window.localStorage.setItem(ACTIVE_MODE_KEY, target);
}

function setStatus(type, title, copy, resident) {
  statusElement.className = `status ${type || ''}`.trim();
  const residentHtml = resident ? `
    <div class="resident">
      ${fieldHtml('Name', resident.name)}
      ${fieldHtml('Villa', resident.house_no || resident.flat)}
      ${fieldHtml('User Type', resident.user_type || resident.userType)}
      ${fieldHtml('Status', resident.status)}
    </div>
  ` : '';

  statusElement.innerHTML = `
    <p class="status-title">${escapeHtml(title)}</p>
    <p class="status-copy">${escapeHtml(copy || '')}</p>
    ${residentHtml}
  `;
}

function setManageStatus(type, message) {
  manageStatusElement.className = `inline-status ${type || ''}`.trim();
  manageStatusElement.textContent = message || '';
}

function setDashboardLoading(message = 'Loading elections...') {
  dashboardUpdatedElement.textContent = message;
}

function activeElectionId() {
  return activeElection ? activeElection.id : '';
}

function requireActiveElection() {
  if (activeElectionId()) return true;
  setStatus('warning', 'No election selected', 'Create or select an election before marking attendance.');
  return false;
}

function canTakeAttendance() {
  return activeElection && ATTENDANCE_STATUSES.has(activeElection.status);
}

function requireAttendanceOpen() {
  if (!requireActiveElection()) return false;
  if (canTakeAttendance()) return true;
  setStatus('warning', 'Attendance not open', 'Start attendance before scanning or adding people.');
  return false;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${getApiUrl()}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  });
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = body && body.detail ? body.detail : body || `Request failed with ${response.status}`;
    throw new Error(message);
  }
  return body;
}

async function loadElections() {
  setDashboardLoading('Loading elections...');
  try {
    elections = await apiRequest('/api/elections');
    renderElectionSelect();
    await selectInitialElection();
    setDashboardLoading(`Updated ${formatTime(new Date())}`);
  } catch (error) {
    elections = [];
    activeElection = null;
    activeElectionDetail = null;
    renderElectionSelect();
    renderQuestions();
    renderEmptyDashboard();
    setDashboardLoading(error.message || 'Could not load elections.');
    setStatus('error', 'Could not load elections', error.message || 'Please check the backend deployment.');
  }
}

function renderElectionSelect() {
  if (!elections.length) {
    electionSelect.innerHTML = '<option value="">No elections yet</option>';
    activeElectionView.hidden = true;
    setElectionFormMode('new');
    return;
  }
  electionSelect.innerHTML = elections.map((election) => `
    <option value="${escapeHtml(election.id)}">${escapeHtml(election.title)} (${escapeHtml(labelize(election.status))})</option>
  `).join('');
  activeElectionView.hidden = false;
}

async function selectInitialElection() {
  if (!elections.length) {
    activeElection = null;
    activeElectionDetail = null;
    renderQuestions();
    renderEmptyDashboard();
    renderElectionStage();
    renderProxyList();
    return;
  }

  const savedId = window.localStorage.getItem(ACTIVE_ELECTION_KEY);
  const selected = elections.find((election) => election.id === savedId) || elections[0];
  electionSelect.value = selected.id;
  await loadElectionDetail(selected.id);
}

async function loadElectionDetail(electionId) {
  if (!electionId) return;
  activeElectionDetail = await apiRequest(`/api/elections/${encodeURIComponent(electionId)}`);
  activeElection = activeElectionDetail;
  window.localStorage.setItem(ACTIVE_ELECTION_KEY, electionId);
  editingNewElection = false;
  populateElectionForm(activeElectionDetail);
  renderQuestions();
  await loadProxies();
  renderElectionStage();
  await loadDashboard();
}

function renderElectionStage() {
  const status = activeElection ? activeElection.status : '';
  const currentIndex = Math.max(0, ELECTION_FLOW.findIndex((stage) => stage.status === status));
  selectedElectionTitleElement.textContent = activeElection ? activeElection.title : 'Select an election';
  activeElectionStatusElement.textContent = activeElection ? labelize(status) : '-';
  stageListElement.innerHTML = ELECTION_FLOW.map((stage, index) => {
    const state = index < currentIndex ? 'done' : index === currentIndex ? 'current' : '';
    return `<span class="stage-step ${state}">${escapeHtml(stage.label)}</span>`;
  }).join('');

  const action = STAGE_ACTIONS[status];
  stageActionButton.hidden = !action;
  if (action) {
    const quorumBlocked = action.requiresQuorum && activeElection && !activeElection.quorum_reached;
    stageActionButton.textContent = quorumBlocked ? 'Quorum Required' : action.label;
    stageActionButton.disabled = Boolean(quorumBlocked);
  }

  activeElectionView.classList.toggle('is-draft', status === 'draft');
}

function setElectionFormMode(mode) {
  editingNewElection = mode === 'new';
  if (editingNewElection) {
    electionForm.reset();
    electionQuorumInput.value = '50';
    electionStatusSelect.value = 'draft';
    deleteElectionButton.disabled = true;
    saveElectionButton.textContent = 'Create Election';
    setManageStatus('', '');
    return;
  }
  deleteElectionButton.disabled = !activeElection;
  saveElectionButton.textContent = 'Save Election';
}

function populateElectionForm(election) {
  if (!election) {
    setElectionFormMode('new');
    return;
  }
  electionTitleInput.value = election.title || '';
  electionDescriptionInput.value = election.description || '';
  electionQuorumInput.value = election.quorum_percent || 50;
  electionStatusSelect.value = election.status || 'draft';
  includeDefaultersQuorumInput.checked = Boolean(election.include_defaulters_in_quorum);
  allowDefaultersVoteInput.checked = Boolean(election.allow_defaulters_to_vote);
  setElectionFormMode('edit');
}

function renderQuestions() {
  const questions = Array.isArray(activeElectionDetail && activeElectionDetail.questions)
    ? activeElectionDetail.questions
    : [];

  if (!activeElection) {
    questionListElement.innerHTML = '<p class="empty-list">Select or create an election to manage questions.</p>';
    return;
  }

  if (!questions.length) {
    questionListElement.innerHTML = '<p class="empty-list">No questions added yet.</p>';
    return;
  }

  questionListElement.innerHTML = questions.map((question, index) => `
    <article class="question-card">
      <div>
        <span class="question-number">Question ${index + 1}</span>
        <strong>${escapeHtml(question.question_text)}</strong>
      </div>
      <ul>
        ${question.choices.map((choice) => `<li>${escapeHtml(choice.choice_text)}</li>`).join('')}
      </ul>
      <small>${escapeHtml(labelize(question.passing_rule))}</small>
    </article>
  `).join('');
}

function renderEmptyDashboard() {
  totalVillasElement.textContent = '-';
  representedVillasElement.textContent = '-';
  representationPctElement.textContent = '-';
  quorumRequiredElement.textContent = '-';
  activeElectionStatusElement.textContent = activeElection ? labelize(activeElection.status) : '-';
  headerQuorumElement.textContent = '-';
  quorumStatusElement.textContent = 'Select an election to view quorum.';
  representationBarElement.style.width = '0%';
  dashboardAttendees = [];
  attendeeCountElement.textContent = '0';
  renderAttendees();
}

function renderDashboard(data) {
  const totalVillas = Number(data && data.totalVillas ? data.totalVillas : 0);
  const representedVillas = Number(data && data.representedVillas ? data.representedVillas : 0);
  const representationPct = Number(data && data.representationPct ? data.representationPct : 0);
  const election = data && data.election ? data.election : activeElection;
  const attendees = Array.isArray(data && data.attendees) ? data.attendees : [];
  dashboardAttendees = attendees;
  activeElection = election;

  totalVillasElement.textContent = formatInt(totalVillas);
  representedVillasElement.textContent = formatInt(representedVillas);
  representationPctElement.textContent = `${formatPct(representationPct)}%`;
  quorumRequiredElement.textContent = election ? `${formatPct(election.quorum_percent)}%` : '-';
  activeElectionStatusElement.textContent = election ? labelize(election.status) : '-';
  headerQuorumElement.textContent = `${formatPct(representationPct)}% / ${election ? formatPct(election.quorum_percent) : '-'}%`;
  representationBarElement.style.width = `${Math.max(0, Math.min(100, representationPct))}%`;
  attendeeCountElement.textContent = formatInt(attendees.length);
  quorumStatusElement.textContent = election && election.quorum_reached
    ? 'Quorum reached.'
    : 'Quorum not reached yet.';
  quorumStatusElement.className = `quorum-status ${election && election.quorum_reached ? 'success-text' : ''}`;
  renderAttendees();
  renderElectionStage();
  dashboardUpdatedElement.textContent = `Updated ${formatTime(new Date())}`;
}

function renderAttendees() {
  const query = attendeeSearchInput.value.trim().toLowerCase();
  const filtered = query
    ? dashboardAttendees.filter((attendee) => `${attendee.name || ''} ${attendee.flat || ''} ${attendee.house_id || ''}`.toLowerCase().includes(query))
    : dashboardAttendees;

  attendeeListElement.innerHTML = filtered.length
    ? filtered.map(attendeeRowHtml).join('')
    : `<p class="empty-list">${dashboardAttendees.length ? 'No attendees match this search.' : 'No attendance marked yet.'}</p>`;
}

function attendeeRowHtml(attendee) {
  return `
    <div class="attendee-row" role="listitem">
      <span>
        <strong>${escapeHtml(attendee.name || '-')}</strong>
        <small>${escapeHtml([attendee.userType, formatDateTime(attendee.attendanceTime)].filter(Boolean).join(' | '))}</small>
      </span>
      <span class="villa-tag">${escapeHtml(attendee.flat || '-')}</span>
    </div>
  `;
}

async function loadDashboard() {
  if (!activeElectionId()) {
    renderEmptyDashboard();
    return;
  }
  setDashboardLoading('Refreshing attendance dashboard...');
  try {
    const dashboard = await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/attendance/dashboard`);
    renderDashboard(dashboard);
  } catch (error) {
    setDashboardLoading(error.message || 'Could not refresh dashboard.');
  }
}

async function saveElection(event) {
  event.preventDefault();
  const title = electionTitleInput.value.trim();
  if (!title) return;

  setManageStatus('', editingNewElection || !activeElection ? 'Creating election...' : 'Saving election...');
  const payload = {
    title,
    description: electionDescriptionInput.value.trim(),
    quorum_percent: Number(electionQuorumInput.value || 50),
    include_defaulters_in_quorum: includeDefaultersQuorumInput.checked,
    allow_defaulters_to_vote: allowDefaultersVoteInput.checked,
  };

  try {
    let election;
    if (editingNewElection || !activeElection) {
      election = await apiRequest('/api/elections', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (electionStatusSelect.value !== 'draft') {
        await apiRequest(`/api/elections/${encodeURIComponent(election.id)}/status`, {
          method: 'POST',
          body: JSON.stringify({ status: electionStatusSelect.value }),
        });
      }
    } else {
      election = await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      if (electionStatusSelect.value !== activeElection.status) {
        await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}/status`, {
          method: 'POST',
          body: JSON.stringify({ status: electionStatusSelect.value }),
        });
      }
    }

    setManageStatus('success', editingNewElection ? 'Election created.' : 'Election updated.');
    await loadElections();
    electionSelect.value = election.id;
    await loadElectionDetail(election.id);
  } catch (error) {
    setManageStatus('error', error.message || 'Could not save election.');
  }
}

async function deleteElection() {
  if (!activeElection || editingNewElection) return;
  const confirmed = window.confirm(`Delete "${activeElection.title}"? This will remove its setup and attendance records.`);
  if (!confirmed) return;
  try {
    await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}`, { method: 'DELETE' });
    window.localStorage.removeItem(ACTIVE_ELECTION_KEY);
    activeElection = null;
    activeElectionDetail = null;
    setManageStatus('success', 'Election deleted.');
    await loadElections();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not delete election.');
  }
}

async function loadProxies() {
  if (!activeElection) {
    proxies = [];
    renderProxyList();
    return;
  }
  try {
    proxies = await apiRequest(`/api/proxies?election_id=${encodeURIComponent(activeElection.id)}`);
    renderProxyList();
  } catch (error) {
    proxies = [];
    proxyListElement.innerHTML = `<p class="empty-list">${escapeHtml(error.message || 'Could not load proxies.')}</p>`;
  }
}

function renderProxyList() {
  if (!activeElection) {
    proxyListElement.innerHTML = '<p class="empty-list">Select an election to manage proxies.</p>';
    return;
  }
  const scopedProxies = proxies.filter((proxy) => !proxy.election_id || proxy.election_id === activeElection.id);
  if (!scopedProxies.length) {
    proxyListElement.innerHTML = '<p class="empty-list">No proxies configured for this election.</p>';
    return;
  }
  proxyListElement.innerHTML = scopedProxies.map((proxy) => `
    <article class="proxy-row">
      <div>
        <strong>${escapeHtml(proxy.grantor_house_no || proxy.grantor_house_id)}</strong>
        <small>${escapeHtml(proxy.proxy_holder_name || proxy.proxy_holder_user_id)}${proxy.proxy_holder_house_no ? ` | ${escapeHtml(proxy.proxy_holder_house_no)}` : ''}</small>
      </div>
      <button class="secondary small-button" type="button" data-cancel-proxy="${escapeHtml(proxy.id)}">Cancel</button>
    </article>
  `).join('');
}

async function addProxy(event) {
  event.preventDefault();
  if (!requireActiveElection()) return;
  try {
    await apiRequest('/api/proxies', {
      method: 'POST',
      body: JSON.stringify({
        election_id: activeElection.id,
        grantor_house_id: proxyGrantorHouseIdInput.value.trim(),
        proxy_holder_user_id: proxyHolderUserIdInput.value.trim(),
        notes: proxyNotesInput.value.trim(),
      }),
    });
    proxyForm.reset();
    setManageStatus('success', 'Proxy added.');
    await loadProxies();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not add proxy.');
  }
}

async function cancelProxy(proxyId) {
  try {
    await apiRequest(`/api/proxies/${encodeURIComponent(proxyId)}/cancel`, {
        method: 'POST',
      });
    setManageStatus('success', 'Proxy cancelled.');
    await loadProxies();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not cancel proxy.');
  }
}

async function addQuestion(event) {
  event.preventDefault();
  if (!activeElection) {
    setManageStatus('warning', 'Select or create an election before adding questions.');
    return;
  }

  const questionText = questionTextInput.value.trim();
  const choiceOne = choiceOneInput.value.trim();
  const choiceTwo = choiceTwoInput.value.trim();
  if (!questionText || !choiceOne || !choiceTwo) return;

  setManageStatus('', 'Adding question...');
  try {
    const passingRule = passingRuleSelect.value;
    await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/questions`, {
      method: 'POST',
      body: JSON.stringify({
        question_text: questionText,
        passing_rule: passingRule,
        passing_threshold_percent: passingRule === 'custom_threshold' && passingThresholdInput.value
          ? Number(passingThresholdInput.value)
          : null,
        choices: [
          { choice_text: choiceOne, display_order: 1 },
          { choice_text: choiceTwo, display_order: 2 },
        ],
      }),
    });
    questionForm.reset();
    setManageStatus('success', 'Question added.');
    await loadElectionDetail(activeElectionId());
  } catch (error) {
    setManageStatus('error', error.message || 'Could not add question.');
  }
}

async function advanceElectionStage() {
  if (!activeElection) return;
  const action = STAGE_ACTIONS[activeElection.status];
  if (!action) return;
  if (action.requiresQuorum && !activeElection.quorum_reached) {
    setStatus('warning', 'Quorum not reached', 'Voting can open after quorum is reached.');
    return;
  }

  const electionId = activeElection.id;
  stageActionButton.disabled = true;
  try {
    await apiRequest(`/api/elections/${encodeURIComponent(electionId)}/status`, {
      method: 'POST',
      body: JSON.stringify({ status: action.nextStatus }),
    });
    await loadElections();
    electionSelect.value = electionId;
    await loadElectionDetail(electionId);
    setStatus('success', labelize(action.nextStatus), 'Election stage updated.');
  } catch (error) {
    setStatus('error', 'Could not update stage', error.message || 'Please try again.');
  } finally {
    stageActionButton.disabled = false;
  }
}

async function toggleScanner() {
  if (scanning) {
    await stopScanner();
    return;
  }

  if (!requireAttendanceOpen()) return;

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
  submitQr(decodedText, 'qr_scan');
}

async function scanFile(file) {
  if (!file) return;
  if (!requireAttendanceOpen()) return;

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
    submitQr(decodedText, 'qr_upload');
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

async function submitQr(qrRawData, method) {
  if (submitting || !requireAttendanceOpen()) return;

  submitting = true;
  setStatus('', 'Marking attendance', 'Checking Resident Master in Postgres.');

  try {
    const response = await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/attendance/qr`, {
      method: 'POST',
      body: JSON.stringify({
        qr_raw_data: qrRawData,
        method,
        source: 'officer',
      }),
    });
    setStatus('success', 'Attendance marked', 'Villa representation has been updated.', response.resident);
    manualInput.value = '';
    await loadDashboard();
  } catch (error) {
    setStatus('error', 'Could not mark attendance', error.message || 'Please try again.');
  } finally {
    submitting = false;
  }
}

async function submitManualAttendance(event) {
  event.preventDefault();
  if (submitting || !requireAttendanceOpen()) return;

  const userId = manualUserIdInput.value.trim();
  const houseId = manualHouseIdInput.value.trim();
  const name = manualNameInput.value.trim();
  if (!userId && (!houseId || !name)) {
    setStatus('warning', 'Missing details', 'Enter User ID, or enter House ID plus Name.');
    return;
  }

  submitting = true;
  setStatus('', 'Adding attendance', 'Checking the resident record.');
  try {
    const response = await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/attendance/manual`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId || null,
        house_id: houseId || null,
        name: name || null,
        source: 'officer',
      }),
    });
    manualAttendanceForm.reset();
    setStatus('success', 'Attendance marked', 'Manual attendance has been recorded.', response.resident);
    await loadDashboard();
  } catch (error) {
    setStatus('error', 'Could not add attendance', error.message || 'Please try again.');
  } finally {
    submitting = false;
  }
}

function formatInt(value) {
  return Math.round(Number(value || 0)).toLocaleString('en-IN');
}

function formatPct(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function formatTime(date) {
  return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function formatDateTime(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function fieldHtml(label, value) {
  return `
    <div class="field">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value || '-')}</strong>
    </div>
  `;
}

function labelize(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function escapeHtml(value) {
  return String(value == null ? '' : value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

modeTabs.forEach((tab) => {
  tab.addEventListener('click', () => switchMode(tab.dataset.mode));
});
scanButton.addEventListener('click', toggleScanner);
fileInput.addEventListener('change', (event) => scanFile(event.target.files[0]));
manualButton.addEventListener('click', submitManual);
manualAttendanceForm.addEventListener('submit', submitManualAttendance);
refreshDashboardButton.addEventListener('click', loadDashboard);
refreshElectionsButton.addEventListener('click', loadElections);
attendeeSearchInput.addEventListener('input', renderAttendees);
electionForm.addEventListener('submit', saveElection);
questionForm.addEventListener('submit', addQuestion);
electionSelect.addEventListener('change', () => loadElectionDetail(electionSelect.value));
stageActionButton.addEventListener('click', advanceElectionStage);
newElectionButton.addEventListener('click', () => setElectionFormMode('new'));
deleteElectionButton.addEventListener('click', deleteElection);
proxyForm.addEventListener('submit', addProxy);
proxyListElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-cancel-proxy]');
  if (button) {
    cancelProxy(button.dataset.cancelProxy);
  }
});
manualInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    submitManual();
  }
});

switchMode(window.localStorage.getItem(ACTIVE_MODE_KEY) || 'manage');
loadElections();
