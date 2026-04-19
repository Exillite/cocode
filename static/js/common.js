// Общие функции для всех страниц

let uiShell = null;

function ensureUiShell() {
    if (uiShell) {
        return uiShell;
    }

    if (!document.getElementById('cocode-ui-styles')) {
        const style = document.createElement('style');
        style.id = 'cocode-ui-styles';
        style.textContent = `
            .cocode-toast-stack {
                position: fixed;
                right: 20px;
                bottom: 20px;
                z-index: 5000;
                display: flex;
                flex-direction: column;
                gap: 10px;
                pointer-events: none;
            }
            .cocode-toast {
                min-width: 240px;
                max-width: min(420px, calc(100vw - 32px));
                padding: 14px 16px;
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                background: rgba(8, 17, 32, 0.96);
                color: #ecf3ff;
                box-shadow: 0 18px 40px rgba(0, 0, 0, 0.34);
                backdrop-filter: blur(18px);
                font-family: Manrope, sans-serif;
                font-size: 14px;
                line-height: 1.5;
                pointer-events: auto;
                animation: cocode-toast-in 0.18s ease-out;
            }
            .cocode-toast-success { border-color: rgba(40, 215, 161, 0.3); }
            .cocode-toast-error { border-color: rgba(255, 107, 122, 0.3); }
            .cocode-toast-warning { border-color: rgba(255, 203, 107, 0.3); }
            .cocode-dialog-backdrop {
                position: fixed;
                inset: 0;
                z-index: 5100;
                display: none;
                align-items: center;
                justify-content: center;
                padding: 16px;
                background: rgba(2, 7, 14, 0.72);
                backdrop-filter: blur(8px);
            }
            .cocode-dialog {
                width: min(420px, calc(100vw - 32px));
                padding: 22px;
                border-radius: 22px;
                border: 1px solid rgba(161, 190, 230, 0.16);
                background: rgba(10, 22, 39, 0.96);
                color: #ecf3ff;
                box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
                font-family: Manrope, sans-serif;
            }
            .cocode-dialog h3 {
                margin: 0 0 8px;
                font-size: 20px;
                font-weight: 800;
            }
            .cocode-dialog p {
                margin: 0 0 16px;
                color: #93a9ca;
                line-height: 1.6;
            }
            .cocode-dialog input {
                width: 100%;
                margin: 0 0 16px;
                padding: 14px 16px;
                border-radius: 14px;
                border: 1px solid rgba(161, 190, 230, 0.16);
                background: rgba(8, 17, 32, 0.88);
                color: #ecf3ff;
                font: inherit;
                outline: none;
            }
            .cocode-dialog input:focus {
                border-color: rgba(124, 173, 255, 0.32);
                box-shadow: 0 0 0 4px rgba(77, 162, 255, 0.14);
            }
            .cocode-dialog-actions {
                display: flex;
                gap: 10px;
                justify-content: flex-end;
            }
            .cocode-dialog-actions button {
                width: auto;
                margin: 0;
                padding: 10px 14px;
                border: 1px solid rgba(106, 169, 255, 0.18);
                border-radius: 10px;
                background: linear-gradient(135deg, #4da2ff 0%, #1f78ff 100%);
                color: white;
                font: inherit;
                font-weight: 700;
                cursor: pointer;
                box-shadow: 0 12px 30px rgba(31, 120, 255, 0.22);
            }
            .cocode-dialog-actions .secondary {
                background: rgba(255, 255, 255, 0.05);
                color: #ecf3ff;
                box-shadow: none;
            }
            .cocode-dialog-actions .danger {
                background: linear-gradient(135deg, rgba(255, 107, 122, 0.92), rgba(255, 84, 103, 0.92));
                box-shadow: 0 12px 30px rgba(255, 84, 103, 0.2);
            }
            @keyframes cocode-toast-in {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }
        `;
        document.head.appendChild(style);
    }

    const toastStack = document.createElement('div');
    toastStack.className = 'cocode-toast-stack';

    const backdrop = document.createElement('div');
    backdrop.className = 'cocode-dialog-backdrop';
    backdrop.innerHTML = `
        <div class="cocode-dialog" role="dialog" aria-modal="true">
            <h3 id="cocode-dialog-title"></h3>
            <p id="cocode-dialog-message"></p>
            <input id="cocode-dialog-input" type="text" style="display: none;" />
            <div class="cocode-dialog-actions">
                <button id="cocode-dialog-cancel" class="secondary" type="button">Отмена</button>
                <button id="cocode-dialog-confirm" type="button">Ок</button>
            </div>
        </div>
    `;

    document.body.appendChild(toastStack);
    document.body.appendChild(backdrop);

    uiShell = {
        toastStack,
        backdrop,
        title: backdrop.querySelector('#cocode-dialog-title'),
        message: backdrop.querySelector('#cocode-dialog-message'),
        input: backdrop.querySelector('#cocode-dialog-input'),
        cancel: backdrop.querySelector('#cocode-dialog-cancel'),
        confirm: backdrop.querySelector('#cocode-dialog-confirm'),
        resolver: null
    };

    return uiShell;
}

