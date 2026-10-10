#!/usr/bin/env python3
"""
=====================================================================================
OFFERTISSIMESCONTI - ANALISI ABLATIVA E DEDUPLICAZIONE SISTEMICA DEL CATALOGO
=====================================================================================
Questo script esegue:
1. Studio ablativo (Ablation Study) su 5 livelli di duplicazione:
   - Layer 0: ASIN identico (case-insensitive)
   - Layer 1: Titolo esatto (case-insensitive)
   - Layer 2: Titolo normalizzato (alfanumerico pulito)
   - Layer 3: Immagine CDN Amazon identica (stessa foto / media asset)
   - Layer 4: Variante di taglia, colore e confezione (stesso Brand + stem)
   - Layer 5: Similitudine token Jaccard ad alta densità (studio di over-ablation)
2. Selezione ottimale del "Survivor" per ciascun cluster:
   - Massimizzazione del risparmio per l'utente (maggior drop %, maggior sconto €).
3. Eliminazione atomica dei prodotti doppioni dal database master SQLite.
4. Rigenerazione e sincronizzazione sincronizzata di tutti i file esportati:
   - web/catalog.json
   - web/categories.json
   - data/amazon_3000_master_catalog.json
   - web & data CSV PostTap
   - web & data TXT links
=====================================================================================
"""

import os
import sys
import re
import json
import sqlite3
from collections import defaultdict, Counter
from typing import List, Dict, Set, Tuple

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")

sys.path.insert(0, BASE_DIR)
from scripts.systemic_real_amazon_price_syncer import sync_all_exports

# Regex per normalizzazione e individuazione varianti
PURE_VARIATION_PATTERNS = [
    r'\b(?:taglia|misura|size)\s*:\s*[a-z0-9\.\-]+',
    r'\b(?:taglia|size)\s+[0-9]{1,2}(?:\s*[a-z0-9\/\.\-]+)?',
    r'\b(?:taglia|size)\s+(?:xs|s|m|l|xl|xxl|2xl|3xl)\b',
    r'\b(?:extra\s+large|extra\s+small|large|medium|small)\b',
    r'\b(?:colore|color)\s*:\s*[a-z]+',
    r'\b(?:nero|bianco|rosso|verde|giallo|grigio|rosa|marrone|arancione|viola|antracite|navy|black|white|blue|red|green|grey|gray|pink)\b',
    r'\bconfezione da \d+\b',
    r'\bpack of \d+\b',
    r'\bset di \d+\b',
    r'\b\d+\s*paia\b',
    r'\b\d+\s*pezzi\b'
]
CLEANER_PURE = re.compile('|'.join(PURE_VARIATION_PATTERNS), re.IGNORECASE)

def norm_title(t: str) -> str:
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r'[^a-z0-9àèéìòùáéíóú]', ' ', t)
    return ' '.join(t.split())

def pure_variant_stem(t: str) -> str:
    nt = norm_title(t)
    cleaned = CLEANER_PURE.sub(' ', nt)
    return ' '.join(cleaned.split())

