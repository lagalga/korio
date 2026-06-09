'use strict'

// ─── Configuración ───────────────────────────────────────────────────────────

// En desarrollo (localhost) apunta al puerto 8000; en producción usa la misma origin
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : ''

const TENANTS = {
  delos: {
    id: 'a0000000-0000-0000-0000-000000000001',
    name: 'Clínica Delos',
    users: [
      { id: 'a1000000-0000-0000-0000-000000000001', role: 'Admin',  spaces: 'RRHH · Médico · Legal' },
      { id: 'a2000000-0000-0000-0000-000000000001', role: 'Doctor', spaces: 'RRHH · Médico' },
      { id: 'a3000000-0000-0000-0000-000000000001', role: 'Staff',  spaces: 'RRHH' },
    ],
    spaces: [
      { id: 'a1000000-0000-0000-0000-000000000001', name: 'RRHH' },
      { id: 'a1000000-0000-0000-0000-000000000002', name: 'Médico' },
      { id: 'a1000000-0000-0000-0000-000000000003', name: 'Legal' },
    ],
    suggestions: [
      '¿Cuántos días de vacaciones tienen los empleados?',
      '¿Cuál es el protocolo de admisión de pacientes?',
      '¿Qué se trató en la última junta directiva?',
    ],
  },
  garcia: {
    id: 'b0000000-0000-0000-0000-000000000002',
    name: 'Despacho García',
    users: [
      { id: 'b1000000-0000-0000-0000-000000000002', role: 'Admin',  spaces: 'Casos · Fiscal' },
      { id: 'b2000000-0000-0000-0000-000000000002', role: 'Lawyer', spaces: 'Casos' },
    ],
    spaces: [
      { id: 'b1000000-0000-0000-0000-000000000001', name: 'Casos' },
      { id: 'b1000000-0000-0000-0000-000000000002', name: 'Fiscal' },
    ],
    suggestions: [
      '¿Cuál es el estado del caso laboral?',
      '¿Qué dice el dictamen fiscal?',
      '¿Cuál es el protocolo para nuevos clientes?',
    ],
  },
}

// ─── Estado ──────────────────────────────────────────────────────────────────

const state = {
  tenantKey: 'delos',
  userIndex: 0,
  history: [],
  selectedFile: null,
}

// ─── DOM refs ─────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id)

const tenantSelect   = $('tenant-select')
const userSelect     = $('user-select')
const userBadge      = $('user-badge')
const chat           = $('chat')
const chatEmpty      = $('chat-empty')
const suggestions    = $('suggestions')
const historyList    = $('history-list')
const historyCount   = $('history-count')
const queryInput     = $('query-input')
const sendBtn        = $('send-btn')
const clearBtn       = $('clear-btn')
const ingestBtn      = $('ingest-btn')
const apiStatus      = $('api-status')
const apiStatusText  = $('api-status-text')

const modalOverlay   = $('modal-overlay')
const modalClose     = $('modal-close')
const modalCancel    = $('modal-cancel')
const dropZone       = $('drop-zone')
const fileInput      = $('file-input')
const ingestFileInfo = $('ingest-file-info')
const ingestFilename = $('ingest-filename')
const ingestFileClear = $('ingest-file-clear')
const ingestSpace    = $('ingest-space')
const ingestSubmit   = $('ingest-submit')
const modalProgress  = $('modal-progress')
const modalProgressText = $('modal-progress-text')

// ─── Helpers ──────────────────────────────────────────────────────────────────

const currentTenant = () => TENANTS[state.tenantKey]
const currentUser   = () => currentTenant().users[state.userIndex]

const simClass = sim => sim >= 0.75 ? 'high' : sim >= 0.55 ? 'mid' : 'low'

