const scanButton = document.querySelector('#scan-button');
const fileInput = document.querySelector('#qr-file');
const manualAttendanceForm = document.querySelector('#manual-attendance-form');
const manualVillaInput = document.querySelector('#manual-villa');
const manualVillaResults = document.querySelector('#manual-villa-results');
const manualOwnerSelect = document.querySelector('#manual-owner-user-id');
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
const attendeeFilterSelect = document.querySelector('#attendee-filter');
const voteEligibleCountElement = document.querySelector('#vote-eligible-count');
const voteSubmittedCountElement = document.querySelector('#vote-submitted-count');
const votePendingCountElement = document.querySelector('#vote-pending-count');
const voteStatusLabelElement = document.querySelector('#vote-status-label');
const votingStatusCopyElement = document.querySelector('#voting-status-copy');
const officerResultsElement = document.querySelector('#officer-results');
const refreshVotingStatusButton = document.querySelector('#refresh-voting-status');
const restartVotingButton = document.querySelector('#restart-voting-button');
const dashboardUpdatedElement = document.querySelector('#dashboard-updated');
const refreshDashboardButton = document.querySelector('#refresh-dashboard');
const refreshElectionsButton = document.querySelector('#refresh-elections');
const refreshElectionLibraryButton = document.querySelector('#refresh-election-library');
const electionSelect = document.querySelector('#election-select');
const electionForm = document.querySelector('#election-form');
const electionDialog = document.querySelector('#election-dialog');
const electionDialogTitle = document.querySelector('#election-dialog-title');
const electionDialogLifecycleElement = document.querySelector('#election-dialog-lifecycle');
const closeElectionDialogButton = document.querySelector('#close-election-dialog-button');
const cancelElectionSettingsButton = document.querySelector('#cancel-election-settings-button');
const electionTitleInput = document.querySelector('#election-title');
const electionDescriptionInput = document.querySelector('#election-description');
const electionQuorumInput = document.querySelector('#election-quorum');
const includeDefaultersQuorumInput = document.querySelector('#include-defaulters-quorum');
const questionForm = document.querySelector('#question-form');
const questionTextInput = document.querySelector('#question-text');
const choiceListElement = document.querySelector('#choice-list');
const addChoiceButton = document.querySelector('#add-choice-button');
const passingRuleSelect = document.querySelector('#passing-rule');
const passingThresholdInput = document.querySelector('#passing-threshold');
const questionListElement = document.querySelector('#question-list');
const activeElectionStatusElement = document.querySelector('#active-election-status');
const headerQuorumElement = document.querySelector('#header-quorum');
const activeElectionView = document.querySelector('#active-election-view');
const selectedElectionTitleElement = document.querySelector('#selected-election-title');
const stageListElement = document.querySelector('#stage-list');
const stageActionButton = document.querySelector('#stage-action-button');
const pageTitleElement = document.querySelector('#page-title');
const portalLinks = document.querySelector('#portal-links');
const officerLink = document.querySelector('#officer-link');
const voterLink = document.querySelector('#voter-link');
const officerTabs = document.querySelector('#officer-tabs');
const officerLogoutButton = document.querySelector('#officer-logout-button');
const officerLoginCopyElement = document.querySelector('#officer-login-copy');
const officerAuthStatusElement = document.querySelector('#officer-auth-status');
const googleSignInButton = document.querySelector('#google-signin-button');
const modeTabs = Array.from(document.querySelectorAll('.mode-tab'));
const appViews = Array.from(document.querySelectorAll('.app-view'));
const manageStatusElement = document.querySelector('#manage-status');
const manageElectionLifecycleElement = document.querySelector('#manage-election-lifecycle');
const manageElectionTitleElement = document.querySelector('#manage-election-title');
const manageElectionDescriptionElement = document.querySelector('#manage-election-description');
const settingsLockInfoElement = document.querySelector('#settings-lock-info');
const questionLockInfoElement = document.querySelector('#question-lock-info');
const proxyLockInfoElement = document.querySelector('#proxy-lock-info');
const defaulterLockInfoElement = document.querySelector('#defaulter-lock-info');
const manageQuorumSummaryElement = document.querySelector('#manage-quorum-summary');
const manageQuestionCountElement = document.querySelector('#manage-question-count');
const managePassingRuleSummaryElement = document.querySelector('#manage-passing-rule-summary');
const manageDefaulterSummaryElement = document.querySelector('#manage-defaulter-summary');
const electionLibraryListElement = document.querySelector('#election-library-list');
const newElectionButton = document.querySelector('#new-election-button');
const editElectionButton = document.querySelector('#edit-election-button');
const deleteElectionButton = document.querySelector('#delete-election-button');
const saveElectionButton = document.querySelector('#save-election-button');
const proxyForm = document.querySelector('#proxy-form');
const proxyGrantorVillaInput = document.querySelector('#proxy-grantor-villa');
const proxyGrantorVillaResults = document.querySelector('#proxy-grantor-villa-results');
const proxyHolderVillaInput = document.querySelector('#proxy-holder-villa');
const proxyHolderVillaResults = document.querySelector('#proxy-holder-villa-results');
const proxyHolderUserSelect = document.querySelector('#proxy-holder-user-id');
const proxyListElement = document.querySelector('#proxy-list');
const defaulterForm = document.querySelector('#defaulter-form');
const defaulterVillaInput = document.querySelector('#defaulter-villa');
const defaulterVillaResults = document.querySelector('#defaulter-villa-results');
const defaulterReasonInput = document.querySelector('#defaulter-reason');
const defaulterListElement = document.querySelector('#defaulter-list');
const questionEditActions = document.querySelector('#question-edit-actions');
const cancelQuestionEditButton = document.querySelector('#cancel-question-edit-button');
const deleteQuestionButton = document.querySelector('#delete-question-button');
const voterScanButton = document.querySelector('#voter-scan-button');
const voterFileInput = document.querySelector('#voter-qr-file');
const voterReaderElement = document.querySelector('#voter-qr-reader');
const voterStatusElement = document.querySelector('#voter-status');
const voterIdentityElement = document.querySelector('#voter-identity');
const voterElectionListElement = document.querySelector('#voter-election-list');
const voterLogoutButton = document.querySelector('#voter-logout-button');
const refreshVoterDashboardButton = document.querySelector('#refresh-voter-dashboard');

const DEFAULT_API_URL = 'https://bellezea-elections-api.onrender.com';
const ACTIVE_ELECTION_KEY = 'bellezea-active-election-id';
const ACTIVE_MODE_KEY = 'bellezea-officer-mode';
const VOTER_SESSION_KEY = 'bellezea-voter-session';
const OFFICER_TOKEN_KEY = 'bellezea-officer-token';
const MAX_CHOICE_IMAGE_BYTES = 1600000;
const ELECTION_FLOW = [
  { status: 'attendance_open', label: 'Attendance' },
  { status: 'voting_open', label: 'Voting' },
  { status: 'voting_closed', label: 'Closed' },
];
const STAGE_ACTIONS = {
  draft: { label: 'Start Attendance', nextStatus: 'attendance_open' },
  attendance_open: { label: 'Open Voting', nextStatus: 'voting_open', requiresQuorum: true },
  voting_open: { label: 'Close Voting', nextStatus: 'voting_closed' },
};
const ATTENDANCE_STATUSES = new Set(['attendance_open', 'voting_open']);

let html5QrCode = null;
let scanning = false;
let submitting = false;
let elections = [];
let activeElection = null;
let activeElectionDetail = null;
let dashboardAttendees = [];
let proxies = [];
let defaulters = [];
let residentDirectory = [];
let editingNewElection = false;
let editingQuestionId = null;
let questionChoices = [{ text: '', imageUrl: '' }, { text: '', imageUrl: '' }];
let officerVotingStatus = null;
let voterHtml5QrCode = null;
let voterScanning = false;
let voterSession = null;
let voterDashboard = null;
let publicConfig = null;
let officerToken = window.localStorage.getItem(OFFICER_TOKEN_KEY) || '';
let currentPortal = getCurrentPortal();

function getCurrentPortal() {
  const portalParam = new URLSearchParams(window.location.search).get('portal');
  if (portalParam === 'officer' || portalParam === 'voter') return portalParam;
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  if (path === '/officer') return 'officer';
  if (path === '/voter') return 'voter';
  return 'home';
}

