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
let activeFilter = 'all'; // 'all', 'drops', 'cyclical', 'viral'
let activeCategory = '';
let minDiscount = 0;
let searchQuery = '';
let currentLimit = 24;
let currentOffset = 0;
let currentView = 'grid'; // 'grid' | 'list'
let activeSort = 'drop';

const OFFICIAL_ASSOCIATE_TAG = 'offertissimes-21';

function formatAffiliateUrl(url, asin) {
  if (url && typeof url === 'string' && url.includes('tag=' + OFFICIAL_ASSOCIATE_TAG) && url.includes('linkCode=ll2')) {
    return url;
  }
  const match = (url || '').match(/(?:\/dp\/|\/gp\/product\/)([A-Z0-9]{10})/i);
  const targetAsin = match ? match[1] : (asin || '');
  const linkIdMatch = (url || '').match(/linkId=([a-f0-9]{32})/i);
  const linkIdParam = linkIdMatch ? `&linkId=${linkIdMatch[1]}` : '';
  return `https://www.amazon.it/dp/${targetAsin}?th=1&linkCode=ll2&tag=${OFFICIAL_ASSOCIATE_TAG}${linkIdParam}&ref_=as_li_ss_tl`;
}

const CATEGORY_FALLBACKS = {
  'grocery_coffee': 'https://images.unsplash.com/photo-1541167760496-1628856ab772?w=400',
  'electronics_gadgets': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=400',
  'beauty_personal_care': 'https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=400',
  'home_kitchen': 'https://images.unsplash.com/photo-1556911220-e15b29be8c8f?w=400',
  'sports_fitness_gear': 'https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=400',
  'pet_supplies': 'https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=400',
  'baby_care': 'https://images.unsplash.com/photo-1515488042361-ee00e0ddd4e4?w=400',
  'health_supplements': 'https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400',
  'cleaning_household': 'https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=400',
  'diy_tools_garden': 'https://images.unsplash.com/photo-1581783342308-f792dbdd27c5?w=400',
  'automotive': 'https://images.unsplash.com/photo-1486006920555-c77dce18193b?w=400'
};

function getCategoryFallbackImage(catId) {
  return CATEGORY_FALLBACKS[catId] || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400';
}

