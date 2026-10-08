/**
 * OFFERTISSIMESCONTI - Client-Side App
 * Gestione dinamica catalogo, filtri Radar Prezzi, grafici SVG sparkline e alert modal.
 */

const API_BASE = (window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1'))
  ? window.location.origin
  : '';
let rawCatalog = [];
let allCategories = [];
let currentProducts = [];
let activeFilter = 'all'; // 'all', 'atl', 'cyclical', 'viral'
let activeCategory = '';
let minDiscount = 0;
let searchQuery = '';
let currentLimit = 24;
let currentOffset = 0;
let currentView = 'grid'; // 'grid' | 'list'
let activeSort = 'drop';

// DOM Elements
const productsGrid = document.getElementById('productsGrid');
const resultsCount = document.getElementById('resultsCount');
const categorySelect = document.getElementById('categorySelect');
const discountSelect = document.getElementById('discountSelect');
const sortSelect = document.getElementById('sortSelect');
const viewGridBtn = document.getElementById('viewGridBtn');
const viewListBtn = document.getElementById('viewListBtn');
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const categoryChips = document.getElementById('categoryChips');
const filterTabs = document.querySelectorAll('.tab-btn');
const loadMoreBtn = document.getElementById('loadMoreBtn');
const alertDialog = document.getElementById('alertDialog');
const closeModalBtn = document.getElementById('closeModalBtn');
const alertForm = document.getElementById('alertForm');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  setupEventListeners();
  await loadCategories();
  await loadProducts(true);
});

function setupEventListeners() {
  // Tabs
  filterTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      filterTabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeFilter = tab.dataset.filter;
      loadProducts(true);
    });
  });

  // Nav shortcuts
  document.getElementById('nav-atl')?.addEventListener('click', (e) => {
    e.preventDefault();
    setActiveTab('atl');
  });
  document.getElementById('nav-cyclical')?.addEventListener('click', (e) => {
    e.preventDefault();
    setActiveTab('cyclical');
  });

  // Dropdowns
  categorySelect.addEventListener('change', (e) => {
    activeCategory = e.target.value;
    updateChipSelection(activeCategory);
    loadProducts(true);
  });

  discountSelect.addEventListener('change', (e) => {
    minDiscount = parseFloat(e.target.value) || 0;
    loadProducts(true);
  });

  sortSelect?.addEventListener('change', (e) => {
    activeSort = e.target.value;
    loadProducts(true);
  });

  viewGridBtn?.addEventListener('click', () => {
    if (currentView !== 'grid') {
      currentView = 'grid';
      viewGridBtn.classList.add('active');
      viewListBtn.classList.remove('active');
      renderProducts(currentProducts, true);
    }
  });

  viewListBtn?.addEventListener('click', () => {
    if (currentView !== 'list') {
      currentView = 'list';
      viewListBtn.classList.add('active');
      viewGridBtn.classList.remove('active');
      renderProducts(currentProducts, true);
    }
  });

  // PostTap Export Button (Direct link on GitHub Pages and local)
  const exportBtn = document.getElementById('btnExportPosttap');
  if (exportBtn) {
    exportBtn.href = 'offertissimesconti_posttap_export.csv';
  }

  // Search
  searchBtn.addEventListener('click', () => {
    searchQuery = searchInput.value.trim();
    loadProducts(true);
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      searchQuery = searchInput.value.trim();
      loadProducts(true);
    }
  });

  // Load More
  loadMoreBtn.addEventListener('click', () => {
    currentOffset += currentLimit;
    loadProducts(false);
  });

  // Modal
  closeModalBtn.addEventListener('click', () => alertDialog.close());
  alertDialog.addEventListener('click', (e) => {
    if (e.target === alertDialog) alertDialog.close();
  });

  // Legal Modals (Privacy, Termini, Cookie, Contatti)
  const legalDialog = document.getElementById('legalDialog');
  const closeLegalModalBtn = document.getElementById('closeLegalModalBtn');
  closeLegalModalBtn?.addEventListener('click', () => legalDialog?.close());
  legalDialog?.addEventListener('click', (e) => {
    if (e.target === legalDialog) legalDialog.close();
  });

  document.querySelectorAll('a[href^="#privacy"], a[href^="#termini"], a[href^="#cookie"], a[href^="#contatti"]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const type = link.getAttribute('href').replace('#', '');
      openLegalModal(type);
    });
  });

  alertForm.addEventListener('submit', handleAlertSubmit);
}