function getApiUrl() {
  const config = window.AttendanceConfig || {};
  return String(config.apiUrl || DEFAULT_API_URL).trim().replace(/\/+$/, '');
}

function activateView(viewId) {
  appViews.forEach((view) => {
    view.classList.toggle('active', view.id === viewId);
  });
}

function switchMode(mode) {
  const target = ['manage', 'run'].includes(mode) ? mode : 'manage';
  modeTabs.forEach((tab) => {
    const active = tab.dataset.mode === target;
    tab.classList.toggle('active', active);
    tab.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  activateView(`${target}-view`);
  window.localStorage.setItem(ACTIVE_MODE_KEY, target);
}

function syncPortalChrome() {
  const isOfficer = currentPortal === 'officer';
  const isVoter = currentPortal === 'voter';
  const isHome = currentPortal === 'home';
  const localPortalPrefix = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const officerHref = localPortalPrefix ? '/?portal=officer' : '/officer';
  const voterHref = localPortalPrefix ? '/?portal=voter' : '/voter';
  document.querySelectorAll('a[href="/officer"], a[href="/?portal=officer"]').forEach((link) => {
    link.href = officerHref;
  });
  document.querySelectorAll('a[href="/voter"], a[href="/?portal=voter"]').forEach((link) => {
    link.href = voterHref;
  });
  portalLinks.hidden = isOfficer && Boolean(officerToken);
  officerTabs.hidden = !isOfficer || !officerToken;
  officerLink.classList.toggle('active', isOfficer);
  voterLink.classList.toggle('active', isVoter);
  if (isOfficer) {
    pageTitleElement.textContent = 'Nambiar Bellezea Elections Officer Console';
  } else if (isVoter) {
    pageTitleElement.textContent = 'Nambiar Bellezea Elections Voter Portal';
  } else if (isHome) {
    pageTitleElement.textContent = 'Nambiar Bellezea Elections';
  }
}

function setStatus(type, title, copy, resident) {
  statusElement.hidden = false;
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

function setVoterStatus(type, title, copy) {
  voterStatusElement.hidden = false;
  voterStatusElement.className = `status ${type || ''}`.trim();
  voterStatusElement.innerHTML = `
    <p class="status-title">${escapeHtml(title)}</p>
    <p class="status-copy">${escapeHtml(copy || '')}</p>
  `;
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

function canEditSetup() {
  return Boolean(activeElection && activeElection.status === 'draft');
}

function canEditQuorum() {
  return Boolean(activeElection && ['draft', 'attendance_open'].includes(activeElection.status));
}

function canEditQuestions() {
  return Boolean(activeElection && ['draft', 'attendance_open'].includes(activeElection.status));
}

function canEditProxies() {
  return canEditSetup();
}

function requireAttendanceOpen() {
  if (!requireActiveElection()) return false;
  if (canTakeAttendance()) return true;
  setStatus('warning', 'Attendance not open', 'Attendance can be marked during Attendance or Voting.');
  return false;
}

function setFormDisabled(form, disabled) {
  Array.from(form.elements).forEach((element) => {
    element.disabled = disabled;
  });
}

async function apiRequest(path, options = {}) {
  const { skipAuth, headers = {}, ...fetchOptions } = options;
  const requestHeaders = {
    'Content-Type': 'application/json',
    ...headers,
  };
  if (!skipAuth && officerToken) {
    requestHeaders.Authorization = `Bearer ${officerToken}`;
  }
  const response = await fetch(`${getApiUrl()}${path}`, {
    ...fetchOptions,
    headers: requestHeaders,
  });
  const contentType = response.headers.get('content-type') || '';
  const body = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) {
    const message = body && body.detail ? body.detail : body || `Request failed with ${response.status}`;
    throw new Error(message);
  }
  return body;
}

async function loadPublicConfig() {
  if (publicConfig) return publicConfig;
  publicConfig = await apiRequest('/api/public-config', { skipAuth: true });
  return publicConfig;
}

function setOfficerAuthStatus(type, message) {
  officerAuthStatusElement.className = `inline-status ${type || ''}`.trim();
  officerAuthStatusElement.textContent = message || '';
}

function waitForGoogleIdentity() {
  return new Promise((resolve, reject) => {
    let attempts = 0;
    const timer = window.setInterval(() => {
      attempts += 1;
      if (window.google && window.google.accounts && window.google.accounts.id) {
        window.clearInterval(timer);
        resolve(window.google.accounts.id);
      } else if (attempts > 60) {
        window.clearInterval(timer);
        reject(new Error('Google sign-in did not load. Refresh the page and try again.'));
      }
    }, 100);
  });
}

async function showOfficerLogin(message = '') {
  syncPortalChrome();
  activateView('officer-auth-view');
  if (message) setOfficerAuthStatus('warning', message);
  try {
    const config = await loadPublicConfig();
    const officerEmail = config.officerEmail || 'bellezea.elections@gmail.com';
    officerLoginCopyElement.textContent = `Only ${officerEmail} can open the election officer console.`;
    if (config.officerAuthDisabled === 'true') {
      googleSignInButton.innerHTML = '<button id="dev-officer-login-button" class="primary" type="button">Open Local Officer Console</button>';
      document.querySelector('#dev-officer-login-button').addEventListener('click', async () => {
        officerToken = 'local-dev';
        window.localStorage.setItem(OFFICER_TOKEN_KEY, officerToken);
        await initializeOfficerPortal();
      });
      setOfficerAuthStatus('warning', 'Local officer auth is disabled for development.');
      return;
    }
    if (!config.googleClientId) {
      setOfficerAuthStatus('warning', 'Google login is not configured yet. Add GOOGLE_CLIENT_ID in Render for the API service.');
      return;
    }
    const googleIdentity = await waitForGoogleIdentity();
    googleSignInButton.innerHTML = '';
    googleIdentity.initialize({
      client_id: config.googleClientId,
      callback: handleOfficerCredential,
      auto_select: false,
    });
    googleIdentity.renderButton(googleSignInButton, {
      theme: 'outline',
      size: 'large',
      text: 'signin_with',
      width: 300,
    });
  } catch (error) {
    setOfficerAuthStatus('error', error.message);
  }
}

async function handleOfficerCredential(response) {
  officerToken = response && response.credential ? response.credential : '';
  if (!officerToken) {
    setOfficerAuthStatus('error', 'Google did not return a login token.');
    return;
  }
  window.localStorage.setItem(OFFICER_TOKEN_KEY, officerToken);
  try {
    await apiRequest('/api/officer/me');
    await initializeOfficerPortal();
  } catch (error) {
    logoutOfficer(false);
    setOfficerAuthStatus('error', error.message);
  }
}

function logoutOfficer(showLogin = true) {
  officerToken = '';
  window.localStorage.removeItem(OFFICER_TOKEN_KEY);
  if (window.google && window.google.accounts && window.google.accounts.id) {
    window.google.accounts.id.disableAutoSelect();
  }
  if (showLogin) {
    showOfficerLogin('Signed out.');
  } else {
    syncPortalChrome();
  }
}

async function initializeOfficerPortal() {
  syncPortalChrome();
  if (!officerToken) {
    await showOfficerLogin();
    return;
  }
  try {
    await apiRequest('/api/officer/me');
  } catch (error) {
    logoutOfficer(false);
    await showOfficerLogin(error.message);
    return;
  }
  syncPortalChrome();
  switchMode(window.localStorage.getItem(ACTIVE_MODE_KEY) || 'manage');
  renderChoiceInputs(['', '']);
  await Promise.all([loadResidentDirectory(), loadDefaulters(), loadElections()]);
}

function initializeVoterPortal() {
  syncPortalChrome();
  activateView('voter-view');
  restoreVoterSession();
}

async function initializeApp() {
  syncPortalChrome();
  if (currentPortal === 'officer') {
    await initializeOfficerPortal();
  } else if (currentPortal === 'voter') {
    initializeVoterPortal();
  } else {
    activateView('home-view');
  }
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

async function loadResidentDirectory() {
  try {
    residentDirectory = await apiRequest('/api/resident-directory');
    renderManualOwners();
    renderProxyHolderOwners();
  } catch (error) {
    residentDirectory = [];
    renderVillaSuggestions(manualVillaInput, manualVillaResults);
    renderManualOwners();
    renderVillaSuggestions(proxyGrantorVillaInput, proxyGrantorVillaResults);
    renderVillaSuggestions(proxyHolderVillaInput, proxyHolderVillaResults);
    renderVillaSuggestions(defaulterVillaInput, defaulterVillaResults);
    setManageStatus('error', error.message || 'Could not load Resident Master villas.');
  }
}

function normalizeLookupValue(value) {
  return String(value || '').trim().toLowerCase();
}

function searchTokens(value) {
  return normalizeLookupValue(value)
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
}

function villaSearchText(villa) {
  return normalizeLookupValue(villa.house_no);
}

function matchingVillas(value) {
  const tokens = searchTokens(value);
  if (!tokens.length) return [];
  return residentDirectory
    .filter((villa) => tokens.every((token) => villaSearchText(villa).includes(token)))
    .slice(0, 8);
}

function renderVillaSuggestions(input, resultElement) {
  const matches = matchingVillas(input.value);
  if (!input.value.trim()) {
    resultElement.innerHTML = '';
    return;
  }
  if (!matches.length) {
    resultElement.innerHTML = '<p>No matching villa found.</p>';
    return;
  }
  resultElement.innerHTML = matches.map((villa) => `
    <button type="button" class="villa-search-option" data-house-no="${escapeHtml(villa.house_no)}">
      <strong>${escapeHtml(villa.house_no)}</strong>
      <small>${escapeHtml((villa.owners || []).map((owner) => owner.name).join(', ') || 'No owner listed')}</small>
    </button>
  `).join('');
}

function selectVillaSuggestion(input, resultElement, houseNo) {
  input.value = houseNo;
  resultElement.innerHTML = '';
  if (input === manualVillaInput) {
    renderManualOwners();
  }
  if (input === proxyHolderVillaInput) {
    renderProxyHolderOwners();
  }
}

function findVillaByInput(value) {
  const normalized = normalizeLookupValue(value);
  if (!normalized) return null;
  return residentDirectory.find((villa) => (
    normalizeLookupValue(villa.house_no) === normalized
  )) || null;
}

function renderProxyHolderOwners() {
  renderOwnerSelectForVilla({
    villaInput: proxyHolderVillaInput,
    ownerSelect: proxyHolderUserSelect,
    disabled: activeElection ? !canEditProxies() : true,
    selectVillaMessage: 'Select a valid proxy holder villa first',
    noOwnerMessage: 'No owner found for this villa',
  });
}

function renderManualOwners() {
  renderOwnerSelectForVilla({
    villaInput: manualVillaInput,
    ownerSelect: manualOwnerSelect,
    disabled: activeElection ? !canTakeAttendance() : true,
    selectVillaMessage: 'Select a valid villa first',
    noOwnerMessage: 'No owner found for this villa',
  });
}

function renderOwnerSelectForVilla({ villaInput, ownerSelect, disabled, selectVillaMessage, noOwnerMessage }) {
  const villa = findVillaByInput(villaInput.value);
  const owners = villa ? villa.owners || [] : [];
  if (!villa) {
    ownerSelect.innerHTML = `<option value="">${escapeHtml(selectVillaMessage)}</option>`;
    ownerSelect.disabled = true;
    return;
  }
  if (!owners.length) {
    ownerSelect.innerHTML = `<option value="">${escapeHtml(noOwnerMessage)}</option>`;
    ownerSelect.disabled = true;
    return;
  }
  ownerSelect.disabled = disabled;
  ownerSelect.innerHTML = [
    '<option value="">Select owner name</option>',
    ...owners.map((owner) => (
      `<option value="${escapeHtml(owner.user_id)}|${escapeHtml(owner.house_id)}">${escapeHtml(owner.name)}</option>`
    )),
  ].join('');
}

function parseResidentOption(value) {
  const [userId, houseId] = String(value || '').split('|');
  return {
    userId: userId || '',
    houseId: houseId || '',
  };
}

function renderElectionSelect() {
  if (!elections.length) {
    electionSelect.innerHTML = '<option value="">No elections yet</option>';
    renderElectionLibrary();
    activeElectionView.hidden = true;
    renderManageSummary();
    return;
  }
  electionSelect.innerHTML = elections.map((election) => `
    <option value="${escapeHtml(election.id)}">${escapeHtml(election.title)} (${escapeHtml(labelize(election.status))})</option>
  `).join('');
  renderElectionLibrary();
  activeElectionView.hidden = false;
}

function renderElectionLibrary() {
  if (!electionLibraryListElement) return;
  if (!elections.length) {
    electionLibraryListElement.innerHTML = '<p class="empty-list">No elections yet.</p>';
    return;
  }
  electionLibraryListElement.innerHTML = elections.map((election) => {
    const active = activeElection && activeElection.id === election.id;
    const count = Number(election.question_count || 0);
    const questionCount = `${count} ${count === 1 ? 'question' : 'questions'}`;
    return `
      <button class="election-list-item ${active ? 'active' : ''}" type="button" data-election-id="${escapeHtml(election.id)}">
        <span>
          <strong>${escapeHtml(election.title)}</strong>
          <small>${escapeHtml([runStatusLabel(election.status), questionCount].filter(Boolean).join(' | '))}</small>
        </span>
        <span class="mini-metric">${escapeHtml(formatPct(election.quorum_percent))}%</span>
      </button>
    `;
  }).join('');
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
  renderElectionLibrary();
  renderManageSummary();
  renderQuestions();
  await loadProxies();
  renderElectionStage();
  await loadDashboard();
}

function renderElectionStage() {
  const status = activeElection ? activeElection.status : '';
  const normalizedStatus = runStageStatus(status);
  const stageIndex = ELECTION_FLOW.findIndex((stage) => stage.status === normalizedStatus);
  const currentIndex = stageIndex >= 0 ? stageIndex : 0;
  selectedElectionTitleElement.textContent = activeElection ? activeElection.title : 'Select an election';
  activeElectionStatusElement.textContent = activeElection ? runStatusLabel(status) : '-';
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
  renderManualOwners();
  syncManageLocks();
}

function setElectionFormMode(mode) {
  editingNewElection = mode === 'new';
  if (editingNewElection) {
    electionForm.reset();
    electionQuorumInput.value = '50';
    passingRuleSelect.value = 'simple_majority';
    passingThresholdInput.value = '';
    syncPassingRuleControl();
    electionDialogTitle.textContent = 'New Election';
    electionDialogLifecycleElement.textContent = 'Draft';
    saveElectionButton.textContent = 'Create Election';
    setFormDisabled(electionForm, false);
    setManageStatus('', '');
    return;
  }
  electionDialogTitle.textContent = 'Election Settings';
  electionDialogLifecycleElement.textContent = activeElection ? runStatusLabel(activeElection.status) : 'Draft';
  syncManageLocks();
  saveElectionButton.textContent = activeElection && !canEditSetup() && canEditQuorum() ? 'Save Quorum' : 'Save Election';
}

function populateElectionForm(election) {
  if (!election) {
    setElectionFormMode('new');
    return;
  }
  electionTitleInput.value = election.title || '';
  electionDescriptionInput.value = election.description || '';
  electionQuorumInput.value = election.quorum_percent || 50;
  passingRuleSelect.value = election.passing_rule || 'simple_majority';
  passingThresholdInput.value = election.passing_threshold_percent || '';
  syncPassingRuleControl();
  electionDialogLifecycleElement.textContent = runStatusLabel(election.status);
  includeDefaultersQuorumInput.checked = Boolean(
    election.include_defaulters_in_quorum || election.allow_defaulters_to_vote
  );
  setElectionFormMode('edit');
}

function syncManageLocks() {
  const setupLocked = activeElection ? !canEditSetup() : true;
  const quorumLocked = activeElection ? !canEditQuorum() : true;
  const questionLocked = activeElection ? !canEditQuestions() : true;
  const proxyLocked = activeElection ? !canEditProxies() : true;
  setFormDisabled(electionForm, editingNewElection ? false : setupLocked);
  if (!editingNewElection && setupLocked && !quorumLocked) {
    electionQuorumInput.disabled = false;
    saveElectionButton.disabled = false;
    cancelElectionSettingsButton.disabled = false;
  }
  setFormDisabled(questionForm, questionLocked);
  setFormDisabled(proxyForm, proxyLocked);
  setFormDisabled(defaulterForm, setupLocked);
  newElectionButton.disabled = false;
  editElectionButton.disabled = (!canEditSetup() && !canEditQuorum()) || !activeElection;
  editElectionButton.textContent = activeElection && !canEditSetup() && canEditQuorum() ? 'Edit Quorum' : 'Edit Settings';
  deleteElectionButton.disabled = !activeElection;
  saveElectionButton.disabled = editingNewElection ? false : (!canEditSetup() && !canEditQuorum());
  if (!editingNewElection) {
    saveElectionButton.textContent = activeElection && !canEditSetup() && canEditQuorum() ? 'Save Quorum' : 'Save Election';
  }
  questionEditActions.classList.toggle('hidden', !editingQuestionId);
  renderManageSummary();
  renderDefaulterList();
  renderSectionLockInfo({ setupLocked, quorumLocked, questionLocked, proxyLocked });
  if (proxyLocked && activeElection && activeElection.status !== 'draft') {
    proxyForm.title = 'Proxy changes are locked after attendance starts.';
  } else {
    proxyForm.title = '';
  }
  defaulterForm.title = setupLocked && activeElection ? 'Defaulter changes are locked after attendance starts.' : '';
}

function renderSectionLockInfo({ setupLocked, quorumLocked, questionLocked, proxyLocked }) {
  if (!activeElection) {
    settingsLockInfoElement.textContent = 'Select an election first.';
    questionLockInfoElement.textContent = 'Select an election first.';
    proxyLockInfoElement.textContent = 'Select an election first.';
    defaulterLockInfoElement.textContent = 'Select an election first.';
    return;
  }

  settingsLockInfoElement.textContent = setupLocked
    ? (quorumLocked ? 'Locked after voting starts.' : 'Only quorum can change now.')
    : '';
  questionLockInfoElement.textContent = questionLocked ? 'Locked after voting starts.' : '';
  proxyLockInfoElement.textContent = proxyLocked ? 'Locked after attendance starts.' : '';
  defaulterLockInfoElement.textContent = setupLocked ? 'Locked after attendance starts.' : '';
}

function renderManageSummary() {
  const questions = Array.isArray(activeElectionDetail && activeElectionDetail.questions)
    ? activeElectionDetail.questions
    : [];
  if (!activeElection) {
    manageElectionLifecycleElement.textContent = '-';
    manageElectionTitleElement.textContent = 'Select an election';
    manageElectionDescriptionElement.textContent = 'Create or select an election to manage its questions and proxies.';
    manageQuorumSummaryElement.textContent = '-';
    manageQuestionCountElement.textContent = '0';
    managePassingRuleSummaryElement.textContent = '-';
    manageDefaulterSummaryElement.textContent = '-';
    editElectionButton.disabled = true;
    deleteElectionButton.disabled = true;
    return;
  }

  manageElectionLifecycleElement.textContent = runStatusLabel(activeElection.status);
  manageElectionTitleElement.textContent = activeElection.title || 'Untitled election';
  manageElectionDescriptionElement.textContent = activeElection.description || 'No description added.';
  manageQuorumSummaryElement.textContent = `${formatPct(activeElection.quorum_percent)}%`;
  manageQuestionCountElement.textContent = formatInt(questions.length);
  managePassingRuleSummaryElement.textContent = passingRuleLabel(
    activeElection.passing_rule,
    activeElection.passing_threshold_percent
  );
  manageDefaulterSummaryElement.textContent = activeElection.include_defaulters_in_quorum || activeElection.allow_defaulters_to_vote
    ? 'Allowed'
    : 'Excluded';
}

function openElectionSettings(mode) {
  if (mode === 'new') {
    setElectionFormMode('new');
  } else {
    if (!activeElection) return;
    populateElectionForm(activeElection);
  }
  if (typeof electionDialog.showModal === 'function') {
    electionDialog.showModal();
  } else {
    electionDialog.setAttribute('open', '');
  }
  electionTitleInput.focus();
}

function closeElectionSettings() {
  electionDialog.close();
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
    <article class="question-card" data-question-id="${escapeHtml(question.id)}">
      <div>
        <span class="question-number">Question ${index + 1}</span>
        <strong>${escapeHtml(question.question_text)}</strong>
      </div>
      <ul>
        ${question.choices.map((choice) => `
          <li class="question-choice-item">
            ${choice.image_url ? `<img class="question-choice-thumb" src="${escapeHtml(choice.image_url)}" alt="">` : ''}
            <span>${escapeHtml(choice.choice_text)}</span>
          </li>
        `).join('')}
      </ul>
      <div class="question-card-actions">
        <small>${escapeHtml(question.choices.length)} choices</small>
        <button class="secondary small-button" type="button" data-edit-question="${escapeHtml(question.id)}" ${canEditQuestions() ? '' : 'disabled'}>Edit</button>
      </div>
    </article>
  `).join('');
}

function renderEmptyDashboard() {
  totalVillasElement.textContent = '-';
  representedVillasElement.textContent = '-';
  representationPctElement.textContent = '-';
  quorumRequiredElement.textContent = '-';
  activeElectionStatusElement.textContent = activeElection ? runStatusLabel(activeElection.status) : '-';
  headerQuorumElement.textContent = '-';
  quorumStatusElement.textContent = 'Select an election to view quorum.';
  representationBarElement.style.width = '0%';
  dashboardAttendees = [];
  attendeeCountElement.textContent = '0';
  renderAttendees();
  renderOfficerVotingStatus(null);
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
  activeElectionStatusElement.textContent = election ? runStatusLabel(election.status) : '-';
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

function renderOfficerVotingStatus(data) {
  officerVotingStatus = data;
  if (!data || !data.election) {
    voteEligibleCountElement.textContent = '-';
    voteSubmittedCountElement.textContent = '-';
    votePendingCountElement.textContent = '-';
    voteStatusLabelElement.textContent = '-';
    votingStatusCopyElement.textContent = 'Select an election to view voting status.';
    officerResultsElement.innerHTML = '';
    restartVotingButton.hidden = true;
    return;
  }

  const election = data.election;
  voteEligibleCountElement.textContent = formatInt(data.represented_villas);
  voteSubmittedCountElement.textContent = formatInt(data.voted_villas);
  votePendingCountElement.textContent = formatInt(data.pending_villas);
  voteStatusLabelElement.textContent = runStatusLabel(election.status);
  restartVotingButton.hidden = !['voting_open', 'voting_closed', 'results_published'].includes(election.status);

  if (election.status === 'voting_open') {
    votingStatusCopyElement.textContent = 'Voting is open. Question-wise results stay hidden until voting closes.';
    officerResultsElement.innerHTML = '';
  } else if (['voting_closed', 'results_published', 'archived'].includes(election.status)) {
    votingStatusCopyElement.textContent = 'Voting is closed. Final results are available below.';
    officerResultsElement.innerHTML = renderResultsList(data.results || []);
  } else {
    votingStatusCopyElement.textContent = 'Voting has not opened yet.';
    officerResultsElement.innerHTML = '';
  }
}

async function restartVoting() {
  if (!activeElection) return;
  const electionId = activeElection.id;
  const confirmed = window.confirm(
    `Restart voting for "${activeElection.title}"? This will permanently delete all submitted votes for this election.`
  );
  if (!confirmed) return;
  restartVotingButton.disabled = true;
  try {
    await apiRequest(`/api/elections/${encodeURIComponent(electionId)}/restart-voting`, {
      method: 'POST',
    });
    setStatus('success', 'Voting restarted', 'All previously submitted votes were cleared.');
    await loadElections();
    electionSelect.value = electionId;
    await loadElectionDetail(electionId);
  } catch (error) {
    setStatus('error', 'Could not restart voting', error.message || 'Please try again.');
  } finally {
    restartVotingButton.disabled = false;
  }
}

async function loadVotingStatus() {
  if (!activeElectionId()) {
    renderOfficerVotingStatus(null);
    return;
  }
  try {
    const status = await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/voting-status`);
    renderOfficerVotingStatus(status);
  } catch (error) {
    votingStatusCopyElement.textContent = error.message || 'Could not load voting status.';
    officerResultsElement.innerHTML = '';
  }
}

function renderAttendees() {
  const query = attendeeSearchInput.value.trim().toLowerCase();
  const filter = attendeeFilterSelect.value;
  const filtered = dashboardAttendees.filter((attendee) => {
    const matchesQuery = !query
      || `${attendee.name || ''} ${attendee.flat || ''} ${attendee.house_id || ''} ${attendee.voteSubmittedByName || ''}`.toLowerCase().includes(query);
    const matchesFilter = filter === 'all'
      || (filter === 'pending' && !attendee.hasVoted)
      || (filter === 'voted' && attendee.hasVoted);
    return matchesQuery && matchesFilter;
  });

  attendeeListElement.innerHTML = filtered.length
    ? filtered.map(attendeeRowHtml).join('')
    : `<p class="empty-list">${dashboardAttendees.length ? 'No attendees match this search.' : 'No attendance marked yet.'}</p>`;
}

function attendeeRowHtml(attendee) {
  const voteCopy = attendee.hasVoted
    ? `Voted by ${attendee.voteSubmittedByName || 'owner'}${attendee.votedAt ? ` | ${formatDateTime(attendee.votedAt)}` : ''}`
    : 'Not voted';
  return `
    <div class="attendee-row ${attendee.hasVoted ? 'has-voted' : ''}" role="listitem">
      <span>
        <strong>${escapeHtml(attendee.name || '-')}</strong>
        <small>${escapeHtml([attendee.userType, formatDateTime(attendee.attendanceTime)].filter(Boolean).join(' | '))}</small>
        <small>${escapeHtml(voteCopy)}</small>
      </span>
      <span>
        <span class="villa-tag">${escapeHtml(attendee.flat || '-')}</span>
        <span class="vote-tag ${attendee.hasVoted ? 'voted' : 'pending'}">${attendee.hasVoted ? 'Voted' : 'Pending'}</span>
      </span>
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
    await loadVotingStatus();
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
    passing_rule: passingRuleSelect.value,
    passing_threshold_percent: passingRuleSelect.value === 'custom_threshold' && passingThresholdInput.value
      ? Number(passingThresholdInput.value)
      : null,
    include_defaulters_in_quorum: includeDefaultersQuorumInput.checked,
    allow_defaulters_to_vote: includeDefaultersQuorumInput.checked,
  };

  try {
    let election;
    if (editingNewElection || !activeElection) {
      election = await apiRequest('/api/elections', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } else if (!canEditSetup() && canEditQuorum()) {
      election = await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}/quorum`, {
        method: 'PATCH',
        body: JSON.stringify({ quorum_percent: payload.quorum_percent }),
      });
    } else {
      election = await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    }

    setManageStatus('success', editingNewElection ? 'Election created.' : 'Election updated.');
    closeElectionSettings();
    await loadElections();
    electionSelect.value = election.id;
    await loadElectionDetail(election.id);
  } catch (error) {
    setManageStatus('error', error.message || 'Could not save election.');
  }
}

