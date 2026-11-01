/**
 * Dynamic Workload Estimator for Crawl Launch Form
 */

document.addEventListener('DOMContentLoaded', () => {
  const sampleInput = document.getElementById('id_sample_size');
  const dwellInput = document.getElementById('id_dwell_time');
  const concurrencyInput = document.getElementById('id_concurrency');

  const estimateTimeDisplay = document.getElementById('estimate-time');
  const estimateWarningDisplay = document.getElementById('estimate-warning');

  function updateEstimate() {
    if (!sampleInput || !dwellInput || !concurrencyInput) return;

    const sample = parseInt(sampleInput.value) || 100;
    const dwell = parseFloat(dwellInput.value) || 5.0;
    const conc = parseInt(concurrencyInput.value) || 2;

    const avgPerDomain = dwell + 4.0;
    const totalSeconds = (sample * avgPerDomain) / Math.max(1, conc);

    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    const hours = Math.floor(minutes / 60);
    const remMin = minutes % 60;

    let formatted = '';
    if (hours > 0) {
      formatted = `~${hours}h ${remMin}m`;
    } else if (minutes > 0) {
      formatted = `~${minutes}m ${seconds}s`;
    } else {
      formatted = `~${seconds}s`;
    }

    if (estimateTimeDisplay) {
      estimateTimeDisplay.textContent = formatted;
    }

    if (estimateWarningDisplay) {
      if (sample > 1000) {
        estimateWarningDisplay.textContent = 'High Workload: Crawling over 1,000 domains runs in background. You can safely close or monitor progress.';
        estimateWarningDisplay.style.display = 'block';
      } else if (sample > 300) {
        estimateWarningDisplay.textContent = 'Medium Workload: Respecting robots.txt and politeness delays.';
        estimateWarningDisplay.style.display = 'block';
      } else {
        estimateWarningDisplay.style.display = 'none';
      }
    }
  }

  // Quick preset buttons (e.g. 10, 50, 100, 500, 1000)
  document.querySelectorAll('.btn-preset-size').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const val = btn.getAttribute('data-size');
      if (sampleInput && val) {
        sampleInput.value = val;
        updateEstimate();
      }
    });
  });

  if (sampleInput) sampleInput.addEventListener('input', updateEstimate);
  if (dwellInput) dwellInput.addEventListener('input', updateEstimate);
  if (concurrencyInput) concurrencyInput.addEventListener('input', updateEstimate);

  updateEstimate();
});