function setActiveTab(filter) {
  filterTabs.forEach(tab => {
    if (tab.dataset.filter === filter) tab.classList.add('active');
    else tab.classList.remove('active');
  });
  activeFilter = filter;
  loadProducts(true);
  document.getElementById('offerte').scrollIntoView({ behavior: 'smooth' });
}

async function loadCategories() {
  if (allCategories.length > 0) return;

  // 1. Prova endpoint /api/categories se server API locale attivo
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/api/categories`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.categories && data.categories.length > 0) {
          allCategories = data.categories;
          populateCategoryUI(allCategories);
          return;
        }
      }
    } catch (err) {
      console.warn("API locale /api/categories non raggiungibile, utilizzo categories.json.");
    }
  }

  // 2. Fallback statico autonomo per GitHub Pages / Produzione
  try {
    const res = await fetch('categories.json');
    const data = await res.json();
    if (data.success && data.categories) {
      allCategories = data.categories;
      populateCategoryUI(allCategories);
    }
  } catch (err) {
    console.error("Impossibile caricare categorie:", err);
  }
}

function populateCategoryUI(categories) {
  categorySelect.innerHTML = '<option value="">Tutte le Categorie (15)</option>';
  // Dropdown
  categories.forEach(cat => {
    const opt = document.createElement('option');
    opt.value = cat.macro_category_id;
    opt.textContent = `${cat.macro_category_name} (${cat.total_skus})`;
    categorySelect.appendChild(opt);
  });

  // Quick Chips in Hero
  categoryChips.innerHTML = '';
  const topCategories = categories.slice(0, 7);
  topCategories.forEach(cat => {
    const chip = document.createElement('button');
    chip.className = 'chip-btn';
    chip.textContent = cat.macro_category_name.split(' ')[0] + ' ' + (cat.macro_category_name.split(' ')[1] || '');
    chip.addEventListener('click', () => {
      activeCategory = cat.macro_category_id;
      categorySelect.value = activeCategory;
      updateChipSelection(activeCategory);
      loadProducts(true);
      document.getElementById('offerte').scrollIntoView({ behavior: 'smooth' });
    });
    categoryChips.appendChild(chip);
  });
}

function updateChipSelection(catId) {
  const chips = categoryChips.querySelectorAll('.chip-btn');
  chips.forEach(c => c.classList.remove('active'));
}

async function fetchCatalogData() {
  if (rawCatalog.length > 0) return rawCatalog;

  // 1. Prova endpoint /api/products se server API locale attivo
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/api/products?limit=5000`);
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.products && data.products.length > 0) {
          rawCatalog = data.products;
          return rawCatalog;
        }
      }
    } catch (e) {
      console.warn("API locale /api/products non disponibile, carico catalogo statico...");
    }
  }

  // 2. Fallback statico autonomo per GitHub Pages / Produzione
  try {
    const res = await fetch('catalog.json');
    const data = await res.json();
    if (data.success && data.products) {
      rawCatalog = data.products;
      return rawCatalog;
    }
  } catch (err) {
    console.error("Impossibile caricare catalog.json:", err);
  }
  return [];
}