const formatMs = ms => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`

const truncate = (str, n) => str?.length > n ? str.slice(0, n) + '…' : (str || '')

// ─── UI: Selectores ──────────────────────────────────────────────────────────

const renderUserSelect = () => {
  const tenant = currentTenant()
  userSelect.innerHTML = tenant.users.map((u, i) =>
    `<option value="${i}">${u.role}</option>`
  ).join('')
  userSelect.value = state.userIndex
  renderUserBadge()
}

const renderUserBadge = () => {
  const u = currentUser()
  userBadge.innerHTML = `<strong>${u.role}</strong>${u.spaces}`
}

const renderSuggestions = () => {
  suggestions.innerHTML = currentTenant().suggestions.map(s =>
    `<button class="suggestion-chip" data-query="${s}">${s}</button>`
  ).join('')
}

const renderIngestSpaces = () => {
  const spaces = currentTenant().spaces
  ingestSpace.innerHTML = spaces.map(s =>
    `<option value="${s.id}">${s.name}</option>`
  ).join('')
}

// ─── UI: Historial ────────────────────────────────────────────────────────────

const addToHistory = query => {
  state.history.unshift(query)
  if (state.history.length > 20) state.history.pop()
  renderHistory()
}

const renderHistory = () => {
  historyCount.textContent = `${state.history.length} quer${state.history.length === 1 ? 'y' : 'ies'}`
  historyList.innerHTML = state.history.map(q =>
    `<li class="history-list__item" title="${q}">${truncate(q, 42)}</li>`
  ).join('')
  historyList.querySelectorAll('li').forEach((li, i) => {
    li.addEventListener('click', () => {
      queryInput.value = state.history[i]
      queryInput.dispatchEvent(new Event('input'))
      queryInput.focus()
    })
  })
}

// ─── UI: Chat ─────────────────────────────────────────────────────────────────

const showEmpty = show => { chatEmpty.hidden = !show }

const appendLoading = () => {
  const el = document.createElement('div')
  el.className = 'message-pair'
  el.id = 'loading-msg'
  el.innerHTML = `
    <div class="message-response message-response--loading">
      <div class="message-response__card">
        <div class="spinner"></div>
        Consultando documentos…
      </div>
    </div>`
  chat.appendChild(el)
  el.scrollIntoView({ behavior: 'smooth', block: 'end' })
  return el
}

const removeLoading = () => $('loading-msg')?.remove()

const renderMessage = (query, result) => {
  const sources = result.sources || []
  const sourcesHtml = sources.length ? `
    <div class="sources">
      <button class="sources__toggle" aria-expanded="false">
        <span class="sources__toggle-icon">▶</span>
        ${sources.length} fuente${sources.length > 1 ? 's' : ''}
      </button>
      <div class="sources__list" hidden>
        ${sources.map(s => {
          const label = s.filename || s.document_id.slice(0, 16) + '…'
          const sim   = s.similarity
          const cls   = simClass(sim)
          return `<div class="source-chip">
            <span class="source-chip__filename" title="${s.filename || s.document_id}">${label}</span>
            <span class="source-chip__sim source-chip__sim--${cls}">${Math.round(sim * 100)}%</span>
          </div>`
        }).join('')}
      </div>
    </div>` : ''

  const answerHtml = result.has_context
    ? `<p class="message-response__answer">${renderMarkdown(result.answer)}</p>`
    : `<p class="message-response__answer message-response__no-context">No encontré documentos relevantes para esta pregunta.</p>`

  const pair = document.createElement('div')
  pair.className = 'message-pair'
  pair.innerHTML = `
    <div class="message-query">${escapeHtml(query)}</div>
    <div class="message-response">
      <div class="message-response__card">
        ${answerHtml}
        <div class="message-response__meta">
          <span class="meta-badge meta-badge--latency">⏱ ${formatMs(result.latency_ms)}</span>
          <span class="meta-badge">${result.model_used}</span>
          <span class="meta-badge">${result.chunks_used} chunks</span>
        </div>
      </div>
      ${sourcesHtml}
    </div>`

  chat.appendChild(pair)
  pair.scrollIntoView({ behavior: 'smooth', block: 'end' })

  // Toggle sources
  const toggle = pair.querySelector('.sources__toggle')
  const list   = pair.querySelector('.sources__list')
  const icon   = pair.querySelector('.sources__toggle-icon')
  if (toggle) {
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') === 'true'
      toggle.setAttribute('aria-expanded', String(!open))
      list.hidden = open
      icon.classList.toggle('sources__toggle-icon--open', !open)
    })
  }
}

const escapeHtml = str => str
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')

const renderMarkdown = str => escapeHtml(str)
  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')
  .replace(/`([^`]+?)`/g, '<code>$1</code>')
  .replace(/\n/g, '<br>')

// ─── API calls ────────────────────────────────────────────────────────────────

const checkHealth = async () => {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(5000) })
    const data = await res.json()
    const ok = data.status === 'ok'
    apiStatus.className = `status-dot status-dot--${ok ? 'ok' : 'error'}`
    apiStatusText.textContent = ok
      ? `API conectada · ${data.services?.llm || ''}`
      : `API degradada: ${JSON.stringify(data.services)}`
  } catch {
    apiStatus.className = 'status-dot status-dot--error'
    apiStatusText.textContent = 'API no disponible — ¿está corriendo el servidor?'
  }
}