async function deleteElection() {
  if (!activeElection || editingNewElection) return;
  const confirmed = window.confirm(
    `Delete "${activeElection.title}"?\n\nAll information for this election will be permanently lost, including settings, questions, attendance, proxies, votes, and results.\n\nThis delete option is enabled only while the app is under development.`
  );
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

async function loadDefaulters() {
  try {
    defaulters = await apiRequest('/api/defaulters');
    renderDefaulterList();
  } catch (error) {
    defaulters = [];
    defaulterListElement.innerHTML = `<p class="empty-list">${escapeHtml(error.message || 'Could not load defaulters.')}</p>`;
  }
}

function renderProxyList() {
  if (!activeElection) {
    proxyListElement.innerHTML = '<p class="empty-list">Select an election to manage proxies.</p>';
    return;
  }
  const scopedProxies = proxies.filter((proxy) => (
    proxy.status === 'active'
    && (!proxy.election_id || proxy.election_id === activeElection.id)
  ));
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
      <button class="secondary small-button" type="button" data-delete-proxy="${escapeHtml(proxy.id)}" ${canEditProxies() ? '' : 'disabled'}>Delete</button>
    </article>
  `).join('');
}

function renderDefaulterList() {
  if (!defaulters.length) {
    defaulterListElement.innerHTML = '<p class="empty-list">No active defaulters.</p>';
    return;
  }
  defaulterListElement.innerHTML = defaulters.map((defaulter) => `
    <article class="defaulter-row">
      <div>
        <strong>${escapeHtml(defaulter.house_no || defaulter.house_id)}</strong>
        <small>${escapeHtml(defaulter.reason || 'No reason added')}</small>
      </div>
      <button class="secondary small-button" type="button" data-clear-defaulter="${escapeHtml(defaulter.id)}" ${canEditSetup() ? '' : 'disabled'}>Remove</button>
    </article>
  `).join('');
}

async function addProxy(event) {
  event.preventDefault();
  if (!requireActiveElection()) return;
  if (!canEditProxies()) {
    setManageStatus('warning', 'Proxy changes are locked after attendance starts.');
    return;
  }
  const grantorVilla = findVillaByInput(proxyGrantorVillaInput.value);
  const holderVilla = findVillaByInput(proxyHolderVillaInput.value);
  const proxyHolder = parseResidentOption(proxyHolderUserSelect.value);
  if (!grantorVilla) {
    setManageStatus('warning', 'Select a valid grantor villa from Resident Master.');
    return;
  }
  if (!holderVilla) {
    setManageStatus('warning', 'Select a valid proxy holder villa from Resident Master.');
    return;
  }
  if (!proxyHolder.userId || !proxyHolder.houseId) {
    setManageStatus('warning', 'Select an owner name from the proxy holder villa.');
    return;
  }
  try {
    await apiRequest('/api/proxies', {
      method: 'POST',
      body: JSON.stringify({
        election_id: activeElection.id,
        grantor_house_id: grantorVilla.house_id,
        proxy_holder_user_id: proxyHolder.userId,
        proxy_holder_house_id: proxyHolder.houseId,
        notes: '',
      }),
    });
    proxyForm.reset();
    proxyGrantorVillaResults.innerHTML = '';
    proxyHolderVillaResults.innerHTML = '';
    renderProxyHolderOwners();
    setManageStatus('success', 'Proxy added.');
    await loadProxies();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not add proxy.');
  }
}

async function addDefaulter(event) {
  event.preventDefault();
  if (!canEditSetup()) {
    setManageStatus('warning', 'Defaulter changes are locked after attendance starts.');
    return;
  }
  const villa = findVillaByInput(defaulterVillaInput.value);
  if (!villa) {
    setManageStatus('warning', 'Select a valid defaulter villa from Resident Master.');
    return;
  }
  try {
    await apiRequest('/api/defaulters', {
      method: 'POST',
      body: JSON.stringify({
        house_id: villa.house_id,
        reason: defaulterReasonInput.value.trim(),
      }),
    });
    defaulterForm.reset();
    defaulterVillaResults.innerHTML = '';
    setManageStatus('success', 'Defaulter added.');
    await loadDefaulters();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not add defaulter.');
  }
}

async function clearDefaulter(defaulterId) {
  if (!canEditSetup()) {
    setManageStatus('warning', 'Defaulter changes are locked after attendance starts.');
    return;
  }
  try {
    await apiRequest(`/api/defaulters/${encodeURIComponent(defaulterId)}/clear`, {
      method: 'POST',
    });
    setManageStatus('success', 'Defaulter removed.');
    await loadDefaulters();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not remove defaulter.');
  }
}

async function cancelProxy(proxyId) {
  if (!canEditProxies()) {
    setManageStatus('warning', 'Proxy changes are locked after attendance starts.');
    return;
  }
  try {
    await apiRequest(`/api/proxies/${encodeURIComponent(proxyId)}/cancel`, {
        method: 'POST',
      });
    setManageStatus('success', 'Proxy deleted.');
    await loadProxies();
  } catch (error) {
    setManageStatus('error', error.message || 'Could not delete proxy.');
  }
}

function renderChoiceInputs(values = questionChoices) {
  questionChoices = values.length >= 2
    ? values.map(normalizeChoice)
    : [{ text: '', imageUrl: '' }, { text: '', imageUrl: '' }];
  choiceListElement.innerHTML = questionChoices.map((choice, index) => `
    <div class="choice-row" data-choice-index="${index}" data-image-url="${escapeHtml(choice.imageUrl)}">
      <span>${index + 1}</span>
      <div class="choice-main">
        <input class="choice-input" type="text" autocomplete="off" value="${escapeHtml(choice.text)}" aria-label="Choice ${index + 1}" required>
        <div class="choice-image-controls">
          <label class="choice-upload small-button">
            <input class="choice-image-input" type="file" accept="image/*" data-choice-image="${index}">
            <span>${choice.imageUrl ? 'Replace Image' : 'Upload Image'}</span>
          </label>
          ${choice.imageUrl ? `
            <img class="choice-preview" src="${escapeHtml(choice.imageUrl)}" alt="">
            <button class="secondary small-button" type="button" data-remove-choice-image="${index}">Remove Image</button>
          ` : ''}
        </div>
      </div>
      <button class="secondary small-button" type="button" data-remove-choice="${index}" ${questionChoices.length <= 2 ? 'disabled' : ''}>Remove</button>
    </div>
  `).join('');
}

function normalizeChoice(choice) {
  if (typeof choice === 'string') {
    return { text: choice, imageUrl: '' };
  }
  return {
    text: choice && (choice.text || choice.choice_text) ? String(choice.text || choice.choice_text) : '',
    imageUrl: choice && (choice.imageUrl || choice.image_url) ? String(choice.imageUrl || choice.image_url) : '',
  };
}

function syncChoiceStateFromInputs() {
  questionChoices = Array.from(choiceListElement.querySelectorAll('.choice-row')).map((row) => ({
    text: row.querySelector('.choice-input').value,
    imageUrl: row.dataset.imageUrl || '',
  }));
}

function addChoiceInput() {
  syncChoiceStateFromInputs();
  renderChoiceInputs([...questionChoices, { text: '', imageUrl: '' }]);
  const inputs = choiceListElement.querySelectorAll('.choice-input');
  inputs[inputs.length - 1].focus();
}

function removeChoiceInput(index) {
  syncChoiceStateFromInputs();
  if (questionChoices.length <= 2) return;
  questionChoices.splice(index, 1);
  renderChoiceInputs(questionChoices);
}

function removeChoiceImage(index) {
  syncChoiceStateFromInputs();
  if (!questionChoices[index]) return;
  questionChoices[index].imageUrl = '';
  renderChoiceInputs(questionChoices);
}

async function handleChoiceImageChange(input) {
  const index = Number(input.dataset.choiceImage);
  const file = input.files && input.files[0];
  if (!file || Number.isNaN(index)) return;
  if (file.size > MAX_CHOICE_IMAGE_BYTES) {
    input.value = '';
    setManageStatus('warning', 'Choice image is too large. Use an image under 1.6 MB.');
    return;
  }
  syncChoiceStateFromInputs();
  questionChoices[index].imageUrl = await readFileAsDataUrl(file);
  renderChoiceInputs(questionChoices);
}

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('Could not read image'));
    reader.readAsDataURL(file);
  });
}

function getQuestionChoices() {
  syncChoiceStateFromInputs();
  return questionChoices
    .map((choice, index) => ({
      choice_text: choice.text.trim(),
      image_url: choice.imageUrl || null,
      display_order: index + 1,
    }))
    .filter((choice) => choice.choice_text);
}

async function addQuestion(event) {
  event.preventDefault();
  if (!activeElection) {
    setManageStatus('warning', 'Select or create an election before adding questions.');
    return;
  }
  if (!canEditQuestions()) {
    setManageStatus('warning', 'Questions are locked once voting starts.');
    return;
  }

  const questionText = questionTextInput.value.trim();
  const choices = getQuestionChoices();
  if (!questionText || choices.length < 2) {
    setManageStatus('warning', 'Add a question and at least two choices.');
    return;
  }

  setManageStatus('', editingQuestionId ? 'Saving question...' : 'Adding question...');
  const payload = {
    question_text: questionText,
    choices,
  };
  try {
    const path = editingQuestionId
      ? `/api/elections/${encodeURIComponent(activeElectionId())}/questions/${encodeURIComponent(editingQuestionId)}`
      : `/api/elections/${encodeURIComponent(activeElectionId())}/questions`;
    await apiRequest(path, {
      method: editingQuestionId ? 'PATCH' : 'POST',
      body: JSON.stringify(payload),
    });
    clearQuestionForm();
    setManageStatus('success', editingQuestionId ? 'Question updated.' : 'Question added.');
    await loadElectionDetail(activeElectionId());
  } catch (error) {
    setManageStatus('error', error.message || 'Could not add question.');
  }
}

function editQuestion(questionId) {
  if (!canEditQuestions()) return;
  const question = activeElectionDetail.questions.find((item) => item.id === questionId);
  if (!question) return;
  editingQuestionId = questionId;
  questionTextInput.value = question.question_text || '';
  renderChoiceInputs(question.choices.map((choice) => ({
    text: choice.choice_text,
    imageUrl: choice.image_url || '',
  })));
  questionForm.querySelector('button[type="submit"]').textContent = 'Save Question';
  questionEditActions.classList.remove('hidden');
}

function clearQuestionForm() {
  editingQuestionId = null;
  questionForm.reset();
  renderChoiceInputs([{ text: '', imageUrl: '' }, { text: '', imageUrl: '' }]);
  questionForm.querySelector('button[type="submit"]').textContent = 'Add Question';
  questionEditActions.classList.add('hidden');
}

async function deleteQuestion() {
  if (!editingQuestionId || !activeElection) return;
  if (!canEditQuestions()) return;
  try {
    await apiRequest(`/api/elections/${encodeURIComponent(activeElection.id)}/questions/${encodeURIComponent(editingQuestionId)}`, {
      method: 'DELETE',
    });
    clearQuestionForm();
    setManageStatus('success', 'Question deleted.');
    await loadElectionDetail(activeElection.id);
  } catch (error) {
    setManageStatus('error', error.message || 'Could not delete question.');
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

  const villa = findVillaByInput(manualVillaInput.value);
  const owner = parseResidentOption(manualOwnerSelect.value);
  if (!villa) {
    setStatus('warning', 'Select a valid villa', 'Choose the villa from Resident Master search results.');
    return;
  }
  if (!owner.userId || !owner.houseId) {
    setStatus('warning', 'Select owner name', 'Choose one of the owner names for the selected villa.');
    return;
  }

  submitting = true;
  setStatus('', 'Adding attendance', 'Checking the resident record.');
  try {
    const response = await apiRequest(`/api/elections/${encodeURIComponent(activeElectionId())}/attendance/manual`, {
      method: 'POST',
      body: JSON.stringify({
        user_id: owner.userId,
        house_id: owner.houseId,
        source: 'officer',
      }),
    });
    manualAttendanceForm.reset();
    manualVillaResults.innerHTML = '';
    renderManualOwners();
    setStatus('success', 'Attendance marked', 'Manual attendance has been recorded.', response.resident);
    await loadDashboard();
  } catch (error) {
    setStatus('error', 'Could not add attendance', error.message || 'Please try again.');
  } finally {
    submitting = false;
  }
}

function restoreVoterSession() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(VOTER_SESSION_KEY) || 'null');
    if (saved && saved.user_id) {
      voterSession = saved;
      renderVoterIdentity(saved);
      loadVoterDashboard();
    }
  } catch (_error) {
    window.localStorage.removeItem(VOTER_SESSION_KEY);
  }
}

function renderVoterIdentity(resident) {
  voterLogoutButton.hidden = !resident;
  voterIdentityElement.hidden = !resident;
  if (!resident) {
    voterIdentityElement.innerHTML = '';
    return;
  }
  voterIdentityElement.innerHTML = `
    ${fieldHtml('Name', resident.name)}
    ${fieldHtml('Villa', resident.house_no)}
    ${fieldHtml('User Type', resident.user_type)}
    ${fieldHtml('Status', resident.status)}
  `;
}

async function loginVoter(qrRawData) {
  setVoterStatus('', 'Checking QR', 'Looking up your MyGate QR in Resident Master.');
  try {
    const response = await apiRequest('/api/auth/qr-login', {
      method: 'POST',
      body: JSON.stringify({
        qr_raw_data: qrRawData,
        method: 'qr_scan',
        source: 'voter',
      }),
    });
    voterSession = response.resident;
    window.localStorage.setItem(VOTER_SESSION_KEY, JSON.stringify(voterSession));
    renderVoterIdentity(voterSession);
    setVoterStatus('success', 'Logged in', `Welcome, ${voterSession.name}.`);
    await loadVoterDashboard();
  } catch (error) {
    setVoterStatus('error', 'Could not log in', error.message || 'Please try again.');
  }
}

async function loadVoterDashboard() {
  if (!voterSession || !voterSession.user_id) {
    voterElectionListElement.innerHTML = '<p class="empty-list">Scan or upload your MyGate QR to view elections.</p>';
    return;
  }
  voterElectionListElement.innerHTML = '<p class="empty-list">Loading your elections...</p>';
  try {
    voterDashboard = await apiRequest(`/api/voters/${encodeURIComponent(voterSession.user_id)}/dashboard`);
    renderVoterIdentity(voterDashboard.resident);
    renderVoterElections(voterDashboard.elections || []);
  } catch (error) {
    voterElectionListElement.innerHTML = `<p class="empty-list">${escapeHtml(error.message || 'Could not load voter dashboard.')}</p>`;
  }
}

function renderVoterElections(items) {
  if (!items.length) {
    voterElectionListElement.innerHTML = '<p class="empty-list">No active elections are available yet.</p>';
    return;
  }
  voterElectionListElement.innerHTML = items.map(voterElectionHtml).join('');
}

function voterElectionHtml(item) {
  const election = item.election;
  const questions = item.questions || [];
  const houses = item.represented_houses || [];
  const status = election.status;
  const canVote = status === 'voting_open';
  const closed = ['voting_closed', 'results_published', 'archived'].includes(status);
  const votedCount = houses.filter((house) => house.has_voted).length;

  return `
    <article class="voter-election-card">
      <div class="voter-election-head">
        <div>
          <span class="status-pill">${escapeHtml(runStatusLabel(status))}</span>
          <h2>${escapeHtml(election.title)}</h2>
          <p class="muted-copy">${escapeHtml(formatInt(election.represented_villas))} villas represented | ${escapeHtml(formatInt(item.voted_villas))} votes cast</p>
        </div>
        <span class="count-pill">${escapeHtml(votedCount)}/${escapeHtml(houses.length)}</span>
      </div>
      ${election.description ? `<p class="muted-copy">${escapeHtml(election.description)}</p>` : ''}
      <div class="voter-house-list">
        ${houses.length ? houses.map((house) => voterHouseHtml(election, questions, house, canVote, closed)).join('') : '<p class="empty-list">Attendance is not marked yet for a villa you can vote for.</p>'}
      </div>
      ${closed ? `<div class="results-list">${renderResultsList(item.results || [])}</div>` : ''}
    </article>
  `;
}

function voterHouseHtml(election, questions, house, canVote, closed) {
  if (house.has_voted) {
    return `
      <article class="voter-house-card">
        <div>
          <strong>${escapeHtml(house.house_no)}</strong>
          <small>${escapeHtml(house.representation_type === 'proxy' ? 'Proxy vote' : 'Own villa')} | Submitted ${escapeHtml(formatDateTime(house.submitted_at))}</small>
        </div>
        <span class="status-pill">Submitted</span>
      </article>
    `;
  }
  if (!canVote) {
    return `
      <article class="voter-house-card">
        <div>
          <strong>${escapeHtml(house.house_no)}</strong>
          <small>${escapeHtml(closed ? 'Voting is closed' : 'Voting has not opened yet')}</small>
        </div>
      </article>
    `;
  }
  return `
    <form class="voter-ballot-form" data-voter-ballot data-election-id="${escapeHtml(election.id)}" data-house-id="${escapeHtml(house.house_id)}">
      <div class="voter-house-card ballot-head">
        <div>
          <strong>${escapeHtml(house.house_no)}</strong>
          <small>${escapeHtml(house.representation_type === 'proxy' ? 'Proxy vote' : 'Own villa')}</small>
        </div>
        <button class="primary small-button" type="submit">Submit Vote</button>
      </div>
      ${questions.map((question, index) => voterBallotQuestionHtml(question, index, house.house_id)).join('')}
    </form>
  `;
}

function voterBallotQuestionHtml(question, index, houseId) {
  return `
    <fieldset class="voter-ballot-question" data-voter-question-id="${escapeHtml(question.id)}">
      <legend>Question ${index + 1}: ${escapeHtml(question.question_text)}</legend>
      <div class="voter-choice-grid">
        ${(question.choices || []).map((choice) => `
          <label class="voter-choice-option">
            <input type="radio" name="vote-${escapeHtml(houseId)}-${escapeHtml(question.id)}" value="${escapeHtml(choice.id)}" required>
            ${choice.image_url ? `<img src="${escapeHtml(choice.image_url)}" alt="">` : ''}
            <span>${escapeHtml(choice.choice_text)}</span>
          </label>
        `).join('')}
      </div>
    </fieldset>
  `;
}

async function submitVoterBallot(form) {
  if (!voterSession) return;
  const questionBlocks = Array.from(form.querySelectorAll('[data-voter-question-id]'));
  const answers = questionBlocks.map((block) => {
    const selected = block.querySelector('input[type="radio"]:checked');
    return selected ? {
      question_id: block.dataset.voterQuestionId,
      choice_id: selected.value,
    } : null;
  });
  if (answers.some((answer) => !answer)) {
    setVoterStatus('warning', 'Incomplete ballot', 'Answer every question before submitting.');
    return;
  }
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await apiRequest(`/api/elections/${encodeURIComponent(form.dataset.electionId)}/ballots`, {
      method: 'POST',
      body: JSON.stringify({
        submitted_by_user_id: voterSession.user_id,
        house_id: form.dataset.houseId,
        answers,
      }),
    });
    setVoterStatus('success', 'Vote submitted', 'Your vote has been recorded for this villa.');
    await loadVoterDashboard();
    await loadVotingStatus();
  } catch (error) {
    setVoterStatus('error', 'Could not submit vote', error.message || 'Please try again.');
  } finally {
    button.disabled = false;
  }
}

async function toggleVoterScanner() {
  if (voterScanning) {
    await stopVoterScanner();
    return;
  }
  if (!window.Html5Qrcode) {
    setVoterStatus('error', 'Scanner unavailable', 'The QR scanner library did not load. Please refresh and try again.');
    return;
  }
  try {
    setVoterStatus('', 'Opening camera', 'Allow camera access when your browser asks.');
    voterReaderElement.classList.add('active');
    voterHtml5QrCode = new Html5Qrcode('voter-qr-reader');
    await voterHtml5QrCode.start(
      { facingMode: 'environment' },
      { fps: 10, qrbox: getQrBox },
      onVoterScanSuccess,
      () => {}
    );
    voterScanning = true;
    voterScanButton.querySelector('span').textContent = 'Stop Scan';
    setVoterStatus('', 'Scanning', 'Point your camera at the MyGate QR code.');
  } catch (error) {
    voterReaderElement.classList.remove('active');
    setVoterStatus('error', 'Camera blocked', error && error.message ? error.message : 'Could not open the camera.');
  }
}

async function stopVoterScanner() {
  if (!voterHtml5QrCode || !voterScanning) return;
  await voterHtml5QrCode.stop();
  await voterHtml5QrCode.clear();
  voterHtml5QrCode = null;
  voterScanning = false;
  voterReaderElement.classList.remove('active');
  voterScanButton.querySelector('span').textContent = 'Scan QR';
}

async function onVoterScanSuccess(decodedText) {
  await stopVoterScanner();
  loginVoter(decodedText);
}

async function scanVoterFile(file) {
  if (!file) return;
  if (!window.Html5Qrcode) {
    setVoterStatus('error', 'Upload unavailable', 'The QR scanner library did not load. Please refresh and try again.');
    return;
  }
  try {
    setVoterStatus('', 'Reading screenshot', 'Looking for a QR code in the uploaded image.');
    voterReaderElement.classList.add('active');
    const scanner = new Html5Qrcode('voter-qr-reader');
    const decodedText = await scanner.scanFile(file, true);
    await scanner.clear();
    voterReaderElement.classList.remove('active');
    loginVoter(decodedText);
  } catch (error) {
    voterReaderElement.classList.remove('active');
    setVoterStatus('error', 'QR not found', 'Please upload a clear screenshot with the full MyGate QR visible.');
  } finally {
    voterFileInput.value = '';
  }
}

function logoutVoter() {
  voterSession = null;
  voterDashboard = null;
  window.localStorage.removeItem(VOTER_SESSION_KEY);
  voterStatusElement.hidden = true;
  renderVoterIdentity(null);
  voterElectionListElement.innerHTML = '<p class="empty-list">Scan or upload your MyGate QR to view elections.</p>';
}

function renderResultsList(results) {
  if (!results || !results.length) {
    return '<p class="empty-list">No results available yet.</p>';
  }
  return results.map((question, index) => `
    <article class="result-card">
      <div class="question-card-actions">
        <div>
          <span class="question-number">Question ${index + 1}</span>
          <strong>${escapeHtml(question.question_text)}</strong>
        </div>
        <span class="status-pill">${question.passed ? 'Passed' : 'Not Passed'}</span>
      </div>
      <small>${escapeHtml(formatInt(question.total_votes))} votes | Threshold ${escapeHtml(formatPct(question.passing_threshold_percent))}%</small>
      <div class="result-choice-list">
        ${(question.choices || []).map((choice) => {
          const pct = question.total_votes ? (Number(choice.vote_count || 0) / Number(question.total_votes) * 100) : 0;
          return `
            <div class="result-choice">
              <div>
                <strong>${escapeHtml(choice.choice_text)}</strong>
                <small>${escapeHtml(formatInt(choice.vote_count || 0))} votes | ${escapeHtml(formatPct(pct))}%</small>
              </div>
              <div class="progress-track" aria-hidden="true">
                <div class="progress-bar" style="width: ${Math.max(0, Math.min(100, pct))}%"></div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    </article>
  `).join('');
}

function formatInt(value) {
  return Math.round(Number(value || 0)).toLocaleString('en-IN');
}

function formatPct(value) {
  const number = Number(value || 0);
  return Number.isInteger(number) ? String(number) : number.toFixed(1);
}

function syncPassingRuleControl() {
  const isCustom = passingRuleSelect.value === 'custom_threshold';
  passingThresholdInput.hidden = !isCustom;
  passingThresholdInput.disabled = !isCustom;
  passingThresholdInput.required = isCustom;
  if (!isCustom) {
    passingThresholdInput.value = '';
  }
}

function passingRuleLabel(rule, threshold) {
  if (rule === 'two_thirds') return 'Two-thirds';
  if (rule === 'custom_threshold') return `Custom ${formatPct(threshold || 50)}%`;
  return 'Simple majority';
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

function runStatusLabel(value) {
  if (value === 'draft') return 'Not Started';
  if (value === 'attendance_open') return 'Attendance';
  if (value === 'voting_open') return 'Voting';
  if (value === 'voting_closed' || value === 'results_published') return 'Closed';
  return labelize(value);
}

function runStageStatus(value) {
  if (value === 'draft') return 'attendance_open';
  if (value === 'results_published' || value === 'archived') return 'voting_closed';
  return value;
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
  if (tab.dataset.mode) {
    tab.addEventListener('click', () => switchMode(tab.dataset.mode));
  }
});
officerLogoutButton.addEventListener('click', () => logoutOfficer());
scanButton.addEventListener('click', toggleScanner);
fileInput.addEventListener('change', (event) => scanFile(event.target.files[0]));
manualAttendanceForm.addEventListener('submit', submitManualAttendance);
refreshDashboardButton.addEventListener('click', loadDashboard);
refreshVotingStatusButton.addEventListener('click', loadVotingStatus);
restartVotingButton.addEventListener('click', restartVoting);
refreshElectionsButton.addEventListener('click', loadElections);
refreshElectionLibraryButton.addEventListener('click', loadElections);
attendeeSearchInput.addEventListener('input', renderAttendees);
attendeeFilterSelect.addEventListener('change', renderAttendees);
electionForm.addEventListener('submit', saveElection);
passingRuleSelect.addEventListener('change', syncPassingRuleControl);
questionForm.addEventListener('submit', addQuestion);
electionSelect.addEventListener('change', () => loadElectionDetail(electionSelect.value));
stageActionButton.addEventListener('click', advanceElectionStage);
newElectionButton.addEventListener('click', () => openElectionSettings('new'));
editElectionButton.addEventListener('click', () => openElectionSettings('edit'));
closeElectionDialogButton.addEventListener('click', closeElectionSettings);
cancelElectionSettingsButton.addEventListener('click', closeElectionSettings);
electionDialog.addEventListener('close', () => {
  editingNewElection = false;
  if (activeElection) {
    populateElectionForm(activeElection);
  } else {
    renderManageSummary();
  }
});
deleteElectionButton.addEventListener('click', deleteElection);
cancelQuestionEditButton.addEventListener('click', clearQuestionForm);
deleteQuestionButton.addEventListener('click', deleteQuestion);
addChoiceButton.addEventListener('click', addChoiceInput);
manualVillaInput.addEventListener('input', () => {
  renderVillaSuggestions(manualVillaInput, manualVillaResults);
  renderManualOwners();
});
manualVillaResults.addEventListener('click', (event) => {
  const button = event.target.closest('[data-house-no]');
  if (button) {
    selectVillaSuggestion(manualVillaInput, manualVillaResults, button.dataset.houseNo);
  }
});
proxyGrantorVillaInput.addEventListener('input', () => {
  renderVillaSuggestions(proxyGrantorVillaInput, proxyGrantorVillaResults);
});
proxyHolderVillaInput.addEventListener('input', () => {
  renderVillaSuggestions(proxyHolderVillaInput, proxyHolderVillaResults);
  renderProxyHolderOwners();
});
proxyGrantorVillaResults.addEventListener('click', (event) => {
  const button = event.target.closest('[data-house-no]');
  if (button) {
    selectVillaSuggestion(proxyGrantorVillaInput, proxyGrantorVillaResults, button.dataset.houseNo);
  }
});
proxyHolderVillaResults.addEventListener('click', (event) => {
  const button = event.target.closest('[data-house-no]');
  if (button) {
    selectVillaSuggestion(proxyHolderVillaInput, proxyHolderVillaResults, button.dataset.houseNo);
  }
});
defaulterVillaInput.addEventListener('input', () => {
  renderVillaSuggestions(defaulterVillaInput, defaulterVillaResults);
});
defaulterVillaResults.addEventListener('click', (event) => {
  const button = event.target.closest('[data-house-no]');
  if (button) {
    selectVillaSuggestion(defaulterVillaInput, defaulterVillaResults, button.dataset.houseNo);
  }
});
choiceListElement.addEventListener('click', (event) => {
  const removeChoiceButton = event.target.closest('[data-remove-choice]');
  if (removeChoiceButton) {
    removeChoiceInput(Number(removeChoiceButton.dataset.removeChoice));
    return;
  }
  const removeImageButton = event.target.closest('[data-remove-choice-image]');
  if (removeImageButton) {
    removeChoiceImage(Number(removeImageButton.dataset.removeChoiceImage));
  }
});
choiceListElement.addEventListener('change', (event) => {
  const input = event.target.closest('[data-choice-image]');
  if (input) {
    handleChoiceImageChange(input);
  }
});
questionListElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-edit-question]');
  if (button) {
    editQuestion(button.dataset.editQuestion);
  }
});
electionLibraryListElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-election-id]');
  if (button) {
    electionSelect.value = button.dataset.electionId;
    loadElectionDetail(button.dataset.electionId);
  }
});
proxyForm.addEventListener('submit', addProxy);
proxyListElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-delete-proxy]');
  if (button) {
    cancelProxy(button.dataset.deleteProxy);
  }
});
defaulterForm.addEventListener('submit', addDefaulter);
defaulterListElement.addEventListener('click', (event) => {
  const button = event.target.closest('[data-clear-defaulter]');
  if (button) {
    clearDefaulter(button.dataset.clearDefaulter);
  }
});
voterScanButton.addEventListener('click', toggleVoterScanner);
voterFileInput.addEventListener('change', (event) => scanVoterFile(event.target.files[0]));
voterLogoutButton.addEventListener('click', logoutVoter);
refreshVoterDashboardButton.addEventListener('click', loadVoterDashboard);
voterElectionListElement.addEventListener('submit', (event) => {
  const form = event.target.closest('[data-voter-ballot]');
  if (form) {
    event.preventDefault();
    submitVoterBallot(form);
  }
});
initializeApp();
