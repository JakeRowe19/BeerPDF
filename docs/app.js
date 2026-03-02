(() => {
  const statusEl = document.getElementById('status');
  const gridEl = document.getElementById('grid');
  const refreshEl = document.getElementById('refresh');
  const updatedAtEl = document.getElementById('updatedAt');

  const modal = document.getElementById('modal');
  const backdrop = document.getElementById('modalBackdrop');
  const closeBtn = document.getElementById('closeBtn');
  const printBtn = document.getElementById('printBtn');
  const frame = document.getElementById('pdfFrame');
  const modalTitle = document.getElementById('modalTitle');
  const openPdf = document.getElementById('openPdf');

  let all = [];
  let currentPdfUrl = '';

  const cacheBuster = () => `v=${Date.now()}`;

  async function loadMeta() {
    const url = `./labels/meta.json?${cacheBuster()}`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) return null;
    try { return await res.json(); } catch { return null; }
  }

  async function loadIndex() {
    const url = `./labels/index.json?${cacheBuster()}`;
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error(`Не удалось загрузить index.json (${res.status})`);
    const data = await res.json();
    if (!Array.isArray(data)) throw new Error('index.json должен быть массивом');
    // sort by numeric id
    data.sort((a,b) => Number(a.id) - Number(b.id));
    return data;
  }

  function card(it) {
    const el = document.createElement('div');
    el.className = 'card';
    el.tabIndex = 0;

    const top = document.createElement('div');
    top.className = 'card__top';

    const badge = document.createElement('div');
    badge.className = 'badge';
    badge.textContent = `#${it.id}`;

    const type = document.createElement('div');
    type.className = 'pill';
    type.textContent = it.type || '—';

    top.appendChild(badge);
    top.appendChild(type);

    const name = document.createElement('div');
    name.className = 'name';
    name.textContent = it.name || '(без названия)';

    const meta = document.createElement('div');
    meta.className = 'meta';

    const city = document.createElement('div');
    city.className = 'pill';
    city.textContent = it.city || '—';

    meta.appendChild(city);

    el.appendChild(top);
    el.appendChild(name);
    el.appendChild(meta);

    const onOpen = () => openPrint(it);
    el.addEventListener('click', onOpen);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); }
    });

    return el;
  }

  function render(items) {
    gridEl.innerHTML = '';
    const frag = document.createDocumentFragment();
    for (const it of items) frag.appendChild(card(it));
    gridEl.appendChild(frag);
  }

  function showModal() {
    modal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function hideModal() {
    modal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    frame.src = 'about:blank';
    currentPdfUrl = '';
  }

  function openPrint(it) {
    const pdfPath = it.pdf || `labels/${it.id}.pdf`;
    currentPdfUrl = `./${pdfPath}?${cacheBuster()}`;
    modalTitle.textContent = `Печать: #${it.id} — ${it.name || ''}`;
    frame.src = currentPdfUrl;
    openPdf.href = currentPdfUrl;
    showModal();
    setTimeout(() => { printBtn.focus(); }, 50);
  }

  function doPrint() {
    if (!currentPdfUrl) return;
    try {
      frame.contentWindow.focus();
      frame.contentWindow.print();
    } catch (e) {
      window.open(currentPdfUrl, '_blank', 'noopener');
    }
  }

  refreshEl.addEventListener('click', () => boot(true));
  backdrop.addEventListener('click', hideModal);
  closeBtn.addEventListener('click', hideModal);
  printBtn.addEventListener('click', doPrint);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') hideModal();
    if (e.key === 'Enter' && modal.getAttribute('aria-hidden') === 'false') { e.preventDefault(); doPrint(); }
  });

  async function boot() {
    try {
      statusEl.textContent = 'Загрузка…';
      gridEl.innerHTML = '';
      const meta = await loadMeta();
      if (updatedAtEl) {
        const ts = meta && meta.generated_at ? String(meta.generated_at) : "";
        if (meta && meta.generated_at) { const raw = String(meta.generated_at).replace("T"," "); const tz = meta.timezone ? " ("+meta.timezone+")" : ""; updatedAtEl.textContent = raw + tz; } else { updatedAtEl.textContent = "—"; }
      }
      all = await loadIndex();
      render(all);
      statusEl.textContent = `Всего позиций: ${all.length}`;
    } catch (err) {
      console.error(err);
      statusEl.textContent = `Ошибка: ${err.message || err}`;
    }
  }

  boot();
})();