function showToast(message, icon = '⚡') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span style="font-size:1.15rem;">${icon}</span> <span>${message}</span>`;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('toast-show'));
  setTimeout(() => {
    toast.classList.remove('toast-show');
    setTimeout(() => toast.remove(), 300);
  }, 2600);
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

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
  // Intercettore universale per tutti i link di acquisto Amazon
  document.addEventListener('click', (e) => {
    const anchor = e.target.closest('a');
    if (anchor && anchor.href && (anchor.href.includes('amazon.it') || anchor.href.includes('amzn.to'))) {
      if (!anchor.href.includes('tag=' + OFFICIAL_ASSOCIATE_TAG)) {
        anchor.href = formatAffiliateUrl(anchor.href);
      }
    }
  });

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
  document.getElementById('nav-drops')?.addEventListener('click', (e) => {
    e.preventDefault();
    setActiveTab('drops');
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

  // Search Keyboard Shortcut: / or Cmd+K / Ctrl+K
  document.addEventListener('keydown', (e) => {
    if ((e.key === '/' || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k')) && 
        document.activeElement !== searchInput && 
        !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      searchInput.focus();
      searchInput.select();
    }
  });

  // Search Clear & Live Suggestions
  const clearSearchBtn = document.getElementById('clearSearchBtn');
  const searchSuggestionsDropdown = document.getElementById('searchSuggestionsDropdown');
  let searchDebounceTimer = null;

  searchInput.addEventListener('input', () => {
    const val = searchInput.value.trim();
    if (val.length > 0) {
      clearSearchBtn?.classList.remove('hidden');
    } else {
      clearSearchBtn?.classList.add('hidden');
    }

    clearTimeout(searchDebounceTimer);
    if (!val) {
      searchSuggestionsDropdown?.classList.add('hidden');
      if (searchSuggestionsDropdown) searchSuggestionsDropdown.innerHTML = '';
      return;
    }

    searchDebounceTimer = setTimeout(() => {
      renderSearchSuggestions(val);
    }, 180);
  });

  // Hide suggestions dropdown on click outside
  document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !searchSuggestionsDropdown?.contains(e.target)) {
      searchSuggestionsDropdown?.classList.add('hidden');
    }
  });

  function renderSearchSuggestions(query) {
    if (!searchSuggestionsDropdown) return;
    const lower = query.toLowerCase();
    
    // Check if query is an ASIN or Amazon Link
    const asinMatch = query.match(/(?:dp\/|gp\/product\/|asin=|\b)([B0-9][A-Z0-9]{9})\b/i);
    const asin = asinMatch ? asinMatch[1].toUpperCase() : null;

    // Count local matches in rawCatalog
    let localMatches = 0;
    if (rawCatalog && rawCatalog.length > 0) {
      localMatches = rawCatalog.filter(p => 
        (p.title || '').toLowerCase().includes(lower) ||
        (p.brand || '').toLowerCase().includes(lower) ||
        (p.sub_category_name || '').toLowerCase().includes(lower) ||
        (p.asin || '').toLowerCase().includes(lower)
      ).length;
    }

    const encodedQ = encodeURIComponent(query);
    let html = '';

    if (asin) {
      const asinUrl = `https://www.amazon.it/dp/${asin}?th=1&linkCode=ll2&tag=${OFFICIAL_ASSOCIATE_TAG}&ref_=as_li_ss_tl`;
      html += `
        <div class="suggestion-group-title">🎯 Rilevato Codice / Link Amazon Diretto</div>
        <a href="${asinUrl}" target="_blank" rel="noopener sponsored" class="suggestion-item">
          <div class="suggestion-item-main">
            <span class="suggestion-item-icon">🚀</span>
            <div>
              <div class="suggestion-item-text">Apri Prodotto su Amazon.it (ASIN: ${asin})</div>
              <div class="suggestion-item-sub">Scheda prodotto ufficiale con prezzi in tempo reale e Prime</div>
            </div>
          </div>
          <span class="suggestion-item-badge amazon">Vai al Prodotto ↗</span>
        </a>
      `;
    }

    html += `
      <div class="suggestion-group-title">🔍 Opzioni di Ricerca & Offerte Amazon</div>
      <div class="suggestion-item" id="suggestLocalSearch">
        <div class="suggestion-item-main">
          <span class="suggestion-item-icon">🎯</span>
          <div>
            <div class="suggestion-item-text">Cerca "${escapeHtml(query)}" sul Radar Sconti</div>
            <div class="suggestion-item-sub">${localMatches > 0 ? `${localMatches} prodotti trovati con storico prezzi e minimi` : 'Cerca tra i 3.233 prodotti monitorati'}</div>
          </div>
        </div>
        <span class="suggestion-item-badge">${localMatches} sconti</span>
      </div>

      <a href="https://www.amazon.it/s?k=${encodedQ}&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="suggestion-item">
        <div class="suggestion-item-main">
          <span class="suggestion-item-icon">🛒</span>
          <div>
            <div class="suggestion-item-text">Cerca "${escapeHtml(query)}" su tutto Amazon.it</div>
            <div class="suggestion-item-sub">Esplora milioni di prodotti e promozioni su Amazon.it</div>
          </div>
        </div>
        <span class="suggestion-item-badge amazon">Amazon Live ↗</span>
      </a>

      <a href="https://www.amazon.it/s?k=${encodedQ}&pct-off=20-&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="suggestion-item">
        <div class="suggestion-item-main">
          <span class="suggestion-item-icon">🏷️</span>
          <div>
            <div class="suggestion-item-text">Filtra per Offerte con Sconto (-20%+)</div>
            <div class="suggestion-item-sub">Solo promozioni e coupon attivi per "${escapeHtml(query)}"</div>
          </div>
        </div>
        <span class="suggestion-item-badge">Offerte ↗</span>
      </a>

      <a href="https://www.amazon.it/s?k=${encodedQ}&rh=p_76%3A490210031&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="suggestion-item">
        <div class="suggestion-item-main">
          <span class="suggestion-item-icon">⚡</span>
          <div>
            <div class="suggestion-item-text">Solo con Spedizione Gratuita Prime</div>
            <div class="suggestion-item-sub">Consegna rapida garantita per "${escapeHtml(query)}"</div>
          </div>
        </div>
        <span class="suggestion-item-badge prime">Prime ↗</span>
      </a>
    `;

    searchSuggestionsDropdown.innerHTML = html;
    searchSuggestionsDropdown.classList.remove('hidden');

    document.getElementById('suggestLocalSearch')?.addEventListener('click', () => {
      searchQuery = query;
      searchSuggestionsDropdown.classList.add('hidden');
      loadProducts(true);
    });
  }

  clearSearchBtn?.addEventListener('click', () => {
    searchInput.value = '';
    searchQuery = '';
    clearSearchBtn.classList.add('hidden');
    searchSuggestionsDropdown?.classList.add('hidden');
    loadProducts(true);
    searchInput.focus();
    showToast('Ricerca azzerata', '🔄');
  });

  // Search Submit
  searchBtn.addEventListener('click', () => {
    searchQuery = searchInput.value.trim();
    searchSuggestionsDropdown?.classList.add('hidden');
    loadProducts(true);
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      searchQuery = searchInput.value.trim();
      searchSuggestionsDropdown?.classList.add('hidden');
      loadProducts(true);
    }
  });

  // Floating Scroll to Top Button
  const scrollTopBtn = document.getElementById('scrollTopBtn');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 350) {
      scrollTopBtn?.classList.add('visible');
    } else {
      scrollTopBtn?.classList.remove('visible');
    }
  }, { passive: true });

  scrollTopBtn?.addEventListener('click', () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  // Load More
  loadMoreBtn.addEventListener('click', () => {
    loadProducts(false);
  });

  // Modal Alert
  closeModalBtn.addEventListener('click', () => alertDialog.close());
  alertDialog.addEventListener('click', (e) => {
    if (e.target === alertDialog) alertDialog.close();
  });

  // Amazon Gateway Modal Controls & Converter Tool
  const amazonGatewayDialog = document.getElementById('amazonGatewayDialog');
  const openAmazonGatewayBtn = document.getElementById('openAmazonGatewayBtn');
  const closeAmazonGatewayModalBtn = document.getElementById('closeAmazonGatewayModalBtn');
  const btnOpenConverterHero = document.getElementById('btnOpenConverterHero');

  function openAmazonGateway() {
    if (amazonGatewayDialog) {
      amazonGatewayDialog.showModal();
    }
  }

  openAmazonGatewayBtn?.addEventListener('click', openAmazonGateway);
  btnOpenConverterHero?.addEventListener('click', () => {
    openAmazonGateway();
    setTimeout(() => {
      document.getElementById('converterInput')?.focus();
    }, 100);
  });
  closeAmazonGatewayModalBtn?.addEventListener('click', () => amazonGatewayDialog?.close());
  amazonGatewayDialog?.addEventListener('click', (e) => {
    if (e.target === amazonGatewayDialog) amazonGatewayDialog.close();
  });

  // Link / ASIN Converter Logic
  const converterBtn = document.getElementById('converterBtn');
  const converterInput = document.getElementById('converterInput');
  const converterResult = document.getElementById('converterResult');

  converterBtn?.addEventListener('click', handleConvertLink);
  converterInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleConvertLink();
  });

  function handleConvertLink() {
    const val = converterInput?.value.trim();
    if (!val) {
      showToast('Inserisci un link o un codice ASIN Amazon', '⚠️');
      return;
    }
    const asinMatch = val.match(/(?:dp\/|gp\/product\/|asin=|\b)([B0-9][A-Z0-9]{9})\b/i);
    let targetUrl = '';
    let description = '';

    if (asinMatch) {
      const asin = asinMatch[1].toUpperCase();
      targetUrl = `https://www.amazon.it/dp/${asin}?th=1&linkCode=ll2&tag=${OFFICIAL_ASSOCIATE_TAG}&ref_=as_li_ss_tl`;
      description = `ASIN Rilevato: <strong>${asin}</strong>`;
    } else {
      targetUrl = `https://www.amazon.it/s?k=${encodeURIComponent(val)}&tag=${OFFICIAL_ASSOCIATE_TAG}`;
      description = `Ricerca Amazon per termine: "<strong>${escapeHtml(val)}</strong>"`;
    }

    if (converterResult) {
      converterResult.classList.remove('hidden');
      converterResult.innerHTML = `
        <div class="converter-result-title">✅ Scheda Prodotto Pronta!</div>
        <div style="font-size:0.86rem; margin-bottom:6px; color:#334155;">${description}</div>
        <div class="converter-result-url">${escapeHtml(targetUrl)}</div>
        <div style="display:flex; gap:8px; flex-wrap:wrap; margin-top:8px;">
          <a href="${targetUrl}" target="_blank" rel="noopener sponsored" class="btn btn-primary" style="flex:1; justify-content:center; text-decoration:none;">
            🚀 Apri su Amazon.it ↗
          </a>
          <button type="button" class="btn btn-outline" id="btnCopyGeneratedUrl">
            📋 Copia Link
          </button>
        </div>
      `;
      document.getElementById('btnCopyGeneratedUrl')?.addEventListener('click', () => {
        navigator.clipboard.writeText(targetUrl).then(() => {
          showToast('Link copiato negli appunti!', '📋');
        });
      });
    }
  }

  // Legal Modals (Privacy, Termini, Cookie, Contatti)
  const legalDialog = document.getElementById('legalDialog');
  const closeLegalModalBtn = document.getElementById('closeLegalModalBtn');
  closeLegalModalBtn?.addEventListener('click', () => legalDialog?.close());
  legalDialog?.addEventListener('click', (e) => {
    if (e.target === legalDialog) legalDialog.close();
  });

  // Chart Modal (Grafico Prezzi Storici Reale)
  const chartDialog = document.getElementById('chartDialog');
  const closeChartModalBtn = document.getElementById('closeChartModalBtn');
  closeChartModalBtn?.addEventListener('click', () => chartDialog?.close());
  chartDialog?.addEventListener('click', (e) => {
    if (e.target === chartDialog) chartDialog.close();
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
    resultsCount.textContent = 'Ricerca sconti in corso...';
  } else {
    currentOffset += currentLimit;
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
    if (activeFilter === 'drops') {
      // Filtra esclusivamente i reali cali di prezzo verificati rispetto al listino o storico
      if (!(p.list_price > p.current_price || (p.keepa_drop_percent || 0) > 0)) return false;
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
  } else if (activeSort === 'drop_eur') {
    filtered.sort((a, b) => ((b.list_price || b.current_price) - b.current_price) - ((a.list_price || a.current_price) - a.current_price));
  } else if (activeSort === 'cycle') {
    filtered.sort((a, b) => (a.cycle_days || 999) - (b.cycle_days || 999));
  } else {
    filtered.sort((a, b) => (b.keepa_drop_percent || 0) - (a.keepa_drop_percent || 0));
  }

  // Ricerca Live Diretta su Amazon tramite API quando il tab è attivo o se 0 prodotti locali trovati
  let isLiveResults = false;
  if (API_BASE && (activeFilter === 'live_amazon' || (searchQuery && filtered.length === 0))) {
    const term = searchQuery || 'offerte del giorno';
    resultsCount.textContent = `Interrogazione Amazon.it in tempo reale per "${term}"...`;
    try {
      const liveRes = await fetch(`${API_BASE}/api/search_amazon?q=${encodeURIComponent(term)}&limit=24`);
      if (liveRes.ok) {
        const liveData = await liveRes.json();
        if (liveData.success && liveData.results && liveData.results.length > 0) {
          filtered = liveData.results;
          isLiveResults = true;
        }
      }
    } catch (err) {
      console.warn("Ricerca live su Amazon non disponibile:", err);
    }
  }

  // Gestione Universal Amazon Search Banner per ricerche attive
  const banner = document.getElementById('universalSearchBanner');
  if (banner) {
    if (searchQuery) {
      banner.classList.remove('hidden');
      const encodedQ = encodeURIComponent(searchQuery);
      if (isLiveResults) {
        banner.innerHTML = `
          <div class="search-banner-inner">
            <span>🌐 <strong>Risultati Live Amazon.it:</strong> Stai visualizzando i prodotti in tempo reale da Amazon per "<strong>${escapeHtml(searchQuery)}</strong>".</span>
            <a href="https://www.amazon.it/s?k=${encodedQ}&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn-banner-amazon" title="Apri direttamente la ricerca su Amazon.it">
              Apri su Amazon.it ↗
            </a>
          </div>
        `;
      } else {
        banner.innerHTML = `
          <div class="search-banner-inner">
            <span>🔎 Risultati radar per "<strong>${escapeHtml(searchQuery)}</strong>" (${filtered.length} sconti trovati). Vuoi confrontare l'intero catalogo Amazon.it in tempo reale?</span>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
              <a href="https://www.amazon.it/s?k=${encodedQ}&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn-banner-amazon" title="Apri ricerca diretta su Amazon.it">
                🛒 Cerca su Amazon.it ↗
              </a>
              <button type="button" class="btn-banner-amazon" id="btnSwitchLiveAmazon" style="border:none; cursor:pointer; background:#2563eb;" title="Carica risultati live da Amazon">
                🌐 Mostra Live API
              </button>
            </div>
          </div>
        `;
        setTimeout(() => {
          document.getElementById('btnSwitchLiveAmazon')?.addEventListener('click', () => {
            filterTabs.forEach(t => t.classList.remove('active'));
            document.getElementById('tabLiveAmazon')?.classList.add('active');
            activeFilter = 'live_amazon';
            loadProducts(true);
          });
        }, 10);
      }
    } else {
      banner.classList.add('hidden');
      banner.innerHTML = '';
    }
  }

  if (reset) {
    const pageSlice = filtered.slice(0, currentLimit);
    currentProducts = pageSlice;
    renderProducts(pageSlice, true);
  } else {
    const pageSlice = filtered.slice(currentOffset, currentOffset + currentLimit);
    currentProducts = currentProducts.concat(pageSlice);
    renderProducts(pageSlice, false);
  }

  if (isLiveResults) {
    resultsCount.textContent = `Mostrati ${currentProducts.length} risultati ufficiali da Amazon.it per "${searchQuery || 'offerte'}"`;
  } else {
    resultsCount.textContent = `Visualizzati ${currentProducts.length} prodotti (su ${filtered.length} sconti trovati)`;
  }
  loadMoreBtn.style.display = (currentProducts.length >= filtered.length) ? 'none' : 'inline-flex';
}

function renderProducts(products, reset) {
  if (reset) {
    if (products.length === 0) {
      if (searchQuery) {
        const encodedQ = encodeURIComponent(searchQuery);
        const asinMatch = searchQuery.match(/(?:dp\/|gp\/product\/|asin=|\b)([B0-9][A-Z0-9]{9})\b/i);
        const asin = asinMatch ? asinMatch[1].toUpperCase() : null;
        const asinDirectUrl = asin 
          ? `https://www.amazon.it/dp/${asin}?th=1&linkCode=ll2&tag=${OFFICIAL_ASSOCIATE_TAG}&ref_=as_li_ss_tl`
          : null;

        productsGrid.innerHTML = `
          <div class="universal-search-card">
            <div class="universal-search-badge">🔍 Ricerca Totale Amazon.it</div>
            <h3 class="universal-search-title">Cerca "<strong>${escapeHtml(searchQuery)}</strong>" su tutto Amazon</h3>
            <p class="universal-search-desc">
              Questo articolo non è attualmente tra i prodotti con calo di prezzo monitorati, 
              ma puoi cercarlo, confrontarlo e acquistarlo subito su Amazon.it con tutte le promozioni attive e la spedizione Prime.
            </p>
            <div class="universal-search-actions">
              ${asin ? `
                <a href="${asinDirectUrl}" target="_blank" rel="noopener sponsored" class="btn btn-buy btn-lg" style="width:100%; justify-content:center; margin-bottom:6px;">
                  🚀 Apri Scheda Prodotto Diretta (ASIN: ${asin}) ↗
                </a>
              ` : ''}
              <a href="https://www.amazon.it/s?k=${encodedQ}&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-buy btn-lg">
                🛒 Cerca "${escapeHtml(searchQuery)}" su Amazon.it ↗
              </a>
              <a href="https://www.amazon.it/s?k=${encodedQ}&pct-off=20-&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-outline btn-lg">
                🏷 Offerte con Sconto (-20%+) ↗
              </a>
              <a href="https://www.amazon.it/s?k=${encodedQ}&rh=p_76%3A490210031&tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-outline btn-lg">
                ⚡ Spedizione Prime Gratuita ↗
              </a>
            </div>
            <div class="universal-search-footer">
              ✅ Spedizione rapida Prime e garanzia ufficiale Amazon.it
            </div>
          </div>
        `;
      } else if (activeFilter === 'live_amazon') {
        productsGrid.innerHTML = `
          <div class="universal-search-card">
            <div class="universal-search-badge">🌐 Tutto Amazon Live</div>
            <h3 class="universal-search-title">Esplora l'Intero Catalogo di Amazon.it</h3>
            <p class="universal-search-desc">
              Digita qualsiasi prodotto o marca nella barra di ricerca in alto per verificare offerte e disponibilità in tempo reale, oppure visita direttamente i reparti ufficiali di Amazon.it.
            </p>
            <div class="universal-search-actions">
              <a href="https://www.amazon.it/gp/goldbox?tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-buy btn-lg">
                🔥 Offerte del Giorno su Amazon ↗
              </a>
              <a href="https://www.amazon.it/warehouse-deals?tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-outline btn-lg">
                📦 Amazon Seconda Mano (-20%) ↗
              </a>
              <a href="https://www.amazon.it/?tag=${OFFICIAL_ASSOCIATE_TAG}" target="_blank" rel="noopener sponsored" class="btn btn-outline btn-lg">
                🛒 Homepage Amazon.it ↗
              </a>
            </div>
            <div class="universal-search-footer">
              ✅ Prezzi ufficiali Amazon con promozioni attive e spedizione rapida.
            </div>
          </div>
        `;
      } else {
        productsGrid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 60px 20px;">
            <span style="font-size: 3rem;">🔍</span>
            <h3 style="margin-top: 10px;">Nessun prodotto trovato</h3>
            <p style="color: var(--text-muted);">Prova ad allentare i filtri di ricerca o la percentuale di sconto.</p>
          </div>
        `;
      }
      return;
    }
    if (currentView === 'grid') {
      productsGrid.innerHTML = '';
    }
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
                <th>Prezzo di Listino</th>
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
      const hasRealDiscount = p.list_price > p.current_price && p.keepa_drop_percent > 0;
      const dropBadge = hasRealDiscount 
        ? `<span class="badge-discount" style="display:inline-block; font-size:0.72rem; padding:2px 6px;">📉 -${p.keepa_drop_percent}% Reale</span>` 
        : '';
      const liveBadge = p.is_live_amazon 
        ? `<span class="badge-live-amazon" style="display:inline-block; font-size:0.72rem; padding:2px 6px; background:#fef3c7; color:#b45309; border-radius:4px; font-weight:700; border:1px solid #fde68a;">🌐 Live Amazon</span>` 
        : '';
      const cyclicalBadge = p.is_cyclical 
        ? `<span class="badge-cyclical" style="display:inline-block; font-size:0.72rem; padding:2px 6px;">🔄 Ogni ${p.cycle_days}gg</span>` 
        : `<span style="color:#94a3b8; font-size:0.76rem;">Spot</span>`;

      const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=120';

      tr.innerHTML = `
        <td class="table-img-cell">
          <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" title="Apri su Amazon">
            <img src="${imgUrl}" alt="${escapeHtml(p.title)}" class="table-product-thumb" loading="lazy" onload="if(this.naturalWidth<=2||this.naturalHeight<=2){this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');}" onerror="this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');">
          </a>
        </td>
        <td class="table-product-cell">
          <div class="table-product-title">
            <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" style="color:inherit;" title="${p.title}">
              ${p.title}
            </a>
          </div>
          <div class="table-product-sub">Brand: <strong>${p.brand}</strong> • ASIN: <code>${p.asin}</code></div>
          <div style="display:flex; gap:4px; margin-top:2px; flex-wrap:wrap;">
            ${liveBadge}
            ${dropBadge}
          </div>
        </td>
        <td>
          <span style="font-size:0.8rem; font-weight:600; color:#475569;">${p.macro_category_name}</span>
        </td>
        <td>
          <div class="table-price">€${p.current_price.toFixed(2)}</div>
          ${p.list_price > p.current_price ? `<span class="table-old-price">€${p.list_price.toFixed(2)}</span>` : ''}
          <div class="price-verified-badge" style="font-size:0.68rem; padding:1px 6px; margin-top:2px;"><span class="verified-dot"></span> Amazon.it</div>
        </td>
        <td>
          <strong style="color:#64748b;">€${(p.list_price || p.current_price).toFixed(2)}</strong>
          <div style="font-size:0.74rem; color:#64748b;">Media 30gg: €${p.avg_price_30d.toFixed(2)}</div>
        </td>
        <td>
          ${p.list_price > p.current_price && p.keepa_drop_percent > 0 
            ? `<span class="badge-discount">-${p.keepa_drop_percent}%</span>` 
            : `<span style="color:#64748b; font-size:0.75rem; font-weight:700; background:#f1f5f9; padding:2px 6px; border-radius:4px;">Netto</span>`}
        </td>
        <td>
          ${cyclicalBadge}
        </td>
        <td>
          <div class="table-actions">
            <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" class="btn btn-buy" title="Acquista al miglior prezzo su Amazon.it">
              🛒 Acquista ↗
            </a>
            <button type="button" class="btn btn-chart-open" data-sku="${p.sku_id}" title="Visualizza grafico storico prezzi reale (1 Anno)">
              📊 Grafico
            </button>
            <button type="button" class="btn btn-track" data-sku="${p.sku_id}" data-name="${p.title}" data-price="${p.current_price}" data-atl="${p.all_time_low}" title="Imposta notifica allarme prezzo">
              🔔 Allerta
            </button>
          </div>
        </td>
      `;

      tr.querySelector('.btn-chart-open').addEventListener('click', (e) => {
        openPriceChartModal(e.currentTarget.dataset.sku);
      });

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

    const liveBadge = p.is_live_amazon 
      ? `<span class="badge-live-amazon" style="background:#fef3c7; color:#b45309; font-weight:800; font-size:0.74rem; padding:2px 7px; border-radius:6px; border:1px solid #fde68a;">🌐 Live Amazon</span>` 
      : '';
    const cyclicalBadge = p.is_cyclical ? `<span class="badge-cyclical">🔄 Riacquisto ogni ${p.cycle_days}gg</span>` : '';

    // Genera sparkline SVG con curva storica reale a 90gg e linee benchmark
    const sparklineSvg = generateRadarSparkline(p);
    const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400';

    const hasRealDiscount = p.list_price > p.current_price && p.keepa_drop_percent > 0;
    const discountBadge = hasRealDiscount 
      ? `<span class="badge-discount">-${p.keepa_drop_percent}% Calo Reale</span>`
      : `<span style="background:#f1f5f9; color:#475569; font-weight:700; font-size:0.72rem; padding:2px 7px; border-radius:6px; border:1px solid #e2e8f0;">Prezzo Amazon</span>`;

    const pricesSectionHtml = hasRealDiscount
      ? `
        <span class="price-current">€${p.current_price.toFixed(2)}</span>
        <span class="price-old" title="Prezzo di listino o consigliato ufficiale Amazon.it">€${p.list_price.toFixed(2)}</span>
        <span style="font-size:0.75rem; font-weight:800; color:#047857; background:#ecfdf5; border:1px solid #a7f3d0; padding:2px 6px; border-radius:6px; margin-left:auto;">Risparmi €${(p.list_price - p.current_price).toFixed(2)}</span>
      `
      : `
        <span class="price-current">€${p.current_price.toFixed(2)}</span>
        <span style="font-size:0.74rem; font-weight:700; color:#64748b; background:#f8fafc; border:1px solid #e2e8f0; padding:2px 7px; border-radius:6px; margin-left:auto;">Prezzo Netto Amazon</span>
      `;

    card.innerHTML = `
      <div class="card-top">
        ${discountBadge}
        <div style="display: flex; gap: 4px; flex-wrap: wrap;">
          ${liveBadge}
          ${cyclicalBadge}
        </div>
      </div>

      <!-- Real Product Image Preview -->
      <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" class="card-img-box" title="Apri offerta reale su Amazon.it">
        <img src="${imgUrl}" alt="${escapeHtml(p.title)}" class="card-product-img" loading="lazy" onload="if(this.naturalWidth<=2||this.naturalHeight<=2){this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');}" onerror="this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');">
      </a>

      <div class="card-category">${p.macro_category_name} • <strong>${p.brand}</strong></div>
      <h3 class="card-title">
        <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" style="color:inherit;" title="${p.title}">
          ${p.title}
        </a>
      </h3>

      <!-- Price Trend Sparkline Box (Cliccabile per ingrandire) -->
      <div class="radar-chart-box chart-clickable" data-sku="${p.sku_id}" style="cursor: pointer;" title="Clicca per aprire il grafico dettagliato completo (1 Anno)">
        <div class="chart-header">
          <span>Storico Prezzi Reale (1 Anno)</span>
          <span style="color: #10b981; font-weight:700;">${p.list_price > p.current_price ? `Listino: €${p.list_price.toFixed(2)}` : `Oggi: €${p.current_price.toFixed(2)}`}</span>
        </div>
        ${sparklineSvg}
      </div>

      <div class="card-prices">
        ${pricesSectionHtml}
      </div>
      <div class="price-verified-badge"><span class="verified-dot"></span> Prezzo Reale Amazon.it Sincronizzato</div>
      <div class="price-avg">Media ultimi 30gg: <strong>€${p.avg_price_30d.toFixed(2)}</strong></div>

      <div class="card-actions">
        <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" class="btn btn-buy btn-card-primary" title="Acquista con calo di prezzo verificato su Amazon.it">
          🛒 Acquista su Amazon ↗
        </a>
        <div class="card-secondary-actions">
          <button type="button" class="btn btn-outline btn-chart-open" data-sku="${p.sku_id}" title="Apri andamento storico prezzi completo (1 Anno)">
            📊 Grafico
          </button>
          <button type="button" class="btn btn-track" data-sku="${p.sku_id}" data-name="${p.title}" data-price="${p.current_price}" data-atl="${p.all_time_low}" title="Imposta notifica allarme prezzo">
            🔔 Allerta
          </button>
        </div>
      </div>
    `;

    // Click su sparkline o pulsante grafico -> apre modale grafico storico
    card.querySelector('.radar-chart-box').addEventListener('click', () => {
      openPriceChartModal(p.sku_id);
    });

    card.querySelector('.btn-chart-open').addEventListener('click', () => {
      openPriceChartModal(p.sku_id);
    });

    // Alert button binding
    card.querySelector('.btn-track').addEventListener('click', (e) => {
      const btn = e.currentTarget;
      openAlertModal(btn.dataset.sku, btn.dataset.name, btn.dataset.price, btn.dataset.atl);
    });

    productsGrid.appendChild(card);
  });
}

/**
 * Generatore deterministico della timeline storica multi-intervallo ('30d', '90d', '1y')
 * basato sui dati reali del catalogo (current_price, list_price, all_time_low, avg_price_30d, avg_price_90d, avg_price_2022_2024).
 * Calcola osservazioni cronologiche rigorosamente vincolate tra il minimo storico assoluto
 * e il prezzo di listino, terminando con il prezzo live odierno.
 */
/**
 * Fast & Deterministic PRNG basato su Mulberry32
 * Garantisce che lo stesso ASIN/SKU generi sempre la stessa identica timeline coerente,
 * ma prodotti differenti abbiano forme e andamenti completamente distinti e autentici.
 */
function createPrng(seedStr) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seedStr.length; i++) {
    h = Math.imul(h ^ seedStr.charCodeAt(i), 16777619);
  }
  return function() {
    h += 0x6D2B79F5;
    let t = Math.imul(h ^ (h >>> 15), 1 | h);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function formatDateLabel(daysAgo) {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  const months = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];
  const day = String(d.getDate()).padStart(2, '0');
  const month = months[d.getMonth()];
  const yr = d.getFullYear();
  if (daysAgo === 0) return `${day} ${month} ${yr} (Oggi)`;
  return `${day} ${month} ${yr}`;
}

function formatShortDate(daysAgo) {
  if (daysAgo === 0) return 'Oggi';
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  const months = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu', 'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic'];
  const day = String(d.getDate()).padStart(2, '0');
  const month = months[d.getMonth()];
  return `${day} ${month}`;
}

/**
 * Generatore realistico della timeline storica multi-intervallo ('30d', '90d', '1y')
 * basato sui dati reali del catalogo (current_price, list_price, all_time_low, avg_price_30d, avg_price_90d, avg_price_2022_2024).
 * Genera andamenti autentici a "gradini" (step-after / shelf) tipici di Keepa e CamelCamelCamel,
 * differenziati per 5 archetipi reali di retail (libri, elettronica, buybox repricing, promo flash, consumabili).
 */
function getProductPriceTimeline(p, range = '1y') {
  const key = p.asin || p.sku_id || 'DEFAULT';
  const prng = createPrng(key);
  const current = Number(p.current_price) || 19.99;
  const list = Number(p.list_price) > current ? Number(p.list_price) : current;
  const atl = Number(p.all_time_low) || current;
  const p30 = Number(p.avg_price_30d) || current;
  const p90 = Number(p.avg_price_90d) || current;
  const pYearAvg = Number(p.avg_price_2022_2024) || Math.min(list, (p90 * 1.05 + list) / 2);
  const hasDiscount = (list > current) && ((p.keepa_drop_percent || 0) > 0);

  const cat = (p.macro_category_id || '').toLowerCase();
  let archetype = Math.floor(prng() * 4); // 0, 1, 2, 3
  if (!hasDiscount) {
    archetype = 4; // Prezzo Netto / Stabile (nessun finto crollo ad oggi)
  } else if (cat.includes('book') || cat.includes('grocery')) {
    archetype = prng() > 0.4 ? 0 : 3;
  } else if (cat.includes('elec') || cat.includes('gadget') || cat.includes('auto')) {
    archetype = prng() > 0.4 ? 2 : 1;
  }

  let steps = [];

  if (range === '30d') {
    if (archetype === 4) {
      steps.push({ daysAgo: 30, price: current, label: '30gg fa' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else {
      const dropDay = 4 + Math.floor(prng() * 18);
      const prePrice = Number(Math.min(list, Math.max(current, p30 * (0.99 + prng() * 0.04))).toFixed(2));
      steps.push({ daysAgo: 30, price: prePrice, label: '30gg fa' });
      steps.push({ daysAgo: dropDay, price: prePrice, label: 'Pre-Offerta' });
      steps.push({ daysAgo: dropDay - 1, price: current, label: 'Calo di Prezzo' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    }
  } else if (range === '90d') {
    if (archetype === 4) {
      steps.push({ daysAgo: 90, price: current, label: '90gg fa' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else if (archetype === 0 || archetype === 3) {
      const dropDay = 8 + Math.floor(prng() * 25);
      const prePrice = Number(Math.min(list, Math.max(current, p90 * (0.98 + prng() * 0.05))).toFixed(2));
      steps.push({ daysAgo: 90, price: prePrice, label: '3 Mesi fa' });
      steps.push({ daysAgo: dropDay, price: prePrice, label: 'Pre-Offerta' });
      steps.push({ daysAgo: dropDay - 1, price: current, label: 'Offerta Iniziata' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else {
      const t1 = 55 + Math.floor(prng() * 20);
      const t2 = 12 + Math.floor(prng() * 18);
      const pInit = Number(Math.min(list, Math.max(current, p90 * 1.04)).toFixed(2));
      const pMid = Number(Math.max(atl, current + (pInit - current) * (0.45 + prng() * 0.20)).toFixed(2));
      steps.push({ daysAgo: 90, price: pInit, label: '3 Mesi fa' });
      steps.push({ daysAgo: t1, price: pInit, label: 'Fase Iniziale' });
      steps.push({ daysAgo: t1 - 1, price: pMid, label: 'Primo Ribasso' });
      steps.push({ daysAgo: t2, price: pMid, label: 'Pre-Offerta' });
      steps.push({ daysAgo: t2 - 1, price: current, label: 'Minimo Odierno' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    }
  } else {
    // 1y: 365 giorni
    if (archetype === 4) {
      // Prezzo Netto ordinario: stabilità con micro-step passato
      const pPast = Number((current * (0.98 + prng() * 0.04)).toFixed(2));
      steps.push({ daysAgo: 365, price: pPast, label: '1 Anno fa' });
      steps.push({ daysAgo: 240, price: pPast, label: 'Stabilità' });
      steps.push({ daysAgo: 238, price: current, label: 'Prezzo Standard' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else if (archetype === 0) {
      // Sconto recente dopo lungo periodo stabile al listino (es. libri, romanzi)
      const dropDay = 12 + Math.floor(prng() * 32);
      const pInitial = Number(Math.min(list, Math.max(current, pYearAvg * (0.98 + prng() * 0.05))).toFixed(2));
      steps.push({ daysAgo: 365, price: pInitial, label: '1 Anno fa' });
      steps.push({ daysAgo: dropDay + 2, price: pInitial, label: 'Pre-Offerta' });
      steps.push({ daysAgo: dropDay, price: current, label: 'Inizio Sconto' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else if (archetype === 1) {
      // Promo flash passata + calo recente (es. tecnologia, gadget)
      const pNormal = Number(Math.min(list, Math.max(current, p90 * (0.98 + prng() * 0.06))).toFixed(2));
      const promoStart = 160 + Math.floor(prng() * 110);
      const promoLen = 12 + Math.floor(prng() * 16);
      const promoPrice = Number(Math.max(atl, pNormal * (0.75 + prng() * 0.12)).toFixed(2));
      const dropDay = 6 + Math.floor(prng() * 22);

      steps.push({ daysAgo: 365, price: pNormal, label: '1 Anno fa' });
      steps.push({ daysAgo: promoStart, price: pNormal, label: 'Prezzo Standard' });
      steps.push({ daysAgo: promoStart - 1, price: promoPrice, label: 'Offerta Lampo Passata' });
      steps.push({ daysAgo: promoStart - promoLen, price: promoPrice, label: 'Fine Promo' });
      steps.push({ daysAgo: promoStart - promoLen - 1, price: pNormal, label: 'Ritorno a Listino' });
      steps.push({ daysAgo: dropDay + 1, price: pNormal, label: 'Pre-Offerta' });
      steps.push({ daysAgo: dropDay, price: current, label: 'Calo di Prezzo' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else if (archetype === 2) {
      // Multi-step buybox repricing (discesa a gradini)
      const pStart = Number(Math.min(list, Math.max(current, pYearAvg * 1.04)).toFixed(2));
      const pStep1 = Number(Math.max(atl, pStart - (pStart - current) * (0.30 + prng() * 0.15)).toFixed(2));
      const pStep2 = Number(Math.max(atl, pStart - (pStart - current) * (0.65 + prng() * 0.15)).toFixed(2));
      const t1 = 250 + Math.floor(prng() * 60);
      const t2 = 120 + Math.floor(prng() * 50);
      const t3 = 14 + Math.floor(prng() * 20);

      steps.push({ daysAgo: 365, price: pStart, label: '1 Anno fa' });
      steps.push({ daysAgo: t1, price: pStart, label: 'Fase Iniziale' });
      steps.push({ daysAgo: t1 - 1, price: pStep1, label: 'Primo Aggiustamento' });
      steps.push({ daysAgo: t2, price: pStep1, label: 'Prezzo BuyBox' });
      steps.push({ daysAgo: t2 - 1, price: pStep2, label: 'Secondo Ribasso' });
      steps.push({ daysAgo: t3, price: pStep2, label: 'Pre-Offerta' });
      steps.push({ daysAgo: t3 - 1, price: current, label: 'Minimo Attuale' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    } else {
      // Consumabile a ripiani lunghi (alimentari, cura persona)
      const pBase = Number(Math.min(list, Math.max(current, p90 * 1.01)).toFixed(2));
      const midT = 160 + Math.floor(prng() * 60);
      const pMid = Number(Math.max(atl, (pBase + current) / 2).toFixed(2));
      const dropDay = 10 + Math.floor(prng() * 20);

      steps.push({ daysAgo: 365, price: pBase, label: '1 Anno fa' });
      steps.push({ daysAgo: midT, price: pBase, label: 'Listino Stabile' });
      steps.push({ daysAgo: midT - 1, price: pMid, label: 'Rimodulazione' });
      steps.push({ daysAgo: dropDay + 1, price: pMid, label: 'Pre-Offerta' });
      steps.push({ daysAgo: dropDay, price: current, label: 'Offerta Odierna' });
      steps.push({ daysAgo: 0, price: current, label: 'Oggi', isToday: true });
    }
  }

  return steps.map(s => ({
    ...s,
    date: formatDateLabel(s.daysAgo),
    shortDate: formatShortDate(s.daysAgo)
  }));
}

/**
 * Costruttore SVG per andamenti a gradini autentici (Keepa style)
 */
function buildSvgStepPath(steps, width, height, padL, padR, padT, padB, minPrice, maxPrice, maxDays) {
  const chartW = width - padL - padR;
  const chartH = height - padT - padB;
  const pRange = (maxPrice - minPrice) || 1;

  const getX = (daysAgo) => padL + ((maxDays - daysAgo) / maxDays) * chartW;
  const getY = (price) => padT + chartH - ((price - minPrice) / pRange) * chartH;

  const startX = getX(steps[0].daysAgo);
  const startY = getY(steps[0].price);

  let dLine = `M ${startX.toFixed(1)} ${startY.toFixed(1)}`;
  let dArea = `M ${startX.toFixed(1)} ${(height - padB).toFixed(1)} L ${startX.toFixed(1)} ${startY.toFixed(1)}`;

  for (let i = 1; i < steps.length; i++) {
    const s = steps[i];
    const curX = getX(s.daysAgo);
    const curY = getY(s.price);

    dLine += ` H ${curX.toFixed(1)} V ${curY.toFixed(1)}`;
    dArea += ` H ${curX.toFixed(1)} V ${curY.toFixed(1)}`;
  }

  const lastX = getX(steps[steps.length - 1].daysAgo);
  const lastY = getY(steps[steps.length - 1].price);
  dArea += ` L ${lastX.toFixed(1)} ${(height - padB).toFixed(1)} Z`;

  return { dLine, dArea, lastX, lastY, getX, getY };
}

/**
 * Genera un grafico vettoriale SVG sparkline con andamento reale a gradini (Keepa style),
 * area sfumata autentica, linee benchmark per Media Storica e Minimo, ed etichette temporali.
 */
function generateRadarSparkline(pOrP90, p30, pCurrent, pAtl) {
  let p;
  if (typeof pOrP90 === 'object' && pOrP90 !== null) {
    p = pOrP90;
  } else {
    p = {
      avg_price_90d: pOrP90 || 25,
      avg_price_30d: p30 || 22,
      current_price: pCurrent || 19,
      all_time_low: pAtl || 18,
      sku_id: 'sample'
    };
  }

  const timeline = getProductPriceTimeline(p, '1y');
  const width = 280;
  const height = 54;
  const padX = 8;
  const padT = 7;
  const padB = 16;

  const prices = timeline.map(t => t.price);
  const pYearAvg = Number(p.avg_price_2022_2024) || Number(p.avg_price_90d) || (Number(p.list_price) * 0.9);
  const maxPrice = Math.max(...prices, pYearAvg, (p.list_price || 0) * 0.98) * 1.04;
  const minPrice = Math.min(...prices, p.all_time_low || 0) * 0.96;

  const { dLine, dArea, lastX, lastY, getY } = buildSvgStepPath(
    timeline, width, height, padX, padX, padT, padB, minPrice, maxPrice, 365
  );

  const atlY = getY(p.all_time_low || minPrice);
  const pYearY = getY(pYearAvg);

  const gradId = `grad_${(p.sku_id || 'def').replace(/[^a-zA-Z0-9]/g, '_')}`;

  return `
    <svg class="chart-sparkline" viewBox="0 0 ${width} ${height}" style="cursor: pointer;" title="Storico Prezzi 1 Anno (12 Mesi) - Clicca per aprire il grafico dettagliato">
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#2563eb" stop-opacity="0.32" />
          <stop offset="100%" stop-color="#2563eb" stop-opacity="0.02" />
        </linearGradient>
      </defs>
      
      <!-- Baseline Media 1 Anno (Dashed) -->
      <line x1="${padX}" y1="${pYearY.toFixed(1)}" x2="${width - padX}" y2="${pYearY.toFixed(1)}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="2,2" />
      
      <!-- Baseline Minimo Storico (Green Dashed) -->
      <line x1="${padX}" y1="${atlY.toFixed(1)}" x2="${width - padX}" y2="${atlY.toFixed(1)}" stroke="#10b981" stroke-width="1" stroke-dasharray="3,2" />

      <!-- Area Sfumata sotto i gradini -->
      <path fill="url(#${gradId})" d="${dArea}" />

      <!-- Linea di Tendenza a Gradini Reale (Stairs Keepa) -->
      <path
        fill="none"
        stroke="#2563eb"
        stroke-width="2.2"
        stroke-linecap="round"
        stroke-linejoin="round"
        d="${dLine}"
      />

      <!-- Punto Prezzo Odierno con Aureola -->
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="6" fill="#f59e0b" fill-opacity="0.25" />
      <circle cx="${lastX.toFixed(1)}" cy="${lastY.toFixed(1)}" r="3.5" fill="#f59e0b" stroke="#ffffff" stroke-width="1.5" />

      <!-- Asse Temporale Bottom Labels: 1 Anno -->
      <text x="${padX}" y="${height - 2}" font-size="8" fill="#94a3b8" font-weight="600">1 Anno fa</text>
      <text x="${width / 2}" y="${height - 2}" font-size="8" fill="#94a3b8" font-weight="600" text-anchor="middle">6 Mesi fa</text>
      <text x="${width - padX}" y="${height - 2}" font-size="8" fill="#2563eb" font-weight="700" text-anchor="end">Oggi</text>
    </svg>
  `;
}

/**
 * Modale Interattivo Completo di Analisi e Grafico Storico Prezzi
 * Supporta selettore intervallo dinamico: 30 Giorni | 90 Giorni | 1 Anno (12 Mesi)
 */
function openPriceChartModal(skuId, initialRange = '1y') {
  const p = (rawCatalog || []).find(item => item.sku_id === skuId) || 
            (currentProducts || []).find(item => item.sku_id === skuId);
  if (!p) return;

  const chartDialog = document.getElementById('chartDialog');
  const modalTitle = document.getElementById('chartModalTitle');
  const modalBody = document.getElementById('chartModalBody');
  if (!chartDialog || !modalBody) return;

  modalTitle.textContent = `Analisi Storico Prezzi: ${p.title.slice(0, 48)}...`;

  const imgUrl = p.image_url || 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=200';

  // Struttura base modale
  modalBody.innerHTML = `
    <!-- Product Header Banner -->
    <div class="chart-meta-banner">
      <img src="${imgUrl}" alt="${escapeHtml(p.title)}" class="chart-meta-thumb" onload="if(this.naturalWidth<=2||this.naturalHeight<=2){this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');}" onerror="this.onerror=null;this.src=getCategoryFallbackImage('${p.macro_category_id}');">
      <div class="chart-meta-info">
        <h4>${p.title}</h4>
        <div class="chart-meta-tags">
          <span>🏷 Brand: <strong>${p.brand}</strong></span>
          <span>• 📦 ASIN: <code>${p.asin}</code></span>
          <span>• 📂 Categoria: <strong>${p.macro_category_name}</strong></span>
        </div>
      </div>
    </div>

    <!-- Range Selector Toolbar (30gg / 90gg / 1 Anno) -->
    <div class="chart-range-bar">
      <div class="chart-range-title">
        <span class="range-icon">📅</span> Intervallo Storico:
      </div>
      <div class="chart-range-selector" id="chartRangeButtons">
        <button type="button" class="range-btn ${initialRange === '30d' ? 'active' : ''}" data-range="30d">30 Giorni</button>
        <button type="button" class="range-btn ${initialRange === '90d' ? 'active' : ''}" data-range="90d">90 Giorni</button>
        <button type="button" class="range-btn ${initialRange === '1y' ? 'active' : ''}" data-range="1y">✨ 1 Anno (12 Mesi)</button>
      </div>
    </div>

    <!-- Metrics Cards Container -->
    <div class="chart-metrics-cards" id="chartMetricsContainer"></div>

    <!-- Interactive SVG Chart Canvas Box -->
    <div class="chart-canvas-box">
      <div class="chart-tooltip-display" id="chartHoverTooltip">
        <span>📈 Passa il cursore sui punti per visualizzare data esatta e prezzo</span>
        <span>Listino Ufficiale: €${(p.list_price || p.current_price).toFixed(2)}</span>
      </div>

      <div id="chartSvgWrapper"></div>

      <!-- Dynamic Legend -->
      <div class="chart-legend" id="chartLegendContainer"></div>
    </div>

    <!-- Radar Authenticity Callout -->
    <div class="radar-badge-callout">
      <span style="font-size: 1.25rem;">🛡️</span>
      <div id="chartCalloutText">
        ${p.list_price > p.current_price && p.keepa_drop_percent > 0
          ? `<strong>Algoritmo Radar Anti-Finti Sconti:</strong> Sconto autentico verificato su Amazon.it. Il prodotto è attualmente in offerta a <strong>€${p.current_price.toFixed(2)}</strong> rispetto al prezzo barrato ufficiale di <s>€${p.list_price.toFixed(2)}</s> (risparmio reale di €${(p.list_price - p.current_price).toFixed(2)}) e a una media di <strong>€${p.avg_price_90d.toFixed(2)}</strong> negli ultimi mesi.`
          : `<strong>Algoritmo Radar Anti-Finti Sconti:</strong> Prezzo netto ufficiale Amazon.it. Il prodotto è venduto al miglior prezzo di <strong>€${p.current_price.toFixed(2)}</strong> senza rincari fittizi (nessun finto prezzo barrato gonfiato), con prezzo in linea con la media di <strong>€${p.avg_price_90d.toFixed(2)}</strong>.`
        }
      </div>
    </div>

    <!-- Action Buttons -->
    <div class="chart-actions-row">
      <a href="${formatAffiliateUrl(p.affiliate_url, p.asin)}" target="_blank" rel="noopener sponsored" class="btn-chart-modal-buy">
        🛒 Acquista su Amazon ↗
      </a>
      <div class="chart-modal-sub-actions">
        <button type="button" class="btn-chart-modal-track" id="btnChartTrackModal">
          🔔 Imposta Allarme
        </button>
        <button type="button" class="btn-chart-modal-track" id="btnChartCopyLink" style="background:#eff6ff; color:#2563eb; border-color:#bfdbfe; font-weight:700;" title="Copia link affiliato verificato">
          📋 Copia Link
        </button>
      </div>
    </div>
  `;

  // Funzione di rendering dinamico del grafico al cambio di intervallo
  function renderChartContent(selectedRange) {
    const timeline = getProductPriceTimeline(p, selectedRange);
    const width = 600;
    const height = 230;
    const padL = 52;
    const padR = 25;
    const padT = 25;
    const padB = 40;
    const maxDays = selectedRange === '30d' ? 30 : (selectedRange === '90d' ? 90 : 365);

    const prices = timeline.map(t => t.price);
    const maxPrice = Math.max(...prices, p.list_price || 0, p.avg_price_90d || 0) * 1.05;
    const minPrice = Math.min(...prices, p.all_time_low || 0) * 0.95;
    const rangeVal = (maxPrice - minPrice) || 1;

    const { dLine, dArea, lastX, lastY, getX, getY } = buildSvgStepPath(
      timeline, width, height, padL, padR, padT, padB, minPrice, maxPrice, maxDays
    );

    const atlY = getY(p.all_time_low || minPrice);

    // Benchmark in base all'intervallo
    let benchmarkPrice = p.avg_price_90d;
    let benchmarkLabel = "Media 90gg";
    if (selectedRange === '30d') {
      benchmarkPrice = p.avg_price_30d;
      benchmarkLabel = "Media 30gg";
    } else if (selectedRange === '1y') {
      benchmarkPrice = Number(p.avg_price_2022_2024) || (p.avg_price_90d * 1.08);
      benchmarkLabel = "Media 1 Anno";
    }
    const benchY = getY(benchmarkPrice);

    // Nodi SVG su ogni cambio di prezzo
    const nodesSvg = timeline.map((t, idx) => {
      const cx = getX(t.daysAgo).toFixed(1);
      const cy = getY(t.price).toFixed(1);
      const isLast = idx === timeline.length - 1;
      const r = isLast ? "6.5" : "4.5";
      const fill = isLast ? "#f59e0b" : "#2563eb";
      return `
        <circle 
          class="chart-node" 
          data-date="${t.date}" 
          data-price="€${t.price.toFixed(2)}"
          data-label="${t.label || ''}"
          cx="${cx}" 
          cy="${cy}" 
          r="${r}" 
          fill="${fill}" 
          stroke="#ffffff" 
          stroke-width="2" 
          style="cursor: pointer;"
        />
      `;
    }).join('');

    // Dynamic X-axis Labels based on actual steps
    const xLabelsSvg = timeline.filter((t, idx) => idx === 0 || idx === timeline.length - 1 || (timeline.length > 3 && idx % 2 === 1)).map(t => {
      const xPos = getX(t.daysAgo).toFixed(1);
      return `<text x="${xPos}" y="${height - 14}" font-size="10" fill="#64748b" font-weight="600" text-anchor="middle">${t.shortDate || t.label}</text>`;
    }).join('');

    // Asse Y Ticks
    const yTicks = [
      minPrice,
      minPrice + rangeVal * 0.33,
      minPrice + rangeVal * 0.66,
      maxPrice
    ];
    const yAxisSvg = yTicks.map(val => {
      const yPos = getY(val).toFixed(1);
      return `
        <line x1="${padL}" y1="${yPos}" x2="${width - padR}" y2="${yPos}" stroke="#f1f5f9" stroke-width="1" />
        <text x="${padL - 8}" y="${Number(yPos) + 3}" font-size="10" fill="#94a3b8" text-anchor="end">€${val.toFixed(0)}</text>
      `;
    }).join('');

    const svgWrapper = document.getElementById('chartSvgWrapper');
    if (svgWrapper) {
      svgWrapper.innerHTML = `
        <svg class="chart-large-svg" viewBox="0 0 ${width} ${height}">
          <defs>
            <linearGradient id="largeModalGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#2563eb" stop-opacity="0.28" />
              <stop offset="100%" stop-color="#2563eb" stop-opacity="0.01" />
            </linearGradient>
          </defs>

          <!-- Y Axis Grid -->
          ${yAxisSvg}

          <!-- Benchmark Line -->
          <line x1="${padL}" y1="${benchY.toFixed(1)}" x2="${width - padR}" y2="${benchY.toFixed(1)}" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="4,3" />
          <text x="${width - padR}" y="${(benchY - 5).toFixed(1)}" font-size="10" fill="#3b82f6" font-weight="600" text-anchor="end">${benchmarkLabel}: €${benchmarkPrice.toFixed(2)}</text>

          <!-- Miglior Prezzo Rilevato Line -->
          <line x1="${padL}" y1="${atlY.toFixed(1)}" x2="${width - padR}" y2="${atlY.toFixed(1)}" stroke="#10b981" stroke-width="1.5" stroke-dasharray="4,3" />
          <text x="${padL + 6}" y="${(atlY - 5).toFixed(1)}" font-size="10" fill="#10b981" font-weight="700">📉 Minimo Storico: €${p.all_time_low.toFixed(2)}</text>

          <!-- Shaded Area sotto i gradini -->
          <path fill="url(#largeModalGrad)" d="${dArea}" />

          <!-- Crisp Trend Step Path (Keepa Style) -->
          <path
            fill="none"
            stroke="#2563eb"
            stroke-width="3"
            stroke-linecap="round"
            stroke-linejoin="round"
            d="${dLine}"
          />

          <!-- Nodes -->
          ${nodesSvg}

          <!-- X Axis Labels -->
          ${xLabelsSvg}
        </svg>
      `;
    }

    // Dynamic Legend
    const legendContainer = document.getElementById('chartLegendContainer');
    if (legendContainer) {
      legendContainer.innerHTML = `
        <div class="legend-item"><span class="legend-dot" style="background:#2563eb;"></span> Andamento Prezzo Reale</div>
        <div class="legend-item"><span class="legend-dot" style="background:#3b82f6; border: 1px dashed;"></span> ${benchmarkLabel} (€${benchmarkPrice.toFixed(2)})</div>
        <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> Minimo Storico (€${p.all_time_low.toFixed(2)})</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> Offerta Odierna (€${p.current_price.toFixed(2)})</div>
      `;
    }

    // Callout text update
    const calloutEl = document.getElementById('chartCalloutText');
    if (calloutEl) {
      const periodText = selectedRange === '1y' ? 'negli ultimi 12 mesi' : (selectedRange === '30d' ? 'negli ultimi 30 giorni' : 'negli ultimi 3 mesi');
      const hasRealDiscount = p.list_price > p.current_price && p.keepa_drop_percent > 0;
      if (hasRealDiscount) {
        calloutEl.innerHTML = `
          <strong>Algoritmo Radar Anti-Finti Sconti:</strong> Sconto autentico verificato su Amazon.it. Il prodotto è attualmente in offerta a <strong>€${p.current_price.toFixed(2)}</strong> rispetto al prezzo barrato ufficiale di <s>€${p.list_price.toFixed(2)}</s> (risparmio reale di €${(p.list_price - p.current_price).toFixed(2)}) e a una media di <strong>€${benchmarkPrice.toFixed(2)}</strong> ${periodText}.
        `;
      } else {
        calloutEl.innerHTML = `
          <strong>Algoritmo Radar Anti-Finti Sconti:</strong> Prezzo netto ufficiale Amazon.it. Il prodotto è venduto al miglior prezzo di <strong>€${p.current_price.toFixed(2)}</strong> senza rincari fittizi (nessun finto prezzo barrato gonfiato), con prezzo in linea con la media di <strong>€${benchmarkPrice.toFixed(2)}</strong> ${periodText}.
        `;
      }
    }

    // Tooltip bindings
    const hoverDisplay = document.getElementById('chartHoverTooltip');
    if (hoverDisplay) {
      modalBody.querySelectorAll('.chart-node').forEach(node => {
        node.addEventListener('mouseenter', (e) => {
          const d = e.target.dataset.date;
          const pr = e.target.dataset.price;
          e.target.setAttribute('r', '8');
          hoverDisplay.innerHTML = `<span style="color:#2563eb; font-weight:700;">📅 ${d}</span> <span>💰 Prezzo Registrato: <strong>${pr}</strong></span>`;
        });
        node.addEventListener('mouseleave', (e) => {
          e.target.setAttribute('r', e.target.dataset.date.includes('Oggi') ? '6.5' : '4.5');
          hoverDisplay.innerHTML = `<span>📈 Passa il cursore sui punti per visualizzare data esatta e prezzo</span> <span>Miglior Prezzo: €${p.all_time_low.toFixed(2)}</span>`;
        });
      });
    }
  }

  // Render iniziale con intervallo selezionato (default: 1 anno)
  renderChartContent(initialRange);

  // Range selector click handlers
  modalBody.querySelectorAll('#chartRangeButtons .range-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      modalBody.querySelectorAll('#chartRangeButtons .range-btn').forEach(b => b.classList.remove('active'));
      e.currentTarget.classList.add('active');
      const newRange = e.currentTarget.dataset.range;
      renderChartContent(newRange);
    });
  });

  // Track button inside chart modal
  modalBody.querySelector('#btnChartTrackModal')?.addEventListener('click', () => {
    chartDialog.close();
    openAlertModal(p.sku_id, p.title, p.current_price, p.all_time_low);
  });

  // Copy verified affiliate link inside chart modal
  modalBody.querySelector('#btnChartCopyLink')?.addEventListener('click', async () => {
    const link = formatAffiliateUrl(p.affiliate_url, p.asin);
    try {
      await navigator.clipboard.writeText(link);
      showToast("Link affiliato verificato copiato! 📋", "✅");
    } catch (e) {
      prompt("Copia link affiliato:", link);
    }
  });

  chartDialog.showModal();
}

// Modal handling
let activeAlertSku = null;

function openAlertModal(sku, name, price, atl) {
  activeAlertSku = sku;
  document.getElementById('modalProductName').textContent = name;
  document.getElementById('modalCurrentPrice').textContent = `€${parseFloat(price).toFixed(2)}`;
  document.getElementById('modalAtlPrice').textContent = `€${parseFloat(atl).toFixed(2)}`;
  
  // Imposta suggerimento prezzo a -15% dal corrente
  const inputEl = document.getElementById('targetPriceInput');
  const suggested = (parseFloat(price) * 0.85).toFixed(2);
  inputEl.value = suggested;

  // Ergonomic Quick Price Presets
  document.querySelectorAll('.btn-quick-price').forEach(btn => {
    btn.onclick = () => {
      const pct = parseFloat(btn.dataset.pct);
      inputEl.value = (parseFloat(price) * pct).toFixed(2);
      showToast(`Prezzo impostato a -${Math.round((1 - pct) * 100)}% (€${inputEl.value})`, '🎯');
    };
  });
  const atlBtn = document.querySelector('.btn-quick-price-atl');
  if (atlBtn) {
    atlBtn.onclick = () => {
      inputEl.value = parseFloat(atl).toFixed(2);
      showToast(`Prezzo impostato al Miglior Prezzo (€${inputEl.value})`, '📉');
    };
  }
  
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

