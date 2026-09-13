(() => {
  const root = document.querySelector('[data-seo-checker]');
  if (!root) return;

  const form = root.querySelector('[data-check-form]');
  const input = root.querySelector('[data-check-input]');
  const loading = root.querySelector('[data-check-loading]');
  const loadingText = root.querySelector('[data-loading-text]');
  const errorBox = root.querySelector('[data-check-error]');
  const results = root.querySelector('[data-check-results]');
  const teaser = root.querySelector('[data-teaser]');
  const full = root.querySelector('[data-full]');
  const emailForm = root.querySelector('[data-email-form]');
  const emailStatus = root.querySelector('[data-email-status]');

  const API_URL = '/api/check';
  const FORMSPREE_ACTION = 'https://formspree.io/f/mnpqyeel';
  const SEVERITY_ORDER = { severe: 0, medium: 1, low: 2 };

  // All localizable UI strings come from data-* attributes build.py renders
  // from content/{en,de}.json's seo_checker section — same pattern main.js
  // already uses for the contact form's status messages. Only the audit
  // *findings* (category names, check detail/tip text) stay English,
  // since those come back from the Cloudflare Worker as-is.
  const i18n = {
    loadingMessages: JSON.parse(root.dataset.loadingMessages || '["Loading…"]'),
    errorGeneric: root.dataset.errorGeneric,
    errorNetwork: root.dataset.errorNetwork,
    noIssuesMessage: root.dataset.noIssuesMessage,
    priorityEmpty: root.dataset.priorityEmpty,
    allTabLabel: root.dataset.allTabLabel,
    severity: {
      severe: root.dataset.severitySevere,
      medium: root.dataset.severityMedium,
      low: root.dataset.severityLow,
    },
    statusPass: root.dataset.statusPass,
    statusFail: root.dataset.statusFail,
    unlockLabel: root.dataset.unlockLabel,
    unlockingLabel: root.dataset.unlockingLabel,
    emailError: root.dataset.emailError,
  };

  let lastReport = null;
  let loadingInterval = null;

  function setLoading(isLoading) {
    loading.hidden = !isLoading;
    form.querySelector('button[type="submit"]').disabled = isLoading;
    if (isLoading) {
      let i = 0;
      loadingText.textContent = i18n.loadingMessages[0];
      loadingInterval = setInterval(() => {
        i = (i + 1) % i18n.loadingMessages.length;
        loadingText.textContent = i18n.loadingMessages[i];
      }, 2500);
    } else if (loadingInterval) {
      clearInterval(loadingInterval);
      loadingInterval = null;
    }
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = '';
  }

  // Check detail/tip text is plain text describing markup (e.g. a real
  // check says `No <link rel=canonical>` to literally name the missing
  // tag) — inserted via innerHTML below for the badges around it, so
  // without escaping, the browser parses that as real HTML instead of
  // displaying it: a void tag like <link> silently swallows everything
  // after it, and a non-void one like <main> swallows everything until
  // the string ends. Escape every value that came from the API before
  // it touches innerHTML.
  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function gradeClass(grade) {
    if (grade === 'A' || grade === 'B') return 'is-good';
    if (grade === 'C') return 'is-mid';
    return 'is-bad';
  }

  function categoryBreakdown(checks) {
    const byCategory = new Map();
    for (const check of checks) {
      if (!byCategory.has(check.category)) byCategory.set(check.category, []);
      byCategory.get(check.category).push(check);
    }
    return byCategory;
  }

  function renderTeaser(report) {
    const g = gradeClass(report.grade);
    root.querySelector('[data-score-grade]').textContent = report.grade;
    root.querySelector('[data-score-grade]').className = 'checker-grade-circle ' + g;
    root.querySelector('[data-score-pct]').textContent = `${report.score_pct}% — ${report.passed}/${report.total} checks passed`;
    root.querySelector('[data-score-url]').textContent = report.url;

    const byCategory = categoryBreakdown(report.checks);
    const chipsEl = root.querySelector('[data-category-chips]');
    chipsEl.innerHTML = '';
    for (const [category, checks] of byCategory) {
      const passed = checks.filter((c) => c.passed).length;
      const chip = document.createElement('div');
      chip.className = 'checker-chip' + (passed === checks.length ? ' is-good' : passed === 0 ? ' is-bad' : ' is-mid');
      chip.innerHTML = `<span>${escapeHtml(category)}</span><strong>${passed}/${checks.length}</strong>`;
      chipsEl.appendChild(chip);
    }

    const topFails = report.checks
      .filter((c) => !c.passed)
      .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
      .slice(0, 5);
    const findingsEl = root.querySelector('[data-top-findings]');
    findingsEl.innerHTML = '';
    if (topFails.length === 0) {
      const li = document.createElement('li');
      li.className = 'checker-finding is-good';
      li.textContent = i18n.noIssuesMessage;
      findingsEl.appendChild(li);
    } else {
      for (const check of topFails) {
        const li = document.createElement('li');
        li.className = 'checker-finding';
        li.innerHTML = `<span class="checker-badge severity-${check.severity}">${i18n.severity[check.severity]}</span> <strong>${escapeHtml(check.label)}</strong> — ${escapeHtml(check.detail)}`;
        findingsEl.appendChild(li);
      }
    }
  }

  function renderFull(report) {
    const byCategory = categoryBreakdown(report.checks);

    const priorityEl = root.querySelector('[data-priority-list]');
    priorityEl.innerHTML = '';
    const priority = report.checks
      .filter((c) => !c.passed)
      .sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity])
      .slice(0, 5);
    if (priority.length === 0) {
      priorityEl.innerHTML = `<li class="checker-priority-item">${i18n.priorityEmpty}</li>`;
    } else {
      priority.forEach((check, i) => {
        const li = document.createElement('li');
        li.className = 'checker-priority-item';
        li.innerHTML = `<span class="checker-priority-num">${i + 1}</span><span class="checker-badge severity-${check.severity}">${i18n.severity[check.severity]}</span> <strong>${escapeHtml(check.label)}</strong> — ${escapeHtml(check.detail)}`;
        priorityEl.appendChild(li);
      });
    }

    const tabsEl = root.querySelector('[data-category-tabs]');
    const categoriesEl = root.querySelector('[data-categories]');
    tabsEl.innerHTML = '';
    categoriesEl.innerHTML = '';

    const allTab = document.createElement('button');
    allTab.type = 'button';
    allTab.className = 'checker-tab is-active';
    allTab.textContent = i18n.allTabLabel;
    allTab.dataset.filter = 'all';
    tabsEl.appendChild(allTab);

    for (const [category, checks] of byCategory) {
      const passed = checks.filter((c) => c.passed).length;
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'checker-tab';
      tab.dataset.filter = category;
      tab.innerHTML = `${escapeHtml(category)} <span>${passed}/${checks.length}</span>`;
      tabsEl.appendChild(tab);

      const card = document.createElement('div');
      card.className = 'checker-category-card';
      card.dataset.category = category;
      const allPassed = passed === checks.length;
      // Every category shows expanded by default, even all-passing ones —
      // a lead-magnet tool that visibly hides "boring" passing checks
      // reads as broken/incomplete rather than tidy. Collapsing is a
      // manual choice the visitor can make per category, not a default.
      card.innerHTML = `
        <button type="button" class="checker-category-head" aria-expanded="true">
          <span class="checker-category-ring ${allPassed ? 'is-good' : 'is-mid'}">${passed}/${checks.length}</span>
          <span class="checker-category-name">${escapeHtml(category)}</span>
          <span class="checker-category-chevron">▴</span>
        </button>
        <div class="checker-category-body">
          ${checks
            .map(
              (c) => `
            <div class="checker-check-row">
              <div>
                <p class="checker-check-title">${escapeHtml(c.label)}</p>
                <p class="checker-check-detail">${escapeHtml(c.detail)}</p>
                ${!c.passed && c.tip ? `<p class="checker-check-tip">${escapeHtml(c.tip)}</p>` : ''}
              </div>
              <div class="checker-check-badges">
                <span class="checker-badge severity-${c.severity}">${i18n.severity[c.severity]}</span>
                <span class="checker-badge ${c.passed ? 'status-pass' : 'status-fail'}">${c.passed ? i18n.statusPass : i18n.statusFail}</span>
              </div>
            </div>`
            )
            .join('')}
        </div>`;
      categoriesEl.appendChild(card);
    }

    tabsEl.addEventListener('click', (e) => {
      const tab = e.target.closest('.checker-tab');
      if (!tab) return;
      tabsEl.querySelectorAll('.checker-tab').forEach((t) => t.classList.remove('is-active'));
      tab.classList.add('is-active');
      const filter = tab.dataset.filter;
      categoriesEl.querySelectorAll('.checker-category-card').forEach((card) => {
        card.hidden = filter !== 'all' && card.dataset.category !== filter;
      });
    });

    categoriesEl.addEventListener('click', (e) => {
      const head = e.target.closest('.checker-category-head');
      if (!head) return;
      const body = head.nextElementSibling;
      const expanded = head.getAttribute('aria-expanded') === 'true';
      head.setAttribute('aria-expanded', String(!expanded));
      body.hidden = expanded;
      head.querySelector('.checker-category-chevron').textContent = expanded ? '▾' : '▴';
    });
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();
    const url = input.value.trim();
    if (!url) return;

    results.hidden = true;
    teaser.hidden = true;
    full.hidden = true;
    setLoading(true);

    try {
      const resp = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        showError(data.error || i18n.errorGeneric);
        return;
      }
      lastReport = data;
      results.hidden = false;
      teaser.hidden = false;
      renderTeaser(data);
    } catch (err) {
      showError(i18n.errorNetwork);
    } finally {
      setLoading(false);
    }
  });

  if (emailForm) {
    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!lastReport) return;
      const emailInput = emailForm.querySelector('[data-email-input]');
      const submitBtn = emailForm.querySelector('button[type="submit"]');
      const marketingConsent = emailForm.querySelector('[data-marketing-consent]');
      const email = emailInput.value.trim();
      if (!email) return;

      submitBtn.disabled = true;
      const originalLabel = submitBtn.textContent;
      submitBtn.textContent = i18n.unlockingLabel;

      const fd = new FormData();
      fd.append('email', email);
      fd.append('_subject', `Website Checker report request for ${lastReport.url}`);
      // Written as a plain sentence rather than a raw key:value dump — the
      // previous rigid "Checked: X\nScore: Y\nPassed: Z" template, plus the
      // bare URL, reads a lot like the shape of content spam filters are
      // tuned to catch, which is a likely reason submissions were landing
      // in Formspree's spam folder even on a brand-new form.
      fd.append(
        'message',
        `Someone unlocked the full Website Checker report for ${lastReport.url}. ` +
          `They scored ${lastReport.score_pct}% (grade ${lastReport.grade}), passing ${lastReport.passed} of ${lastReport.total} checks.`
      );
      // Sent either way (not just when checked) so there's always a clear
      // record of whether marketing consent was given for this lead.
      fd.append('marketing_consent', marketingConsent && marketingConsent.checked ? 'yes' : 'no');

      try {
        const resp = await fetch(FORMSPREE_ACTION, { method: 'POST', body: fd, headers: { Accept: 'application/json' } });
        if (resp.ok) {
          teaser.hidden = true;
          full.hidden = false;
          renderFull(lastReport);
          full.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
          emailStatus.textContent = i18n.emailError;
          emailStatus.hidden = false;
        }
      } catch (err) {
        emailStatus.textContent = i18n.errorNetwork;
        emailStatus.hidden = false;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalLabel;
      }
    });
  }
})();