function uiToast(message, type = 'info', duration = 2600) {
    const shell = ensureUiShell();
    const toast = document.createElement('div');
    toast.className = `cocode-toast cocode-toast-${type}`;
    toast.textContent = message;
    shell.toastStack.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, duration);
}

function openDialog(options) {
    const shell = ensureUiShell();
    shell.title.textContent = options.title || 'Сообщение';
    shell.message.textContent = options.message || '';
    shell.confirm.textContent = options.confirmText || 'Ок';
    shell.cancel.textContent = options.cancelText || 'Отмена';
    shell.confirm.className = options.danger ? 'danger' : '';
    shell.cancel.style.display = options.showCancel ? 'inline-flex' : 'none';
    shell.input.style.display = options.mode === 'prompt' ? 'block' : 'none';
    shell.input.value = options.value || '';
    shell.input.placeholder = options.placeholder || '';
    shell.backdrop.style.display = 'flex';

    return new Promise((resolve) => {
        shell.resolver = resolve;

        function close(result) {
            shell.backdrop.style.display = 'none';
            shell.confirm.onclick = null;
            shell.cancel.onclick = null;
            shell.backdrop.onclick = null;
            shell.input.onkeydown = null;
            shell.resolver = null;
            resolve(result);
        }

        shell.confirm.onclick = () => {
            close(options.mode === 'prompt' ? shell.input.value.trim() : true);
        };

        shell.cancel.onclick = () => close(options.mode === 'prompt' ? null : false);

        shell.backdrop.onclick = (event) => {
            if (event.target === shell.backdrop) {
                close(options.mode === 'prompt' ? null : false);
            }
        };

        shell.input.onkeydown = (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                shell.confirm.click();
            }
            if (event.key === 'Escape') {
                shell.cancel.click();
            }
        };

        if (options.mode === 'prompt') {
            setTimeout(() => shell.input.focus(), 0);
        } else {
            setTimeout(() => shell.confirm.focus(), 0);
        }
    });
}

function uiAlert(message, options = {}) {
    return openDialog({
        title: options.title || 'Сообщение',
        message,
        confirmText: options.confirmText || 'Понятно',
        showCancel: false
    });
}

function uiConfirm(message, options = {}) {
    return openDialog({
        title: options.title || 'Подтвердите действие',
        message,
        confirmText: options.confirmText || 'Подтвердить',
        cancelText: options.cancelText || 'Отмена',
        showCancel: true,
        danger: !!options.danger
    });
}

function uiPrompt(message, options = {}) {
    return openDialog({
        title: options.title || 'Введите значение',
        message,
        confirmText: options.confirmText || 'Сохранить',
        cancelText: options.cancelText || 'Отмена',
        showCancel: true,
        mode: 'prompt',
        value: options.value || '',
        placeholder: options.placeholder || ''
    });
}

function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    localStorage.setItem('token', token);
}

function removeToken() {
    localStorage.removeItem('token');
}

function isLoggedIn() {
    return !!getToken();
}

function redirectToLogin() {
    window.location.href = '/static/login.html';
}

function redirectToRooms() {
    window.location.href = '/static/rooms.html';
}

function redirectToRoom(roomId) {
    window.location.href = `/static/room.html?room=${roomId}`;
}

// Проверка логина при загрузке страницы
function checkAuth(requiredAuth = true) {
    const isLogged = isLoggedIn();
    
    if (requiredAuth && !isLogged) {
        redirectToLogin();
    }
    
    return isLogged;
}

// API функции
async function login(username, password) {
    const response = await fetch('/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: new URLSearchParams({
            username: username,
            password: password
        })
    });
    return response.json();
}

async function register(username, password) {
    const response = await fetch('/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: username,
            password: password
        })
    });
    return response.json();
}

async function getRooms() {
    const response = await fetch('/rooms', {
        headers: {
            'Authorization': 'Bearer ' + getToken()
        }
    });
    return response.json();
}

async function createRoom(name) {
    const response = await fetch('/create-room', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + getToken()
        },
        body: JSON.stringify({ name: name })
    });
    return response.json();
}

// Утилиты для отображения сообщений об ошибках
function showError(elementId, message) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
    }
}

function hideError(elementId) {
    const errorDiv = document.getElementById(elementId);
    if (errorDiv) {
        errorDiv.style.display = 'none';
    }
}

function showSuccess(elementId, message) {
    const successDiv = document.getElementById(elementId);
    if (successDiv) {
        successDiv.textContent = message;
        successDiv.style.display = 'block';
    }
}

function hideSuccess(elementId) {
    const successDiv = document.getElementById(elementId);
    if (successDiv) {
        successDiv.style.display = 'none';
    }
}
