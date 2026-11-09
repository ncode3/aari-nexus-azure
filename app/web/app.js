'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let token = '';
  let operatorId = null;
  let generation = 0;
  const active = new Set();

  function lock() {
    generation++;
    token = '';
    operatorId = null;
    for (const controller of active) controller.abort();
    active.clear();
    $('api-token').value = '';
    $('workspace').hidden = true;
    $('unlock-panel').hidden = false;
    $('disconnect').hidden = true;
    $('connection-label').textContent = 'Locked';
    $('messages').replaceChildren();
    $('memory-results').textContent = 'Search to recall saved context.';
    $('save-result').textContent = '';
    $('workspace-error').textContent = '';
    for (const id of ['chat-input', 'memory-query', 'memory-input']) $(id).value = '';
  }

  async function api(path, options = {}) {
    const current = generation;
    const controller = new AbortController();
    active.add(controller);
    try {
      const response = await fetch(path, { ...options, cache: 'no-store', credentials: 'omit',
        signal: controller.signal, headers: { 'Content-Type': 'application/json', ...options.headers, Authorization: 'Bearer ' + token } });
      if (current !== generation) throw new DOMException('Workspace locked', 'AbortError');
      if (!response.ok) {
        if (response.status === 401) { lock(); throw new Error('Token not accepted. Unlock with your local API token.'); }
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || 'Nexus could not complete this request.');
      }
      const body = await response.json();
      if (current !== generation) throw new DOMException('Workspace locked', 'AbortError');
      return body;
    } finally { active.delete(controller); }
  }

  async function refreshStatus() {
    const status = await api('/local/runtime');
    operatorId = status.operator_id;
    $('model-name').textContent = status.model;
    $('model-status').textContent = status.model_available ? 'Ollama is ready' : 'Ollama is unavailable';
    $('memory-count').textContent = String(status.memory_records);
    $('telegram-status').textContent = status.telegram_polling ? 'Enabled' : 'Disabled';
    $('uptime').textContent = 'Uptime ' + Math.floor(status.uptime_seconds / 60) + ' min';
    $('connection-label').textContent = status.model_available ? 'Connected locally' : 'Local · model unavailable';
  }

  function appendMessage(role, text) {
    $('chat-empty')?.remove();
    const article = document.createElement('article');
    article.className = 'message ' + role;
    const label = document.createElement('strong');
    label.textContent = role === 'user' ? 'You' : 'Nexus';
    const content = document.createElement('div');
    content.textContent = text;
    article.append(label, content);
    $('messages').append(article);
    $('messages').scrollTop = $('messages').scrollHeight;
  }

  async function command(text) {
    return api('/local/command', { method: 'POST', body: JSON.stringify({ chat_id: operatorId, text }) });
  }

  async function busy(buttonId, action) {
    const button = $(buttonId);
    button.disabled = true;
    $('workspace-error').textContent = '';
    try { await action(); }
    catch (error) { if (error.name !== 'AbortError') $('workspace-error').textContent = error.message; }
    finally { button.disabled = false; }
  }

  $('unlock-form').addEventListener('submit', async event => {
    event.preventDefault();
    $('unlock-error').textContent = '';
    token = $('api-token').value.trim();
    $('api-token').value = '';
    try {
      await refreshStatus();
      $('unlock-panel').hidden = true;
      $('workspace').hidden = false;
      $('disconnect').hidden = false;
      $('chat-input').focus();
    } catch (error) {
      lock();
      if (error.name !== 'AbortError') $('unlock-error').textContent = error.message;
    }
  });
  $('disconnect').addEventListener('click', lock);
  $('refresh-status').addEventListener('click', () => busy('refresh-status', refreshStatus));
  $('chat-form').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('chat-input').value.trim();
    if (!text) return;
    busy('send-chat', async () => {
      appendMessage('user', text);
      $('chat-input').value = '';
      const result = await command(text.startsWith('/') ? text : '/brief ' + text);
      appendMessage('assistant', result.reply);
      await refreshStatus();
    });
  });
  $('search-form').addEventListener('submit', event => {
    event.preventDefault();
    busy('search-memory', async () => { const result = await command('/find ' + $('memory-query').value.trim()); $('memory-results').textContent = result.reply; });
  });
  $('remember-form').addEventListener('submit', event => {
    event.preventDefault();
    const text = $('memory-input').value.trim();
    if (!text) return;
    busy('save-memory', async () => {
      const result = await command('/remember ' + text);
      $('memory-input').value = '';
      $('save-result').textContent = result.reply;
      await refreshStatus();
    });
  });
})();