const doSearch = async (query) => {
  const user   = currentUser()
  const tenant = currentTenant()

  const res = await fetch(`${API_BASE}/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      user_id: user.id,
      tenant_id: tenant.id,
    }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `Error ${res.status}`)
  }

  return res.json()
}

const doUpload = async (file, tenantId, spaceId) => {
  const form = new FormData()
  form.append('file', file)
  form.append('tenant_id', tenantId)
  form.append('space_id', spaceId)

  const res = await fetch(`${API_BASE}/upload`, { method: 'POST', body: form })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    const e = new Error(err.detail || `Error ${res.status}`)
    e.status = res.status
    throw e
  }

  return res.json()
}

// ─── Acción: enviar query ─────────────────────────────────────────────────────

const sendQuery = async () => {
  const query = queryInput.value.trim()
  if (!query) return

  showEmpty(false)
  queryInput.value = ''
  queryInput.style.height = 'auto'
  sendBtn.disabled = true

  addToHistory(query)
  const loadingEl = appendLoading()

  try {
    const result = await doSearch(query)
    removeLoading()
    renderMessage(query, result)
  } catch (err) {
    removeLoading()
    const pair = document.createElement('div')
    pair.className = 'message-pair'
    pair.innerHTML = `
      <div class="message-query">${escapeHtml(query)}</div>
      <div class="message-response">
        <div class="message-response__card">
          <p class="message-response__answer message-response__no-context">Error: ${escapeHtml(err.message)}</p>
        </div>
      </div>`
    chat.appendChild(pair)
    pair.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }

  queryInput.disabled = false
  updateSendBtn()
  queryInput.focus()
}

// ─── Acción: clear session ────────────────────────────────────────────────────

const clearSession = () => {
  state.history = []
  renderHistory()
  chat.innerHTML = ''
  chat.appendChild(chatEmpty)
  chatEmpty.hidden = false
  queryInput.value = ''
  updateSendBtn()
}

// ─── Modal de ingesta ─────────────────────────────────────────────────────────

const openModal = () => {
  renderIngestSpaces()
  state.selectedFile = null
  ingestFileInfo.hidden = true
  dropZone.hidden = false
  ingestSubmit.disabled = true
  modalProgress.hidden = true
  modalOverlay.hidden = false
}

const closeModal = () => { modalOverlay.hidden = true }

const setFile = file => {
  state.selectedFile = file
  ingestFilename.textContent = file.name
  ingestFileInfo.hidden = false
  dropZone.hidden = true
  ingestSubmit.disabled = false
}

const renderConflictReport = (cr) => {
  if (!cr || !cr.has_conflicts) return ''

  const resolutionLabel = r => ({
    'auto_new_wins':      '⚡ Nuevo prevalece (auto)',
    'auto_existing_wins': '⚡ Existente prevalece (auto)',
    'pending':            '⏳ Pendiente revisión humana',
    'approved_new':       '✅ Aprobado: nuevo',
    'approved_existing':  '✅ Aprobado: existente',
    'kept_both':          '✅ Conservados ambos',
  })[r] || r

  const conflictRows = cr.conflicts.map(c => `
    <div class="conflict-item conflict-item--${c.resolution.startsWith('auto') ? 'auto' : c.resolution === 'pending' ? 'pending' : 'resolved'}">
      <span class="conflict-item__file" title="${c.existing_document_id}">${c.existing_filename}</span>
      <span class="conflict-item__sim">${Math.round(c.similarity * 100)}% similitud</span>
      <span class="conflict-item__resolution">${resolutionLabel(c.resolution)}</span>
    </div>`).join('')

  return `
    <div class="conflict-report">
      <div class="conflict-report__header">
        <span class="conflict-report__icon">${cr.pending_review > 0 ? '⚠️' : '⚡'}</span>
        <strong>Gobernanza activa:</strong>
        ${cr.total_conflicts} conflicto${cr.total_conflicts > 1 ? 's' : ''} detectado${cr.total_conflicts > 1 ? 's' : ''}
        &nbsp;·&nbsp; ${cr.auto_resolved} auto-resuelto${cr.auto_resolved !== 1 ? 's' : ''}
        ${cr.pending_review > 0 ? `&nbsp;·&nbsp; <em>${cr.pending_review} pendiente${cr.pending_review > 1 ? 's' : ''} (email enviado)</em>` : ''}
      </div>
      <div class="conflict-report__list">${conflictRows}</div>
    </div>`
}

const submitIngest = async () => {
  if (!state.selectedFile) return

  ingestSubmit.disabled = true
  modalProgress.hidden = false
  modalProgressText.textContent = 'Procesando documento…'

  try {
    const result = await doUpload(
      state.selectedFile,
      currentTenant().id,
      ingestSpace.value
    )

    const conflictHtml = renderConflictReport(result.conflict_report)
    modalProgressText.innerHTML =
      `✅ <strong>${result.filename}</strong> — ${result.chunks_created} chunks creados` +
      (result.pii_found > 0 ? ` · ${result.pii_found} PII anonimizados` : '') +
      conflictHtml

    // Si hay conflictos pendientes, dejamos el modal abierto más tiempo
    const delay = (result.conflict_report?.pending_review > 0) ? 6000 : 2500
    setTimeout(closeModal, delay)
  } catch (err) {
    if (err.status === 409) {
      // Duplicado — no es realmente un error, informamos sin alarma
      modalProgressText.innerHTML = `ℹ️ <strong>Documento ya ingestado.</strong> ${err.message}`
    } else {
      modalProgressText.textContent = `❌ Error: ${err.message}`
    }
    ingestSubmit.disabled = false
  }
}

// ─── Event listeners ──────────────────────────────────────────────────────────

const updateSendBtn = () => {
  sendBtn.disabled = queryInput.value.trim().length === 0
}

tenantSelect.addEventListener('change', () => {
  state.tenantKey = tenantSelect.value
  state.userIndex = 0
  renderUserSelect()
  renderSuggestions()
  renderIngestSpaces()
})

userSelect.addEventListener('change', () => {
  state.userIndex = parseInt(userSelect.value, 10)
  renderUserBadge()
})

queryInput.addEventListener('input', () => {
  // Auto-resize
  queryInput.style.height = 'auto'
  queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + 'px'
  updateSendBtn()
})

queryInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendBtn.click() }
})

sendBtn.addEventListener('click', sendQuery)
clearBtn.addEventListener('click', clearSession)
ingestBtn.addEventListener('click', openModal)

suggestions.addEventListener('click', e => {
  const chip = e.target.closest('.suggestion-chip')
  if (!chip) return
  queryInput.value = chip.dataset.query
  queryInput.dispatchEvent(new Event('input'))
  sendQuery()
})

// Modal
modalClose.addEventListener('click', closeModal)
modalCancel.addEventListener('click', closeModal)
modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal() })
ingestSubmit.addEventListener('click', submitIngest)
ingestFileClear.addEventListener('click', () => {
  state.selectedFile = null
  fileInput.value = ''
  ingestFileInfo.hidden = true
  dropZone.hidden = false
  ingestSubmit.disabled = true
})

// File input / drag & drop
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) setFile(fileInput.files[0])
})

dropZone.addEventListener('click', () => fileInput.click())

dropZone.addEventListener('dragover', e => {
  e.preventDefault()
  dropZone.classList.add('drop-zone--active')
})

dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drop-zone--active'))

dropZone.addEventListener('drop', e => {
  e.preventDefault()
  dropZone.classList.remove('drop-zone--active')
  const file = e.dataTransfer.files[0]
  if (file) setFile(file)
})

// ─── Init ─────────────────────────────────────────────────────────────────────

renderUserSelect()
renderSuggestions()
renderIngestSpaces()
checkHealth()
setInterval(checkHealth, 30_000)