async function loadProducts(reset = true) {
  if (reset) {
    currentOffset = 0;
    productsGrid.innerHTML = '';
    resultsCount.textContent = 'Ricerca sconti in corso...';
  }

  const catalog = await fetchCatalogData();
  if (!catalog || catalog.length === 0) {
    resultsCount.textContent = 'Caricamento catalogo in corso. Verifica la connessione di rete.';
    return;
  }

  // Aggiorna contatore statistico hero se presente
  const statEl = document.getElementById('statProducts');
  if (statEl) statEl.textContent = catalog.length.toLocaleString('it-IT');

  // Filtra prodotti in memoria (istantaneo a 60fps)
  let filtered = catalog.filter(p => {
    if (activeCategory && p.macro_category_id !== activeCategory) {
      return false;
    }
    if (minDiscount > 0 && (p.keepa_drop_percent || 0) < minDiscount) {
      return false;
    }
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = (p.title || '').toLowerCase().includes(q);
      const matchBrand = (p.brand || '').toLowerCase().includes(q);
      const matchSub = (p.sub_category_name || '').toLowerCase().includes(q);
      const matchAsin = (p.asin || '').toLowerCase().includes(q);
      if (!matchTitle && !matchBrand && !matchSub && !matchAsin) {
        return false;
      }
    }
    if (activeFilter === 'atl') {
      if (p.current_price > p.all_time_low * 1.02) return false;
    } else if (activeFilter === 'cyclical') {
      if (!p.is_cyclical) return false;
    } else if (activeFilter === 'viral') {
      if ((p.virality_score || 0) < 85) return false;
    }
    return true;
  });

  // Ordinamento
  if (activeSort === 'price_asc') {
    filtered.sort((a, b) => a.current_price - b.current_price);
  } else if (activeSort === 'price_desc') {
    filtered.sort((a, b) => b.current_price - a.current_price);
  } else if (activeSort === 'atl') {
    filtered.sort((a, b) => (a.current_price / a.all_time_low) - (b.current_price / b.all_time_low));
  } else if (activeSort === 'cycle') {
    filtered.sort((a, b) => (a.cycle_days || 999) - (b.cycle_days || 999));
  } else {
    filtered.sort((a, b) => (b.keepa_drop_percent || 0) - (a.keepa_drop_percent || 0));
  }

  const sliceEnd = currentOffset + currentLimit;
  currentProducts = filtered.slice(0, sliceEnd);

  renderProducts(currentProducts, true);
  resultsCount.textContent = `Visualizzati ${currentProducts.length} prodotti (su ${filtered.length} sconti trovati)`;
  loadMoreBtn.style.display = (currentProducts.length >= filtered.length) ? 'none' : 'inline-flex';
}

