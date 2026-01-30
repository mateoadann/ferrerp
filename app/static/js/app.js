/**
 * FerrERP - JavaScript Global
 */

// Configuración de HTMX
document.addEventListener('DOMContentLoaded', function() {
    // Configurar CSRF token para HTMX
    document.body.addEventListener('htmx:configRequest', function(event) {
        const csrfToken = document.querySelector('input[name="csrf_token"]');
        if (csrfToken) {
            event.detail.headers['X-CSRFToken'] = csrfToken.value;
        }
    });

    // Cerrar alertas automáticamente después de 5 segundos
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
});

document.addEventListener('DOMContentLoaded', function() {
    const moneyInputs = document.querySelectorAll('input[data-mask="money"]');
    moneyInputs.forEach(initMoneyInput);

    const forms = document.querySelectorAll('form');
    forms.forEach((form) => {
        form.addEventListener('submit', () => {
            const masked = form.querySelectorAll('input[data-mask="money"]');
            masked.forEach((input) => {
                input.value = normalizeMoneyValue(input.value);
            });
        });
    });
});

// Modal de confirmación (para forms con action URL)
function confirmAction(url, message, buttonText = 'Confirmar', buttonClass = 'btn-danger') {
    const modal = document.getElementById('confirmModal');
    const form = document.getElementById('confirmModalForm');
    const messageEl = document.getElementById('confirmModalMessage');
    const submitBtn = document.getElementById('confirmModalSubmit');
    const iconEl = document.getElementById('confirmModalIcon');

    form.action = url;
    messageEl.textContent = message;
    submitBtn.textContent = buttonText;
    submitBtn.className = 'btn ' + buttonClass;
    submitBtn.type = 'submit';
    iconEl.textContent = buttonClass.includes('danger') ? 'warning' : 'help_outline';
    iconEl.style.color = buttonClass.includes('danger') ? 'var(--error)' : 'var(--warning)';

    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// Modal de alerta custom (reemplaza alert() nativo)
function showAlert(message, title, icon) {
    const modal = document.getElementById('alertModal');
    const messageEl = document.getElementById('alertModalMessage');
    const titleEl = document.getElementById('alertModalLabel');
    const iconEl = document.getElementById('alertModalIcon');

    messageEl.textContent = message;
    titleEl.textContent = title || 'Atención';
    iconEl.textContent = icon || 'warning';

    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// Modal de confirmación custom (reemplaza confirm() nativo)
// Retorna una Promise que resuelve a true/false
function showConfirm(message, options = {}) {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        const form = document.getElementById('confirmModalForm');
        const messageEl = document.getElementById('confirmModalMessage');
        const submitBtn = document.getElementById('confirmModalSubmit');
        const titleEl = document.getElementById('confirmModalLabel');
        const iconEl = document.getElementById('confirmModalIcon');

        messageEl.textContent = message;
        titleEl.textContent = options.title || 'Confirmar acción';
        submitBtn.textContent = options.confirmText || 'Confirmar';
        submitBtn.className = 'btn ' + (options.confirmClass || 'btn-primary');
        iconEl.textContent = options.icon || 'help_outline';
        iconEl.style.color = options.iconColor || 'var(--primary)';

        // Deshabilitar submit del form y usar click handler
        form.action = '';
        form.onsubmit = (e) => e.preventDefault();
        submitBtn.type = 'button';

        const handleConfirm = (event) => {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            cleanup();
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
            resolve(true);
        };
        const handleDismiss = () => {
            cleanup();
            resolve(false);
        };

        function cleanup() {
            submitBtn.removeEventListener('click', handleConfirm);
            modal.removeEventListener('hidden.bs.modal', handleDismiss);
            form.onsubmit = null;
        }

        submitBtn.addEventListener('click', handleConfirm, { once: true });
        modal.addEventListener('hidden.bs.modal', handleDismiss, { once: true });

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    });
}

// Formatear moneda
function formatCurrency(value) {
    return new Intl.NumberFormat('es-AR', {
        style: 'currency',
        currency: 'ARS',
        minimumFractionDigits: 2
    }).format(value);
}