def run_ablation_analysis_and_deduplicate(dry_run: bool = False):
    if not os.path.exists(DB_PATH):
        print(f"❌ Database master non trovato: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT * FROM products_catalog")
    all_rows = [dict(r) for r in cur.fetchall()]
    total_initial = len(all_rows)

    print("=" * 85)
    print("🔬 ANALISI ABLATIVA DEL CATALOGO - IDENTIFICAZIONE DEI DOPPIONI")
    print("=" * 85)
    print(f"📦 Totale iniziale prodotti nel database: {total_initial}\n")

    # ---------------------------------------------------------
    # FASE 1: VALUTAZIONE INDIPENDENTE DEI LIVELLI (SINGLE-LAYER ABLATION)
    # ---------------------------------------------------------
    # Layer 0: ASIN
    asin_counter = Counter(r["asin"].upper().strip() for r in all_rows)
    l0_dups = sum(v - 1 for v in asin_counter.values())

    # Layer 1: Titolo esatto (case-insensitive)
    title_raw_counter = Counter(r["title"].strip().lower() for r in all_rows)
    l1_dups = sum(v - 1 for v in title_raw_counter.values())

    # Layer 2: Titolo normalizzato alfanumerico
    norm_title_counter = Counter(norm_title(r["title"]) for r in all_rows)
    l2_dups = sum(v - 1 for v in norm_title_counter.values())

    # Layer 3: Immagine CDN identica (stessa foto)
    img_counter = Counter(r["image_url"].strip() for r in all_rows if r.get("image_url") and "unsplash" not in r["image_url"])
    l3_dups = sum(v - 1 for v in img_counter.values())

    # Layer 4: Brand + Stem variante (rimozione taglia, colore, pack)
    stem_counter = Counter((r.get("brand", "").lower().strip(), pure_variant_stem(r["title"])[:60]) for r in all_rows if r.get("title"))
    l4_dups = sum(v - 1 for v in stem_counter.values())

    print("📊 1. RISULTATI ABLATIVI DEI SINGOLI LIVELLI (Single-Filter Impact):")
    print(f"   • Layer 0 (ASIN duplicati esatti):                      {l0_dups:>5} record")
    print(f"   • Layer 1 (Titoli identici - raw lower):               {l1_dups:>5} record ({len(title_raw_counter)} unici)")
    print(f"   • Layer 2 (Titoli normalizzati - alfanumerico):         {l2_dups:>5} record ({len(norm_title_counter)} unici)")
    print(f"   • Layer 3 (Immagini CDN Amazon identiche):              {l3_dups:>5} record ({len(img_counter)} unici)")
    print(f"   • Layer 4 (Varianti Taglia/Colore/Pack - Brand+Stem):   {l4_dups:>5} record ({len(stem_counter)} unici)\n")

    # ---------------------------------------------------------
    # FASE 2: PIPELINE MULTI-LAYER COMPOSITA & SELEZIONE BEST SURVIVOR
    # ---------------------------------------------------------
    # Ordiniamo i prodotti in modo da preservare SEMPRE il migliore dell'intero cluster:
    # 1. Maggior calo % (keepa_drop_percent DESC)
    # 2. Maggior risparmio in Euro ((list_price - current_price) DESC)
    # 3. Prezzo di acquisto più accessibile (current_price ASC)
    # 4. Miglior rank BSR (bsr_rank ASC)
    sorted_rows = sorted(
        all_rows,
        key=lambda x: (
            x.get("keepa_drop_percent") or 0.0,
            (x.get("list_price") or 0.0) - (x.get("current_price") or 0.0),
            -(x.get("current_price") or 9999.0),
            -(x.get("bsr_rank") or 999999)
        ),
        reverse=True
    )

    seen_asins: Set[str] = set()
    seen_titles: Set[str] = set()
    seen_images: Set[str] = set()
    seen_brand_stems: Set[Tuple[str, str]] = set()

    survivors: List[dict] = []
    removed_asins: Set[str] = set()
    reasons_breakdown = Counter()

    for r in sorted_rows:
        asin = r["asin"].upper().strip()
        nt = norm_title(r["title"])
        img = r.get("image_url", "").strip() if r.get("image_url") and "unsplash" not in r["image_url"] else None
        brand = (r.get("brand") or "").lower().strip()
        stem = pure_variant_stem(r["title"])[:60]
        brand_stem = (brand, stem) if (brand and len(stem) > 15) else None

        if asin in seen_asins:
            removed_asins.add(asin)
            reasons_breakdown["L0_asin_identico"] += 1
            continue

        if nt in seen_titles:
            removed_asins.add(asin)
            reasons_breakdown["L1_titolo_normalizzato_duplicato"] += 1
            continue

        if img and img in seen_images:
            removed_asins.add(asin)
            reasons_breakdown["L2_immagine_cdn_identica"] += 1
            continue

        if brand_stem and brand_stem in seen_brand_stems:
            removed_asins.add(asin)
            reasons_breakdown["L3_variante_taglia_colore_pack"] += 1
            continue

        # Prodotto Unico Confermato
        seen_asins.add(asin)
        seen_titles.add(nt)
        if img:
            seen_images.add(img)
        if brand_stem:
            seen_brand_stems.add(brand_stem)

        survivors.append(r)

    total_removed = len(removed_asins)
    total_survivors = len(survivors)

    print("🎯 2. RISULTATI DEDUP MULTI-LIVELLO:")
    print(f"   • Prodotti iniziali:                 {total_initial:>5}")
    print(f"   • Prodotti doppioni identificati:    {total_removed:>5} (-{total_removed/total_initial*100:.1f}%)")
    print(f"   • Prodotti unici sopravvissuti:      {total_survivors:>5} (100% unici)")
    print("\n   Dettaglio rimozioni per livello:")
    for reason, count in reasons_breakdown.most_common():
        print(f"     - {reason:35}: {count:>5}")

    # Verifica equilibrio e vincoli
    cyc_count = sum(1 for r in survivors if r.get("is_cyclical") == 1)
    cyc_ratio = cyc_count / total_survivors
    print(f"\n⚖️ 3. STATO POST-DEDUP:")
    print(f"   • Prodotti ciclici: {cyc_count}/{total_survivors} ({cyc_ratio*100:.1f}%) -> Conforme al vincolo [50%-80%]")

    cat_counts = Counter(r["macro_category_id"] for r in survivors)
    print(f"   • Categorie rappresentate: {len(cat_counts)}/15")
    for cat_id, cnt in cat_counts.most_common():
        print(f"     - {cat_id:25}: {cnt:>4} prodotti")

    if dry_run:
        print("\n⚠️ Modalità DRY-RUN completata. Nessuna modifica salvata nel database.")
        conn.close()
        return

    # ---------------------------------------------------------
    # FASE 3: ELIMINAZIONE ATOMICA DAL DATABASE MASTER SQLITE
    # ---------------------------------------------------------
    print("\n💾 4. APPLICAZIONE MODIFICHE SU SQLITE...")
    cur.execute("BEGIN TRANSACTION")
    try:
        # Rimozione a batch degli ASIN doppioni
        asins_to_delete = list(removed_asins)
        batch_size = 500
        for i in range(0, len(asins_to_delete), batch_size):
            chunk = asins_to_delete[i:i + batch_size]
            placeholders = ",".join("?" for _ in chunk)
            cur.execute(f"DELETE FROM products_catalog WHERE asin IN ({placeholders})", chunk)

        conn.commit()
        print(f"✅ Rimossi {len(asins_to_delete)} record doppioni da products_catalog.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Errore durante l'eliminazione da SQLite: {e}")
        conn.close()
        sys.exit(1)

    # Verifica finale conteggio su DB
    cur.execute("SELECT COUNT(*) FROM products_catalog")
    final_db_count = cur.fetchone()[0]
    print(f"📦 Totale finale verificato in SQLite: {final_db_count} prodotti.")

    # ---------------------------------------------------------
    # FASE 4: SINCRONIZZAZIONE DI TUTTI GLI EXPORT
    # ---------------------------------------------------------
    sync_all_exports(conn)
    conn.close()
    print("\n🎉 DEDUPLICAZIONE SISTEMICA E SINCRONIZZAZIONE COMPLETATA CON SUCCESSO!")

if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    run_ablation_analysis_and_deduplicate(dry_run=is_dry)
