"use strict";

const API_BASE_URL = "http://127.0.0.1:8000/api";
const REFRESH_INTERVAL_MS = 30_000;
const STATUS_LABELS = {
  PENDING: "Pendiente",
  SUCCESS: "Exitosa",
  FAILED: "Fallida",
  CANCELLED: "Cancelada",
};
const SOURCE_LABELS = {
  format_1: "Formato 1",
  format_2: "Formato 2",
  format_3: "Formato 3",
  unknown: "Desconocida",
};

const state = {
  transactions: [],
  visibleTransactions: [],
  invalidOnly: false,
  selectedFiles: [],
  loading: false,
  searchRequest: 0,
  refreshTimer: null,
};

const elements = {
  connectionStatus: document.querySelector("#connection-status"),
  connectionLabel: document.querySelector("#connection-label"),
  metricProcessed: document.querySelector("#metric-processed"),
  metricValid: document.querySelector("#metric-valid"),
  metricInvalid: document.querySelector("#metric-invalid"),
  metricDuplicates: document.querySelector("#metric-duplicates"),
  metricValidityRate: document.querySelector("#metric-validity-rate"),
  navCount: document.querySelector("#nav-transaction-count"),
  currencyTotals: document.querySelector("#currency-totals"),
  statusCounts: document.querySelector("#status-counts"),
  globalAlert: document.querySelector("#global-alert"),
  globalAlertMessage: document.querySelector("#global-alert-message"),
  fileInput: document.querySelector("#file-input"),
  dropzone: document.querySelector("#dropzone"),
  selectedFiles: document.querySelector("#selected-files"),
  uploadForm: document.querySelector("#upload-form"),
  uploadButton: document.querySelector("#upload-button"),
  uploadButtonLabel: document.querySelector(".upload-button-label"),
  uploadResults: document.querySelector("#upload-results"),
  transactionRows: document.querySelector("#transaction-rows"),
  tableCount: document.querySelector("#table-count"),
  tableSummary: document.querySelector("#table-summary"),
  searchInput: document.querySelector("#search-input"),
  sourceFilter: document.querySelector("#source-filter"),
  statusFilter: document.querySelector("#status-filter"),
  currencyFilter: document.querySelector("#currency-filter"),
  resetFilters: document.querySelector("#reset-filters"),
  clearButton: document.querySelector("#clear-button"),
  refreshButton: document.querySelector("#refresh-button"),
  detailDialog: document.querySelector("#detail-dialog"),
  detailContent: document.querySelector("#detail-content"),
  detailClose: document.querySelector("#detail-close"),
  toastRegion: document.querySelector("#toast-region"),
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function formatNumber(value) {
  return new Intl.NumberFormat("es-GT", { maximumFractionDigits: 2 }).format(
    Number(value) || 0,
  );
}

function formatAmount(value, currency) {
  if (value === null || value === undefined || currency === null) {
    return '<span class="amount-cell">—</span>';
  }
  return `<span class="amount-cell">${escapeHtml(value)}<span class="currency-suffix">${escapeHtml(currency)}</span></span>`;
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-GT", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date);
}

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function setConnectionStatus(status, label) {
  elements.connectionStatus.classList.toggle("is-offline", status === "offline");
  elements.connectionStatus.classList.toggle("is-checking", status === "checking");
  elements.connectionLabel.textContent = label;
}

function showAlert(message) {
  elements.globalAlertMessage.textContent = message;
  elements.globalAlert.hidden = false;
}

function hideAlert() {
  elements.globalAlert.hidden = true;
}

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  elements.toastRegion.append(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch (error) {
    throw new Error("No se pudo conectar con la API. Comprueba que el backend esté en ejecución.");
  }

  const responseText = await response.text();
  let payload = null;
  if (responseText) {
    try {
      payload = JSON.parse(responseText);
    } catch (error) {
      throw new Error("La API devolvió una respuesta que no es JSON válido.");
    }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item.msg).join("; ")
        : `Error HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

async function checkHealth() {
  setConnectionStatus("checking", "Conectando API");
  try {
    await requestJson("/health");
    setConnectionStatus("online", "API conectada");
    hideAlert();
    return true;
  } catch (error) {
    setConnectionStatus("offline", "API desconectada");
    showAlert(`${error.message} Inicia el backend y vuelve a intentar.`);
    return false;
  }
}

async function refreshDashboard({ silent = false } = {}) {
  setConnectionStatus("checking", "Actualizando");
  try {
    const [metrics, transactions] = await Promise.all([
      requestJson("/metrics"),
      requestJson("/transactions"),
    ]);
    state.transactions = Array.isArray(transactions) ? transactions : [];
    renderMetrics(metrics);
    renderTransactions(state.transactions);
    setConnectionStatus("online", "API conectada");
    hideAlert();
    return true;
  } catch (error) {
    setConnectionStatus("offline", "API desconectada");
    if (!silent) {
      showAlert(error.message);
    }
    return false;
  }
}

function renderMetrics(metrics) {
  elements.metricProcessed.textContent = formatNumber(metrics.total_processed);
  elements.metricValid.textContent = formatNumber(metrics.total_valid);
  elements.metricInvalid.textContent = formatNumber(metrics.total_invalid);
  elements.metricDuplicates.textContent = formatNumber(metrics.total_duplicates);
  const validityRate = Number(metrics.validity_percentage) || 0;
  elements.metricValidityRate.textContent = `${formatNumber(validityRate)}%`;
  elements.navCount.textContent = formatNumber(metrics.total_processed);
  elements.clearButton.disabled = Number(metrics.total_processed) === 0;

  renderCurrencyTotals(metrics.totals_by_currency || {});
  renderStatusCounts(metrics.count_by_status || {});
}

function renderCurrencyTotals(totals) {
  const entries = Object.entries(totals);
  if (!entries.length) {
    elements.currencyTotals.innerHTML = '<div class="empty-note">Aún no hay totales financieros.</div>';
    return;
  }
  const maxAmount = Math.max(...entries.map(([, amount]) => Number(amount) || 0), 0);
  elements.currencyTotals.innerHTML = entries.map(([currency, amount]) => {
    const ratio = maxAmount > 0 ? Math.max((Number(amount) / maxAmount) * 100, 2) : 0;
    return `<div class="currency-row">
      <span class="currency-code">${escapeHtml(currency)}</span>
      <span class="currency-track"><span class="currency-progress" style="width:${ratio}%"></span></span>
      <strong class="currency-total">${escapeHtml(amount)}</strong>
    </div>`;
  }).join("");
}

function renderStatusCounts(counts) {
  const statusOrder = ["PENDING", "SUCCESS", "FAILED", "CANCELLED"];
  const statusClasses = {
    PENDING: "state-pending",
    SUCCESS: "state-success",
    FAILED: "state-failed",
    CANCELLED: "state-cancelled",
  };
  elements.statusCounts.innerHTML = statusOrder.map((status) => `
    <div class="state-item">
      <span class="state-dot ${statusClasses[status]}"></span>
      <span>${STATUS_LABELS[status]}</span>
      <strong>${formatNumber(counts[status] || 0)}</strong>
    </div>
  `).join("");
}

function getStatusClass(status) {
  return {
    SUCCESS: "status-success",
    PENDING: "status-pending",
    FAILED: "status-failed",
    CANCELLED: "status-cancelled",
  }[status] || "status-unknown";
}

function renderTransactionRow(transaction, index) {
  const source = transaction.source || "unknown";
  const status = transaction.status;
  const validBadge = transaction.is_valid
    ? '<span class="validity-badge is-valid">Válida</span>'
    : '<span class="validity-badge is-invalid">Inválida</span>';
  const duplicateBadge = transaction.is_duplicate
    ? '<span class="duplicate-badge">Duplicada</span>'
    : "";
  const statusLabel = STATUS_LABELS[status] || "Sin estado";
  const rowClasses = [
    transaction.is_valid ? "" : "row-invalid",
    transaction.is_duplicate ? "row-duplicate" : "",
  ].filter(Boolean).join(" ");

  return `<tr class="${rowClasses}">
    <td><span class="transaction-id"><span class="transaction-id-code" title="${escapeHtml(transaction.transaction_id ?? "Sin identificador")}">${escapeHtml(transaction.transaction_id ?? "—")}</span></span></td>
    <td><span class="source-badge source-${escapeHtml(source)}">${escapeHtml(SOURCE_LABELS[source] || source)}</span></td>
    <td>${formatAmount(transaction.amount, transaction.currency)}</td>
    <td class="date-cell" title="${escapeHtml(transaction.timestamp || "")}">${escapeHtml(formatDate(transaction.timestamp))}</td>
    <td><span class="status-badge ${getStatusClass(status)}">${escapeHtml(statusLabel)}</span></td>
    <td>${validBadge}${duplicateBadge}</td>
    <td><button class="detail-button" type="button" data-detail-index="${index}" aria-label="Ver detalle de ${escapeHtml(transaction.transaction_id ?? "registro")}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4M11 8v.1M11 11v3"/></svg></button></td>
  </tr>`;
}

function renderTransactions(transactions) {
  const sourceFilter = elements.sourceFilter.value;
  const statusFilter = elements.statusFilter.value;
  const currencyFilter = elements.currencyFilter.value;
  const query = elements.searchInput.value.trim().toLocaleLowerCase();
  const filtered = transactions.filter((transaction) => {
    const identifier = String(transaction.transaction_id ?? "").toLocaleLowerCase();
    return (!state.invalidOnly || !transaction.is_valid)
      && (!sourceFilter || transaction.source === sourceFilter)
      && (!statusFilter || transaction.status === statusFilter)
      && (!currencyFilter || transaction.currency === currencyFilter)
      && (!query || identifier.includes(query));
  });
  state.visibleTransactions = filtered;
  elements.tableCount.textContent = `${formatNumber(filtered.length)} ${filtered.length === 1 ? "registro" : "registros"}`;
  const visibleLabel = `${formatNumber(filtered.length)} ${filtered.length === 1 ? "registro" : "registros"}`;
  elements.tableSummary.textContent = filtered.length === transactions.length
    ? `${visibleLabel} en memoria`
    : `${visibleLabel} de ${formatNumber(transactions.length)} registros`;

  if (!filtered.length) {
    const hasFilters = sourceFilter || statusFilter || currencyFilter || query;
    elements.transactionRows.innerHTML = `<tr><td class="table-message" colspan="7">${hasFilters ? "No hay registros que coincidan con los filtros." : "Aún no hay transacciones. Importa un archivo JSON para comenzar."}</td></tr>`;
    return;
  }
  elements.transactionRows.innerHTML = filtered.map(renderTransactionRow).join("");
}

function renderSelectedFiles() {
  elements.selectedFiles.hidden = state.selectedFiles.length === 0;
  elements.uploadButton.disabled = state.selectedFiles.length === 0 || state.loading;
  if (!state.selectedFiles.length) {
    elements.selectedFiles.replaceChildren();
    return;
  }
  elements.selectedFiles.innerHTML = state.selectedFiles.map((file, index) => `
    <div class="selected-file">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9l-5.5-5.5Z"/><path d="M13 4v5h5"/></svg>
      <span>${escapeHtml(file.name)}</span>
      <span class="selected-file-size">${formatBytes(file.size)}</span>
      <button class="selected-file-remove" type="button" data-remove-file="${index}" aria-label="Quitar ${escapeHtml(file.name)}">×</button>
    </div>
  `).join("");
}

function setSelectedFiles(files) {
  const validFiles = [];
  const rejectedFiles = [];
  for (const file of files) {
    if (!file.name.toLocaleLowerCase().endsWith(".json")) {
      rejectedFiles.push(file.name);
    } else {
      validFiles.push(file);
    }
  }
  state.selectedFiles = [...state.selectedFiles, ...validFiles];
  renderSelectedFiles();
  if (rejectedFiles.length) {
    showToast(`Solo se aceptan archivos .json: ${rejectedFiles.join(", ")}`, "error");
  }
}

async function processSelectedFiles(event) {
  event.preventDefault();
  if (state.loading || !state.selectedFiles.length) {
    return;
  }
  state.loading = true;
  elements.uploadButton.classList.add("is-loading");
  elements.uploadButton.disabled = true;
  elements.uploadButtonLabel.textContent = "Procesando…";
  elements.uploadResults.hidden = true;
  elements.uploadResults.classList.remove("has-errors");

  const results = [];
  for (const file of state.selectedFiles) {
    try {
      const contents = await file.text();
      JSON.parse(contents);
      const result = await requestJson("/transactions/upload", {
        method: "POST",
        body: contents,
      });
      results.push({
        file: file.name,
        success: true,
        received: result.received,
        added: result.added,
        total: result.total_processed,
      });
    } catch (error) {
      results.push({ file: file.name, success: false, message: error.message });
    }
  }

  state.loading = false;
  elements.uploadButton.classList.remove("is-loading");
  elements.uploadButtonLabel.textContent = "Procesar archivos";
  state.selectedFiles = [];
  renderSelectedFiles();
  const successful = results.filter((result) => result.success);
  const failed = results.filter((result) => !result.success);
  elements.uploadResults.hidden = false;
  elements.uploadResults.classList.toggle("has-errors", failed.length > 0);
  const summary = successful.map((result) =>
    `${result.file}: ${result.received} recibidas, ${result.added} procesadas`,
  );
  const failures = failed.map((result) => `${result.file}: ${result.message}`);
  elements.uploadResults.textContent = [...summary, ...failures].join(" · ");

  if (successful.length) {
    const fileLabel = successful.length === 1 ? "archivo procesado" : "archivos procesados";
    showToast(`Carga completada: ${successful.length} ${fileLabel}.`);
    await refreshDashboard({ silent: true });
  }
  if (failed.length) {
    showToast(`${failed.length} archivo(s) no pudieron procesarse.`, "error");
  }
}

async function runIdentifierSearch() {
  const requestId = ++state.searchRequest;
  const query = elements.searchInput.value.trim();
  if (!query) {
    renderTransactions(state.transactions);
    return;
  }
  try {
    const matches = await requestJson(`/transactions/search?transaction_id=${encodeURIComponent(query)}`);
    if (requestId !== state.searchRequest) {
      return;
    }
    renderTransactions(matches);
  } catch (error) {
    if (requestId === state.searchRequest) {
      showToast(error.message, "error");
    }
  }
}

function openTransactionDetail(transaction) {
  const banners = [
    transaction.is_valid ? "" : '<span class="detail-banner invalid">Transacción inválida</span>',
    transaction.is_duplicate ? '<span class="detail-banner duplicate">Registro duplicado</span>' : "",
  ].filter(Boolean).join("");
  const detailFields = [
    ["Identificador", transaction.transaction_id ?? "—"],
    ["Fuente", SOURCE_LABELS[transaction.source] || transaction.source || "—"],
    ["Monto", transaction.amount ?? "—"],
    ["Moneda", transaction.currency ?? "—"],
    ["Fecha normalizada (UTC)", transaction.timestamp ?? "—"],
    ["Estado", STATUS_LABELS[transaction.status] || transaction.status || "—"],
    ["Válida", transaction.is_valid ? "Sí" : "No"],
    ["Duplicada", transaction.is_duplicate ? "Sí" : "No"],
  ];
  const errors = Array.isArray(transaction.errors) ? transaction.errors : [];
  const errorsMarkup = errors.length
    ? `<div class="error-list">${errors.map((error) => `
      <div class="error-item">
        <strong>${escapeHtml(error.code)} · ${escapeHtml(error.field)}</strong>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `).join("")}</div>`
    : '<p class="empty-note">Sin errores de validación.</p>';
  let sourcePayload;
  try {
    sourcePayload = JSON.stringify(transaction.source_payload, null, 2);
  } catch (error) {
    sourcePayload = "No se pudo mostrar el payload original.";
  }

  elements.detailContent.innerHTML = `
    <div class="detail-banners">${banners}</div>
    <dl class="detail-grid">${detailFields.map(([label, value]) => `
      <div class="detail-field"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>
    `).join("")}</dl>
    <section class="detail-section"><h3>Errores de validación (${errors.length})</h3>${errorsMarkup}</section>
    <section class="detail-section"><h3>Payload original</h3><pre class="json-block">${escapeHtml(sourcePayload)}</pre></section>
  `;
  elements.detailDialog.showModal();
}

async function clearMemory() {
  if (!state.transactions.length) {
    return;
  }
  const confirmed = window.confirm(
    `¿Limpiar los ${state.transactions.length} registros almacenados en memoria? Esta acción no se puede deshacer.`,
  );
  if (!confirmed) {
    return;
  }
  elements.clearButton.disabled = true;
  try {
    const result = await requestJson("/transactions", { method: "DELETE" });
    state.transactions = [];
    renderTransactions([]);
    await refreshDashboard({ silent: true });
    const clearedLabel = result.cleared === 1 ? "registro eliminado" : "registros eliminados";
    showToast(`${formatNumber(result.cleared)} ${clearedLabel} de la memoria.`);
  } catch (error) {
    elements.clearButton.disabled = state.transactions.length === 0;
    showToast(error.message, "error");
  }
}

function resetFilters() {
  state.invalidOnly = false;
  elements.sourceFilter.value = "";
  elements.statusFilter.value = "";
  elements.currencyFilter.value = "";
  elements.searchInput.value = "";
  state.searchRequest += 1;
  renderTransactions(state.transactions);
}

function handleDrop(event) {
  event.preventDefault();
  elements.dropzone.classList.remove("is-dragging");
  setSelectedFiles(Array.from(event.dataTransfer?.files || []));
}

function bindEvents() {
  elements.fileInput.addEventListener("change", (event) => {
    setSelectedFiles(Array.from(event.target.files || []));
    event.target.value = "";
  });
  elements.uploadForm.addEventListener("submit", processSelectedFiles);
  elements.selectedFiles.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-file]");
    if (!button) {
      return;
    }
    state.selectedFiles.splice(Number(button.dataset.removeFile), 1);
    renderSelectedFiles();
  });
  elements.dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    elements.dropzone.classList.add("is-dragging");
  });
  elements.dropzone.addEventListener("dragleave", () => {
    elements.dropzone.classList.remove("is-dragging");
  });
  elements.dropzone.addEventListener("drop", handleDrop);
  [elements.sourceFilter, elements.statusFilter, elements.currencyFilter].forEach(
    (filter) => filter.addEventListener("change", () => renderTransactions(state.transactions)),
  );
  elements.searchInput.addEventListener("input", () => renderTransactions(state.transactions));
  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runIdentifierSearch();
    }
    if (event.key === "Escape") {
      elements.searchInput.value = "";
      renderTransactions(state.transactions);
    }
  });
  document.querySelectorAll("[data-filter-invalid]").forEach((link) => {
    link.addEventListener("click", () => {
      window.setTimeout(() => {
        state.invalidOnly = true;
        elements.statusFilter.value = "";
        elements.sourceFilter.value = "";
        elements.currencyFilter.value = "";
        elements.searchInput.value = "";
        renderTransactions(state.transactions);
      }, 0);
    });
  });
  elements.resetFilters.addEventListener("click", resetFilters);
  elements.transactionRows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-detail-index]");
    if (!button) {
      return;
    }
    const transaction = state.visibleTransactions[Number(button.dataset.detailIndex)];
    if (transaction) {
      openTransactionDetail(transaction);
    }
  });
  elements.clearButton.addEventListener("click", clearMemory);
  elements.refreshButton.addEventListener("click", () => refreshDashboard());
  elements.detailClose.addEventListener("click", () => elements.detailDialog.close());
  elements.detailDialog.addEventListener("click", (event) => {
    if (event.target === elements.detailDialog) {
      elements.detailDialog.close();
    }
  });
  document.querySelector("#alert-close").addEventListener("click", hideAlert);
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
      event.preventDefault();
      elements.searchInput.focus();
    }
  });
}

bindEvents();
checkHealth().then((connected) => {
  if (connected) {
    refreshDashboard();
  }
});
state.refreshTimer = window.setInterval(() => refreshDashboard({ silent: true }), REFRESH_INTERVAL_MS);
