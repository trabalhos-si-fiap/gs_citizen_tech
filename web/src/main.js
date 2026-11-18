const apiBase = window.RECLAME_JA_API_URL || 'http://localhost:8000';

function metricUrl(format = 'json') {
  const params = new URLSearchParams();
  const category = document.querySelector('#category').value.trim();
  const agency = document.querySelector('#agency').value.trim();
  if (category) params.set('category', category);
  if (agency) params.set('agency_id', agency);
  params.set('format', format);
  return `${apiBase}/v1/public/metrics?${params.toString()}`;
}

async function loadMetrics() {
  const error = document.querySelector('#error');
  error.textContent = '';
  try {
    const response = await fetch(metricUrl('json'));
    if (!response.ok) throw new Error(`API respondeu ${response.status}`);
    const data = await response.json();
    document.querySelector('#totalReports').textContent = data.totals.reports;
    document.querySelector('#avgResponse').textContent =
      data.totals.avg_response_hours ?? '—';
    document.querySelector('#resolutionRate').textContent =
      data.totals.resolution_rate == null
        ? '—'
        : `${(data.totals.resolution_rate * 100).toFixed(1)}%`;
    document.querySelector('#recurrence').textContent =
      data.totals.recurrence;

    const tbody = document.querySelector('#agencyRows');
    tbody.replaceChildren();
    for (const row of data.by_agency) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${row.agency.name}</td>
        <td>${row.reports}</td>
        <td>${row.avg_response_hours ?? '—'}</td>
        <td>${(row.resolution_rate * 100).toFixed(1)}%</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (reason) {
    error.textContent =
      'Não foi possível carregar os indicadores. Verifique a API e o CORS.';
  }
}

document.querySelector('#refresh').addEventListener('click', loadMetrics);
document.querySelector('#download').addEventListener('click', () => {
  window.location.assign(metricUrl('csv'));
});

loadMetrics();