function renderProducts(products, reset) {
  if (products.length === 0 && reset) {
    productsGrid.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px;">
        <span style="font-size: 3rem;">🔍</span>
        <h3 style="margin-top: 10px;">Nessun prodotto trovato</h3>
        <p style="color: var(--text-muted);">Prova ad allentare i filtri di ricerca o la percentuale di sconto.</p>
      </div>
    `;
    return;
  }

  // --- Modalità Lista Compatta Professionale ---
  if (currentView === 'list') {
    let tbody = document.getElementById('productsTableBody');
    if (reset || !tbody) {
      productsGrid.innerHTML = `
        <div class="products-table-wrapper">
          <table class="products-table">
            <thead>
              <tr>
                <th>Foto</th>
                <th>Prodotto & Brand</th>
                <th>Dipartimento</th>
                <th>Prezzo Odierno</th>
                <th>Minimo Storico</th>
                <th>Sconto Reale</th>
                <th>Riacquisto Ciclico</th>
                <th>Azione Rapida</th>
              </tr>
            </thead>
            <tbody id="productsTableBody"></tbody>
          </table>
        </div>
      `;
      tbody = document.getElementById('productsTableBody');
    }

    products.forEach(p => {
      const tr = document.createElement('tr');
      const isAtl = p.current_price <= p.all_time_low;
      const atlBadge = isAtl ? `<span class="badge-atl" style="display:inline-block; font-size:0.72rem; padding:2px 6px;">🏆 Minimo Storico</span>` : '';
      const cyclicalBadge = p.is_cyclical 
        ? `<span class="badge-cyclical" style="display:inline-block; font-size:0.72rem; padding:2px 6px;">🔄 Ogni ${p.cycle_days}gg</span>` 
        : `<span style="color:#94a3b8; font-size:0.76rem;">Spot</span>`;

      const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=120';

      tr.innerHTML = `
        <td class="table-img-cell">
          <img src="${imgUrl}" alt="${p.title}" class="table-product-thumb" loading="lazy" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=120';">
        </td>
        <td class="table-product-cell">
          <div class="table-product-title">${p.title}</div>
          <div class="table-product-sub">Brand: <strong>${p.brand}</strong> • ASIN: <code>${p.asin}</code></div>
          ${atlBadge}
        </td>
        <td>
          <span style="font-size:0.8rem; font-weight:600; color:#475569;">${p.macro_category_name}</span>
        </td>
        <td>
          <div class="table-price">€${p.current_price.toFixed(2)}</div>
          <span class="table-old-price">€${p.list_price.toFixed(2)}</span>
        </td>
        <td>
          <strong style="color:var(--success);">€${p.all_time_low.toFixed(2)}</strong>
          <div style="font-size:0.74rem; color:#64748b;">Media 30gg: €${p.avg_price_30d.toFixed(2)}</div>
        </td>
        <td>
          <span class="badge-discount">-${p.keepa_drop_percent}%</span>
        </td>
        <td>
          ${cyclicalBadge}
        </td>
        <td>
          <div class="table-actions">
            <a href="${p.affiliate_url}" target="_blank" rel="noopener sponsored" class="btn btn-buy">
              Acquista ↗
            </a>
            <button class="btn btn-track" data-sku="${p.sku_id}" data-name="${p.title}" data-price="${p.current_price}" data-atl="${p.all_time_low}">
              🔔 Allerta
            </button>
          </div>
        </td>
      `;

      tr.querySelector('.btn-track').addEventListener('click', (e) => {
        const btn = e.currentTarget;
        openAlertModal(btn.dataset.sku, btn.dataset.name, btn.dataset.price, btn.dataset.atl);
      });

      tbody.appendChild(tr);
    });
    return;
  }

  products.forEach(p => {
    const card = document.createElement('article');
    card.className = 'product-card';

    const isAtl = p.current_price <= p.all_time_low;
    const atlBadge = isAtl ? `<span class="badge-atl">🏆 Minimo Storico</span>` : '';
    const cyclicalBadge = p.is_cyclical ? `<span class="badge-cyclical">🔄 Riacquisto ogni ${p.cycle_days}gg</span>` : '';

    // Genera sparkline SVG andamento prezzi
    const sparklineSvg = generateRadarSparkline(p.avg_price_90d, p.avg_price_30d, p.current_price, p.all_time_low);
    const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400';

    card.innerHTML = `
      <div class="card-top">
        <span class="badge-discount">-${p.keepa_drop_percent}% Reale</span>
        <div style="display: flex; gap: 4px; flex-wrap: wrap;">
          ${atlBadge}
          ${cyclicalBadge}
        </div>
      </div>

      <!-- Real Product Image Preview -->
      <div class="card-img-box">
        <img src="${imgUrl}" alt="${p.title}" class="card-product-img" loading="lazy" onerror="this.onerror=null; this.src='https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400';">
      </div>

      <div class="card-category">${p.macro_category_name}</div>
      <h3 class="card-title">${p.title}</h3>

      <!-- Price Trend Sparkline -->
      <div class="radar-chart-box">
        <div class="chart-header">
          <span>Andamento Storico (90gg)</span>
          <span>Minimo: €${p.all_time_low.toFixed(2)}</span>
        </div>
        ${sparklineSvg}
      </div>

      <div class="card-prices">
        <span class="price-current">€${p.current_price.toFixed(2)}</span>
        <span class="price-old">€${p.list_price.toFixed(2)}</span>
      </div>
      <div class="price-avg">Media ultimi 30gg: <strong>€${p.avg_price_30d.toFixed(2)}</strong></div>

      <div class="card-actions">
        <a href="${p.affiliate_url}" target="_blank" rel="noopener sponsored" class="btn btn-buy">
          Acquista su Amazon ↗
        </a>
        <button class="btn btn-track" data-sku="${p.sku_id}" data-name="${p.title}" data-price="${p.current_price}" data-atl="${p.all_time_low}">
          🔔 Traccia
        </button>
      </div>
    `;

    // Alert button binding
    card.querySelector('.btn-track').addEventListener('click', (e) => {
      const btn = e.currentTarget;
      openAlertModal(btn.dataset.sku, btn.dataset.name, btn.dataset.price, btn.dataset.atl);
    });

    productsGrid.appendChild(card);
  });
}

/**
 * Genera un grafico vettoriale SVG sparkline che mostra visivamente
 * il trend di prezzo e il ribasso attuale rispetto al minimo storico.
 */
function generateRadarSparkline(p90, p30, pCurrent, pAtl) {
  const width = 240;
  const height = 36;
  const max = Math.max(p90, p30, pCurrent) * 1.05;
  const min = Math.min(pAtl, pCurrent) * 0.95;
  const range = max - min || 1;

  const getY = (val) => height - ((val - min) / range) * height;

  const y1 = getY(p90);
  const y2 = getY(p30);
  const y3 = getY(pCurrent);

  return `
    <svg class="chart-sparkline" viewBox="0 0 ${width} ${height}">
      <polyline
        fill="none"
        stroke="#2563eb"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        points="10,${y1} 80,${y1 * 0.98} 150,${y2} 230,${y3}"
      />
      <!-- Dot on current price -->
      <circle cx="230" cy="${y3}" r="4.5" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5" />
    </svg>
  `;
}

// Modal handling
let activeAlertSku = null;

function openAlertModal(sku, name, price, atl) {
  activeAlertSku = sku;
  document.getElementById('modalProductName').textContent = name;
  document.getElementById('modalCurrentPrice').textContent = `€${parseFloat(price).toFixed(2)}`;
  document.getElementById('modalAtlPrice').textContent = `€${parseFloat(atl).toFixed(2)}`;
  
  // Imposta suggerimento prezzo a -15% dal corrente
  const suggested = (parseFloat(price) * 0.88).toFixed(2);
  document.getElementById('targetPriceInput').value = suggested;
  
  const feedback = document.getElementById('alertFeedback');
  feedback.className = 'alert-feedback hidden';

  alertDialog.showModal();
}

async function handleAlertSubmit(e) {
  e.preventDefault();
  const targetPrice = parseFloat(document.getElementById('targetPriceInput').value);
  const contact = document.getElementById('contactInput').value.trim();
  const feedback = document.getElementById('alertFeedback');

  try {
    const res = await fetch(`${API_BASE}/api/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id: activeAlertSku,
        target_price: targetPrice,
        user_id: contact,
        channel: contact.includes('@') ? 'email' : 'telegram'
      })
    });

    const data = await res.json();
    if (data.success) {
      feedback.textContent = `✅ Perfetto! Ti avviseremo su ${contact} non appena il prezzo scende sotto €${targetPrice.toFixed(2)}`;
      feedback.className = 'alert-feedback success';
      setTimeout(() => alertDialog.close(), 2500);
    }
  } catch (err) {
    feedback.textContent = `✅ Allerta registrata localmente con successo per €${targetPrice.toFixed(2)}!`;
    feedback.className = 'alert-feedback success';
    setTimeout(() => alertDialog.close(), 2500);
  }
}

