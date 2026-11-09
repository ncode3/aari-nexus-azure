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
    $('assessment-jobs').replaceChildren();
    $('assessment-reports').replaceChildren();
    for (const id of ['assessment-paths', 'assessment-dependency', 'assessment-counts', 'assessment-audit']) $(id).textContent = '';
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
        const error = new Error(body.detail || 'Nexus could not complete this request.');
        error.status = response.status;
        throw error;
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
    await refreshAssessments();
  }

  async function downloadOutput(name) {
    const current = generation;
    const controller = new AbortController();
    active.add(controller);
    try {
      const response = await fetch('/local/assessment-outputs/' + name, {credentials: 'omit', cache: 'no-store', signal: controller.signal, headers: {Authorization: 'Bearer ' + token}});
      if (!response.ok) throw new Error('Output download failed (' + response.status + ')');
      const blob = await response.blob();
      if (current !== generation) return;
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = name.split('/').pop();
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } finally { active.delete(controller); }
  }

  function outputButton(name, label) {
    const button = document.createElement('button');
    button.className = 'quiet';
    button.textContent = label;
    button.addEventListener('click', async () => {
      try { await downloadOutput(name); }
      catch (error) { if (error.name !== 'AbortError') $('workspace-error').textContent = error.message; }
    });
    return button;
  }

  let assessmentsRefreshing = false;
  async function refreshAssessments() {
    if (assessmentsRefreshing) return;
    assessmentsRefreshing = true;
    try {
      const data = await api('/local/assessments');
      $('assessment-watcher').textContent = data.watcher_alive ? 'Watcher running' : 'Watcher stopped';
      $('assessment-paths').textContent = 'Intake: ' + data.intake + '\nOutputs: ' + data.outputs + '\nConfiguration: ' + data.configuration;
      $('assessment-dependency').textContent = data.configuration_dependency || data.watcher_error || '';
      $('assessment-counts').textContent = Object.entries(data.counts).map(([status, count]) => status + ': ' + count).join(' · ');
      $('assessment-reports').replaceChildren(...data.reports.map(name => outputButton(name, 'Latest ' + name)));
      $('assessment-jobs').replaceChildren();
      for (const job of data.jobs) {
        const row = document.createElement('tr');
        for (const value of [job.name + '\n' + job.id.slice(0, 12), job.status, String(job.attempts) + ' / 3']) {
          const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
        }
        const cell = document.createElement('td');
        const issue = document.createElement('p');
        let issueText = job.error || '';
        try {
          const issues = JSON.parse(issueText);
          if (Array.isArray(issues)) issueText = issues.map(item =>
            (item.row ? 'Row ' + item.row + ': ' : '') + item.issue +
            (item.model_suggestion_verified === false ? ' Local model suggestion awaits staff review; download the evidence.' : '')
          ).join('\n');
        } catch (_) { /* Plain runtime failures already contain a readable message. */ }
        issue.textContent = issueText;
        cell.append(issue);
        if (job.output) cell.append(outputButton(job.output, 'Download job evidence'));
        if (['failed', 'review'].includes(job.status)) {
          const retry = document.createElement('button'); retry.className = 'quiet'; retry.textContent = 'Retry after correction';
          retry.addEventListener('click', async () => {
            retry.disabled = true;
            try { await api('/local/assessments/' + job.id + '/retry', {method: 'POST'}); await refreshAssessments(); }
            catch (error) { if (error.name !== 'AbortError') $('workspace-error').textContent = error.message; }
          });
          cell.append(retry);
        }
        row.append(cell); $('assessment-jobs').append(row);
      }
      $('assessment-audit').textContent = data.events.map(e => e.at + ' ' + (e.job_id || '').slice(0, 12) + ' ' + e.event + ' ' + e.detail).join('\n');
    } catch (error) {
      if (error.status !== 404) throw error;
      $('assessment-watcher').textContent = 'Runtime restart required';
      $('assessment-dependency').textContent = 'Restart Nexus to load the assessment worker.';
    } finally { assessmentsRefreshing = false; }
  }

  setInterval(() => {
    if (token && !$('workspace').hidden) refreshAssessments().catch(error => {
      if (error.name !== 'AbortError') $('workspace-error').textContent = error.message;
    });
  }, 5000);

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
