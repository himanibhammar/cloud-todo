/* ═══════════════════════════════════════════════════════════════════════════
   Cloud To-Do — Frontend Application Logic
   - All API calls use relative URLs so the same code works locally and on EC2
   - No hardcoded localhost references
   ═══════════════════════════════════════════════════════════════════════════ */

'use strict';

// ── API base (relative; works on any host) ──────────────────────────────────
const API = '/api';

// ── State ───────────────────────────────────────────────────────────────────
let allTasks    = [];   // authoritative task list from server
let activeFilter = 'all';
let searchQuery  = '';
let pendingDeleteId = null;   // task ID waiting for modal confirmation
let isBusy       = false;     // prevents double-submissions

// ── DOM refs ────────────────────────────────────────────────────────────────
const addForm        = document.getElementById('add-task-form');
const titleInput     = document.getElementById('task-title');
const descInput      = document.getElementById('task-description');
const titleError     = document.getElementById('title-error');
const addBtn         = document.getElementById('add-btn');
const addBtnText     = addBtn.querySelector('.btn-text');
const addBtnSpinner  = addBtn.querySelector('.btn-spinner');

const taskList       = document.getElementById('task-list');
const loadingBox     = document.getElementById('tasks-loading');
const emptyBox       = document.getElementById('tasks-empty');
const errorBox       = document.getElementById('tasks-error');
const errorMsg       = document.getElementById('tasks-error-msg');
const retryBtn       = document.getElementById('retry-btn');
const searchInput    = document.getElementById('search-input');

const filterTabs     = document.querySelectorAll('.filter-tab');

const countTotal     = document.getElementById('count-total');
const countPending   = document.getElementById('count-pending');
const countCompleted = document.getElementById('count-completed');

const statusDot      = document.getElementById('status-dot');
const statusLabel    = document.getElementById('status-label');

const modal          = document.getElementById('confirm-modal');
const modalCancel    = document.getElementById('modal-cancel');
const modalConfirm   = document.getElementById('modal-confirm');

const toastContainer = document.getElementById('toast-container');

// ═══════════════════════════════════════════════════════════════════════════
// Toast notifications
// ═══════════════════════════════════════════════════════════════════════════
function showToast(message, type = 'info', duration = 3500) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.setAttribute('role', 'status');
  el.innerHTML = `<span aria-hidden="true">${icons[type] ?? ''}</span><span>${escapeHtml(message)}</span>`;
  toastContainer.appendChild(el);

  setTimeout(() => {
    el.classList.add('fade-out');
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }, duration);
}

// ═══════════════════════════════════════════════════════════════════════════
// Health check / API status indicator
// ═══════════════════════════════════════════════════════════════════════════
async function checkHealth() {
  try {
    const res = await fetch(`${API}/health`, { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    if (res.ok && data.status === 'healthy') {
      setStatus('ok', 'API Connected');
    } else {
      setStatus('warn', 'API Degraded');
    }
  } catch {
    setStatus('error', 'API Offline');
  }
}

function setStatus(state, label) {
  statusDot.className = `status-dot ${state}`;
  statusLabel.textContent = label;
}

// ═══════════════════════════════════════════════════════════════════════════
// Data layer — API calls
// ═══════════════════════════════════════════════════════════════════════════
async function fetchTasks() {
  showLoading();
  try {
    const res = await fetch(`${API}/tasks`, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    allTasks = await res.json();
    renderTasks();
  } catch (err) {
    showError(err.message || 'Could not connect to the server.');
  }
}

async function createTask(title, description) {
  const res = await fetch(`${API}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description }),
    signal: AbortSignal.timeout(8000),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to create task');
  return data;
}

async function toggleTask(id, completed) {
  const res = await fetch(`${API}/tasks/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ completed }),
    signal: AbortSignal.timeout(8000),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to update task');
  return data;
}

async function deleteTask(id) {
  const res = await fetch(`${API}/tasks/${id}`, {
    method: 'DELETE',
    signal: AbortSignal.timeout(8000),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Failed to delete task');
  return data;
}

// ═══════════════════════════════════════════════════════════════════════════
// Rendering
// ═══════════════════════════════════════════════════════════════════════════
function getVisibleTasks() {
  let tasks = allTasks;

  // Filter by status
  if (activeFilter === 'pending')   tasks = tasks.filter(t => !t.completed);
  if (activeFilter === 'completed') tasks = tasks.filter(t => t.completed);

  // Filter by search query
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    tasks = tasks.filter(t =>
      t.title.toLowerCase().includes(q) ||
      (t.description || '').toLowerCase().includes(q)
    );
  }
  return tasks;
}

function renderTasks() {
  const visible = getVisibleTasks();

  // Update counters (always from allTasks)
  const total     = allTasks.length;
  const completed = allTasks.filter(t => t.completed).length;
  const pending   = total - completed;
  countTotal.textContent     = total;
  countPending.textContent   = pending;
  countCompleted.textContent = completed;

  // Show/hide states
  loadingBox.classList.add('hidden');
  errorBox.classList.add('hidden');

  if (visible.length === 0) {
    taskList.innerHTML = '';
    emptyBox.classList.remove('hidden');
    return;
  }
  emptyBox.classList.add('hidden');

  taskList.innerHTML = visible.map(taskCard).join('');
  attachTaskListeners();
}

function taskCard(task) {
  const date = formatDate(task.created_at);
  const badgeClass = task.completed ? 'badge-completed' : 'badge-pending';
  const badgeText  = task.completed ? 'Done' : 'Pending';
  const checked    = task.completed ? 'checked' : '';
  const descHtml   = task.description
    ? `<p class="task-desc">${escapeHtml(task.description)}</p>`
    : '';

  return `
    <li class="task-item${task.completed ? ' completed' : ''}" data-id="${task.id}">
      <div class="task-checkbox-wrapper">
        <input
          type="checkbox"
          class="task-checkbox"
          id="chk-${task.id}"
          aria-label="${task.completed ? 'Mark as pending' : 'Mark as completed'}"
          data-id="${task.id}"
          ${checked}
        />
      </div>
      <div class="task-body">
        <p class="task-title">${escapeHtml(task.title)}</p>
        ${descHtml}
        <p class="task-meta">
          Added ${date}
          <span class="task-badge ${badgeClass}">${badgeText}</span>
        </p>
      </div>
      <button
        class="task-delete-btn"
        aria-label="Delete task: ${escapeHtml(task.title)}"
        data-id="${task.id}"
        title="Delete task"
      >🗑️</button>
    </li>`;
}

function attachTaskListeners() {
  // Checkbox — toggle completion
  taskList.querySelectorAll('.task-checkbox').forEach(chk => {
    chk.addEventListener('change', async e => {
      const id = parseInt(e.target.dataset.id, 10);
      const completed = e.target.checked;
      disableCheckbox(id, true);
      try {
        const updated = await toggleTask(id, completed);
        const idx = allTasks.findIndex(t => t.id === id);
        if (idx !== -1) allTasks[idx] = updated;
        renderTasks();
        showToast(completed ? 'Task completed! 🎉' : 'Task reopened.', 'success');
      } catch (err) {
        showToast(err.message, 'error');
        e.target.checked = !completed; // revert
        disableCheckbox(id, false);
      }
    });
  });

  // Delete buttons
  taskList.querySelectorAll('.task-delete-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      pendingDeleteId = parseInt(e.currentTarget.dataset.id, 10);
      openModal();
    });
  });
}