// Formatear número
function formatNumber(value, decimals = 2) {
    return new Intl.NumberFormat('es-AR', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(value);
}

function formatThousands(value) {
    return value.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

function normalizeDecimalSeparator(value) {
    if (value.includes(',')) {
        return value;
    }
    if (value.includes('.')) {
        const lastDot = value.lastIndexOf('.');
        const decimalPart = value.slice(lastDot + 1);
        if (/^\d{1,2}$/.test(decimalPart)) {
            const integerPart = value.slice(0, lastDot).replace(/\./g, '');
            return `${integerPart},${decimalPart}`;
        }
        return value.replace(/\./g, '');
    }
    return value;
}

function getMoneyParts(value) {
    const normalized = normalizeDecimalSeparator(value);
    const cleaned = normalized.replace(/[^\d,]/g, '');
    if (cleaned === '') {
        return { integer: '', decimals: '', hasComma: false };
    }
    const parts = cleaned.split(',');
    const integer = (parts[0] || '').replace(/^0+(?=\d)/, '');
    const decimals = (parts[1] || '').slice(0, 2);
    return {
        integer,
        decimals,
        hasComma: cleaned.includes(',')
    };
}

function formatMoneyOnInput(value) {
    const { integer, decimals, hasComma } = getMoneyParts(value);
    if (integer === '' && !hasComma) {
        return '';
    }
    const formattedInt = formatThousands(integer === '' ? '0' : integer);
    if (hasComma) {
        return `${formattedInt},${decimals}`;
    }
    return formattedInt;
}

function formatMoneyOnBlur(value) {
    const { integer, decimals } = getMoneyParts(value);
    if (integer === '' && decimals === '') {
        return '';
    }
    const formattedInt = formatThousands(integer === '' ? '0' : integer);
    const decimalPart = (decimals || '').padEnd(2, '0').slice(0, 2);
    return `${formattedInt},${decimalPart}`;
}

function normalizeMoneyValue(value) {
    const { integer, decimals } = getMoneyParts(value);
    if (integer === '' && decimals === '') {
        return '';
    }
    const decimalPart = (decimals || '').padEnd(2, '0').slice(0, 2);
    return `${integer === '' ? '0' : integer}.${decimalPart}`;
}

function parseMoneyNumber(value) {
    if (value === null || value === undefined) {
        return 0;
    }
    if (typeof value === 'number') {
        return Number.isFinite(value) ? value : 0;
    }
    const normalized = normalizeMoneyValue(String(value));
    if (!normalized) {
        return 0;
    }
    const parsed = Number.parseFloat(normalized);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function getCursorPosition(formatted, digitsBefore, hadCommaBefore) {
    if (digitsBefore === 0) {
        if (hadCommaBefore) {
            const commaIndex = formatted.indexOf(',');
            return commaIndex >= 0 ? commaIndex + 1 : 0;
        }
        return 0;
    }
    let count = 0;
    for (let i = 0; i < formatted.length; i++) {
        if (/\d/.test(formatted[i])) {
            count += 1;
            if (count >= digitsBefore) {
                const commaIndex = formatted.indexOf(',');
                const position = i + 1;
                if (hadCommaBefore && commaIndex >= 0 && position <= commaIndex) {
                    return commaIndex + 1;
                }
                return position;
            }
        }
    }
    return formatted.length;
}

function initMoneyInput(input) {
    if (input.dataset.moneyInit === 'true') {
        return;
    }
    input.dataset.moneyInit = 'true';

    if (input.type === 'number') {
        input.type = 'text';
    }
    if (!input.getAttribute('inputmode')) {
        input.setAttribute('inputmode', 'decimal');
    }

    const updateValue = () => {
        input.value = formatMoneyOnBlur(input.value);
    };

    input.addEventListener('input', () => {
        const original = input.value;
        const cursor = input.selectionStart || 0;
        const rawBefore = original.slice(0, cursor);
        const digitsBefore = rawBefore.replace(/\D/g, '').length;
        const hadCommaBefore = rawBefore.includes(',');
        const formatted = formatMoneyOnInput(original);
        input.value = formatted;
        const newPos = getCursorPosition(formatted, digitsBefore, hadCommaBefore);
        input.setSelectionRange(newPos, newPos);
    });

    input.addEventListener('blur', () => {
        input.value = formatMoneyOnBlur(input.value);
    });

    updateValue();
}

// Debounce para búsquedas
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Toggle sidebar en móvil
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    sidebar.classList.toggle('open');
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // F2 - Focus en búsqueda
    if (e.key === 'F2') {
        e.preventDefault();
        const searchInput = document.querySelector('.search-bar input, .pos-search input');
        if (searchInput) {
            searchInput.focus();
            searchInput.select();
        }
    }

    // Escape - Cerrar modales
    if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
        });
    }
});

// Inicializar tooltips de Bootstrap
document.addEventListener('DOMContentLoaded', function() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Utilidad para mostrar notificaciones toast
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container') || createToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
    return container;
}
