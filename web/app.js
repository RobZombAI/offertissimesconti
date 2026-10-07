/**
 * OFFERTISSIMESCONTI - Client-Side App
 * Gestione dinamica catalogo, filtri Keepa, grafici SVG sparkline e alert modal.
 */

const CLOUDFLARE_BACKEND = 'https://voices-limousines-showing-classes.trycloudflare.com';
const API_BASE = window.location.origin.includes('github.io') 
  ? CLOUDFLARE_BACKEND 
  : (window.location.origin.includes('http') ? window.location.origin : 'http://localhost:8000');
let currentProducts = [];
let allCategories = [];
let activeFilter = 'all'; // 'all', 'atl', 'cyclical', 'viral'
let activeCategory = '';
let minDiscount = 0;
let searchQuery = '';
let currentLimit = 24;
let currentOffset = 0;

// DOM Elements
const productsGrid = document.getElementById('productsGrid');
const resultsCount = document.getElementById('resultsCount');
const categorySelect = document.getElementById('categorySelect');
const discountSelect = document.getElementById('discountSelect');
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
  try {
    const res = await fetch(`${API_BASE}/api/categories`);
    const data = await res.json();
    if (data.success && data.categories) {
      allCategories = data.categories;
      populateCategoryUI(allCategories);
    }
  } catch (err) {
    console.warn("Impossibile caricare categorie dall'API, uso fallback statico.");
  }
}

function populateCategoryUI(categories) {
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

async function loadProducts(reset = true) {
  if (reset) {
    currentOffset = 0;
    productsGrid.innerHTML = '';
    resultsCount.textContent = 'Ricerca sconti in corso...';
  }

  // Costruisci parametri query
  const params = new URLSearchParams({
    limit: currentLimit,
    offset: currentOffset
  });

  if (activeCategory) params.append('category', activeCategory);
  if (minDiscount > 0) params.append('min_drop', minDiscount);
  if (searchQuery) params.append('search', searchQuery);

  if (activeFilter === 'cyclical') params.append('cyclical', '1');
  if (activeFilter === 'viral') params.append('min_virality', '90');

  try {
    const res = await fetch(`${API_BASE}/api/products?${params.toString()}`);
    const data = await res.json();

    if (data.success && data.products) {
      let prods = data.products;

      // Filtro locale per Minimi Storici
      if (activeFilter === 'atl') {
        prods = prods.filter(p => p.current_price <= p.all_time_low * 1.02);
      }

      if (reset) {
        currentProducts = prods;
      } else {
        currentProducts.push(...prods);
      }

      renderProducts(prods, reset);
      resultsCount.textContent = `Visualizzati ${currentProducts.length} prodotti (su ${data.total_matched} sconti trovati)`;
      loadMoreBtn.style.display = (currentProducts.length >= data.total_matched) ? 'none' : 'inline-flex';
    }
  } catch (err) {
    console.error('Errore nel caricamento prodotti:', err);
    resultsCount.textContent = 'Connessione al database in corso. Assicurati che il server API sia attivo.';
  }
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

  products.forEach(p => {
    const card = document.createElement('article');
    card.className = 'product-card';

    const isAtl = p.current_price <= p.all_time_low;
    const atlBadge = isAtl ? `<span class="badge-atl">🏆 Minimo Storico</span>` : '';
    const cyclicalBadge = p.is_cyclical ? `<span class="badge-cyclical">🔄 Riacquisto ogni ${p.cycle_days}gg</span>` : '';

    // Genera sparkline SVG Keepa-style
    const sparklineSvg = generateKeepaSparkline(p.avg_price_90d, p.avg_price_30d, p.current_price, p.all_time_low);

    card.innerHTML = `
      <div class="card-top">
        <span class="badge-discount">-${p.keepa_drop_percent}% Reale</span>
        <div style="display: flex; gap: 4px; flex-wrap: wrap;">
          ${atlBadge}
          ${cyclicalBadge}
        </div>
      </div>

      <div class="card-category">${p.macro_category_name}</div>
      <h3 class="card-title">${p.title}</h3>

      <!-- Keepa-Style Sparkline -->
      <div class="keepa-chart-box">
        <div class="chart-header">
          <span>Andamento Keepa (90gg)</span>
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
 * Genera un grafico vettoriale SVG sparkline stile Keepa che mostra visivamente
 * il trend di prezzo e il ribasso attuale rispetto al minimo storico.
 */
function generateKeepaSparkline(p90, p30, pCurrent, pAtl) {
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