function disableCheckbox(id, disabled) {
  const chk = taskList.querySelector(`#chk-${id}`);
  if (chk) chk.disabled = disabled;
}

// ═══════════════════════════════════════════════════════════════════════════
// UI state helpers
// ═══════════════════════════════════════════════════════════════════════════
function showLoading() {
  loadingBox.classList.remove('hidden');
  emptyBox.classList.add('hidden');
  errorBox.classList.add('hidden');
  taskList.innerHTML = '';
  countTotal.textContent = countPending.textContent = countCompleted.textContent = '—';
}

function showError(message) {
  loadingBox.classList.add('hidden');
  emptyBox.classList.add('hidden');
  errorBox.classList.remove('hidden');
  errorMsg.textContent = message || 'Could not connect to the server.';
}

function setAddBtnBusy(busy) {
  isBusy = busy;
  addBtn.disabled = busy;
  addBtnText.textContent = busy ? 'Adding…' : 'Add Task';
  addBtnSpinner.classList.toggle('hidden', !busy);
}

// ═══════════════════════════════════════════════════════════════════════════
// Form handling
// ═══════════════════════════════════════════════════════════════════════════
addForm.addEventListener('submit', async e => {
  e.preventDefault();
  if (isBusy) return;

  const title = titleInput.value.trim();
  const description = descInput.value.trim();

  // Client-side validation
  titleError.textContent = '';
  titleInput.classList.remove('error');

  if (!title) {
    titleError.textContent = 'Please enter a task title.';
    titleInput.classList.add('error');
    titleInput.focus();
    return;
  }

  setAddBtnBusy(true);
  try {
    const newTask = await createTask(title, description);
    allTasks.unshift(newTask);   // prepend (newest first)
    titleInput.value = '';
    descInput.value  = '';
    titleInput.focus();
    renderTasks();
    showToast('Task added successfully!', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    setAddBtnBusy(false);
  }
});

// Clear validation on typing
titleInput.addEventListener('input', () => {
  titleError.textContent = '';
  titleInput.classList.remove('error');
});

// ═══════════════════════════════════════════════════════════════════════════
// Search & filter
// ═══════════════════════════════════════════════════════════════════════════
searchInput.addEventListener('input', e => {
  searchQuery = e.target.value.trim();
  renderTasks();
});

filterTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    filterTabs.forEach(t => { t.classList.remove('active'); t.setAttribute('aria-selected', 'false'); });
    tab.classList.add('active');
    tab.setAttribute('aria-selected', 'true');
    activeFilter = tab.dataset.filter;
    renderTasks();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// Delete modal
// ═══════════════════════════════════════════════════════════════════════════
function openModal() {
  modal.classList.remove('hidden');
  modalConfirm.focus();
}

function closeModal() {
  modal.classList.add('hidden');
  pendingDeleteId = null;
}

modalCancel.addEventListener('click', closeModal);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !modal.classList.contains('hidden')) closeModal();
});

modalConfirm.addEventListener('click', async () => {
  if (!pendingDeleteId) return;
  const id = pendingDeleteId;
  closeModal();

  try {
    await deleteTask(id);
    allTasks = allTasks.filter(t => t.id !== id);
    renderTasks();
    showToast('Task deleted.', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// Retry button
// ═══════════════════════════════════════════════════════════════════════════
retryBtn.addEventListener('click', fetchTasks);

// ═══════════════════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════════════════
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatDate(isoString) {
  if (!isoString) return '';
  try {
    return new Date(isoString).toLocaleString(undefined, {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// Initialisation
// ═══════════════════════════════════════════════════════════════════════════
(async function init() {
  await checkHealth();
  await fetchTasks();
  // Re-check health every 60 seconds
  setInterval(checkHealth, 60_000);
})();