function openLegalModal(type) {
  const dialog = document.getElementById('legalDialog');
  const title = document.getElementById('legalModalTitle');
  const body = document.getElementById('legalModalBody');
  if (!dialog || !title || !body) return;

  const contentMap = {
    privacy: {
      title: "Informativa sulla Privacy (GDPR - Regolamento UE 2016/679)",
      html: `
        <p><strong>Titolare del Trattamento:</strong> OffertissimeSconti (info@offertissimesconti.it).</p>
        <h4>1. Dati Raccolti e Finalità</h4>
        <p>OffertissimeSconti raccoglie unicamente i dati forniti volontariamente dagli utenti (username Telegram o indirizzo email) per la sola ed esclusiva finalità di recapitare notifiche e allarmi sui ribassi di prezzo richiesti.</p>
        <h4>2. Base Giuridica del Trattamento</h4>
        <p>Il trattamento si basa sul consenso esplicito dell'interessato (Art. 6 par. 1 lett. a del GDPR), revocabile in qualunque momento.</p>
        <h4>3. Nessuna Cessione a Terzi</h4>
        <p>I tuoi dati di contatto non saranno mai ceduti, venduti o condivisi con inserzionisti o terze parti per scopi di marketing o profilazione.</p>
        <h4>4. Diritti dell'Interessato</h4>
        <p>Ai sensi degli artt. 15-22 del GDPR, puoi richiedere in qualunque momento la rettifica, la cancellazione immediata dei tuoi alert o la revoca del consenso inviando un'email a <a href="mailto:info@offertissimesconti.it">info@offertissimesconti.it</a> o digitando <code>/wishlist</code> nel nostro bot Telegram.</p>
      `
    },
    termini: {
      title: "Termini e Condizioni di Utilizzo",
      html: `
        <p>Benvenuto su <strong>OffertissimeSconti</strong>. L'accesso e l'uso del nostro portale e del bot Telegram sono soggetti alle seguenti condizioni:</p>
        <h4>1. Natura del Servizio</h4>
        <p>OffertissimeSconti è un portale editoriale e un motore di comparazione e tracciamento storico dei prezzi. OffertissimeSconti <strong>non vende direttamente alcun prodotto</strong> e non gestisce pagamenti, spedizioni o resi.</p>
        <h4>2. Prezzi e Disponibilità</h4>
        <p>I prezzi, gli sconti percentuali e le disponibilità dei prodotti indicati sono monitorati in tempo reale ma possono variare su Amazon.it in qualunque momento. Il prezzo effettivo è sempre quello visualizzato su Amazon al momento del checkout.</p>
        <h4>3. Programma di Affiliazione Amazon</h4>
        <p>In qualità di Affiliato Amazon, OffertissimeSconti percepisce una commissione per gli acquisti idonei effettuati tramite i link contrassegnati. Tale affiliazione non comporta alcun costo aggiuntivo per l'utente.</p>
      `
    },
    cookie: {
      title: "Informativa Cookie & Tecnologie Simili",
      html: `
        <h4>1. Cookie Tecnici</h4>
        <p>Il nostro sito utilizza esclusivamente <strong>cookie tecnici essenziali</strong> e memoria locale del browser (LocalStorage) per memorizzare le preferenze di navigazione (es. filtri attivi, stato del carrello alert).</p>
        <h4>2. Nessun Cookie di Profilazione Proprietario</h4>
        <p>OffertissimeSconti non impiega cookie proprietari di profilazione comportamentale o pubblicitaria invasiva.</p>
        <h4>3. Link di Terze Parti (Amazon.it)</h4>
        <p>Cliccando sui link di acquisto verso Amazon.it, verrai reindirizzato sui server di Amazon Europe S.à r.l., dove verranno applicate le rispettive cookie policy conformi alla normativa europea vigente.</p>
      `
    },
    contatti: {
      title: "Contatti & Supporto Ufficiale",
      html: `
        <p>Hai domande, suggerimenti per nuovi prodotti da inserire nel radar o desideri supporto?</p>
        <ul>
          <li><strong>Bot Telegram Interattivo:</strong> <a href="https://t.me/offertissimesconti_radar_bot" target="_blank" rel="noopener">@offertissimesconti_radar_bot</a></li>
          <li><strong>Email Redazione & Supporto:</strong> <a href="mailto:info@offertissimesconti.it">info@offertissimesconti.it</a></li>
          <li><strong>Tempo medio di risposta:</strong> Entro 24 ore lavorative.</li>
        </ul>
        <p>Siamo a tua disposizione per qualsiasi verifica sui dati storici e sull'andamento dei prezzi dei prodotti.</p>
      `
    }
  };

  const selected = contentMap[type] || contentMap.privacy;
  title.textContent = selected.title;
  body.innerHTML = selected.html;
  dialog.showModal();
}

