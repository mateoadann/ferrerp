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

        const handleConfirm = () => {
            cleanup();
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
