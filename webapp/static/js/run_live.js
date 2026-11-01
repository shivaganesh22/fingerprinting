document.addEventListener('DOMContentLoaded', () => {
  const root = document.getElementById('live-run-container');
  if (!root) return;

  const runId = root.dataset.runId;
  const byId = (id) => document.getElementById(id);
  const nodes = {
    bar: byId('live-progress-bar'),
    percent: byId('live-percent-text'),
    status: byId('live-status-badge'),
    domain: byId('live-current-domain'),
    rank: byId('live-current-rank'),
    progress: byId('domain-progress-count'),
    attempted: byId('count-attempted'),
    total: byId('count-total'),
    loaded: byId('count-completed'),
    failed: byId('count-failed'),
    skipped: byId('count-skipped'),
    elapsed: byId('time-elapsed'),
    eta: byId('time-eta'),
    visits: byId('live-visits-tbody'),
    cancel: byId('btn-cancel-run'),
    report: byId('btn-view-report'),
  };
  let timer;

  const setText = (node, value) => { if (node) node.textContent = value ?? '—'; };
  const formatTime = (seconds) => `${Math.floor(seconds / 60)}m ${seconds % 60}s`;

  function addCell(row, value, className = '') {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    cell.textContent = value === null || value === undefined || value === '' ? '—' : value;
    row.appendChild(cell);
  }

  function renderVisits(visits, blockedMeasured) {
    if (!nodes.visits || !Array.isArray(visits) || visits.length === 0) return;
    nodes.visits.replaceChildren();
    visits.slice().reverse().forEach((visit) => {
      const row = document.createElement('tr');
      addCell(row, visit.rank ?? '—', 'number-cell');
      addCell(row, visit.domain, 'font-mono');

      const statusCell = document.createElement('td');
      const pill = document.createElement('span');
      pill.className = `state-pill ${visit.status === 'ok' ? 'state-good' : visit.status.startsWith('skipped') ? 'state-neutral' : 'state-bad'}`;
      pill.textContent = visit.status.replaceAll('_', ' ');
      statusCell.appendChild(pill);
      row.appendChild(statusCell);

      addCell(row, visit.http_status, 'number-cell');
      addCell(row, visit.load_time_ms ? `${visit.load_time_ms} ms` : '—', 'number-cell');
      addCell(row, visit.requests_count, 'number-cell');
      addCell(row, blockedMeasured ? (visit.blocked_requests ?? 0) : 'n/a', 'number-cell');
      addCell(row, visit.ts, 'muted-cell');
      nodes.visits.appendChild(row);
    });
  }

  async function refresh() {
    try {
      const response = await fetch(`/api/run/${encodeURIComponent(runId)}/progress/`, { headers: { Accept: 'application/json' } });
      if (!response.ok) return;
      const data = await response.json();
      const attempted = data.attempted_count ?? 0;
      const total = data.domains_total ?? 0;
      const percent = data.percent ?? 0;

      if (nodes.bar) nodes.bar.style.width = `${percent}%`;
      setText(nodes.percent, `${percent}%`);
      setText(nodes.progress, `${attempted}/${total}`);
      setText(nodes.attempted, attempted);
      setText(nodes.total, total);
      setText(nodes.loaded, data.completed_count);
      setText(nodes.failed, data.failed_count);
      setText(nodes.skipped, data.skipped_count);
      setText(nodes.domain, data.current_domain || (data.status === 'completed' ? 'Crawl complete' : 'Preparing crawl…'));
      setText(nodes.rank, data.current_rank ? `Tranco #${data.current_rank}` : '');
      if (nodes.elapsed && data.elapsed_seconds !== undefined) setText(nodes.elapsed, formatTime(data.elapsed_seconds));
      if (nodes.eta && data.eta_seconds !== undefined) {
        const terminalLabels = { completed: 'Done', cancelled: 'Stopped', failed: 'Failed' };
        setText(nodes.eta, terminalLabels[data.status] || (data.eta_seconds ? formatTime(data.eta_seconds) : 'Calculating…'));
      }

      if (nodes.status) {
        nodes.status.textContent = data.status.replaceAll('_', ' ');
        nodes.status.className = `state-pill ${data.status === 'completed' ? 'state-good' : ['running', 'queued'].includes(data.status) ? 'state-neutral' : 'state-bad'}`;
      }
      renderVisits(data.recent_visits, data.blocked_counter_measured);

      if (!data.is_active) {
        if (nodes.cancel) nodes.cancel.hidden = true;
        if (nodes.report) nodes.report.hidden = false;
        if (nodes.bar) nodes.bar.classList.remove('progress-bar-animated');
        clearInterval(timer);
      }
    } catch (error) {
      console.error('Could not refresh crawl progress', error);
    }
  }

  if (nodes.cancel) nodes.cancel.addEventListener('click', async () => {
    if (!window.confirm('Stop this crawl? Results already collected will be kept.')) return;
    nodes.cancel.disabled = true;
    try {
      const token = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='))?.split('=').slice(1).join('=');
      await fetch(`/api/run/${encodeURIComponent(runId)}/cancel/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': decodeURIComponent(token || ''), 'Content-Type': 'application/json' },
      });
      await refresh();
    } finally {
      nodes.cancel.disabled = false;
    }
  });

  refresh();
  timer = setInterval(refresh, 1800);
});
