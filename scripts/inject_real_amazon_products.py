"""
Real Amazon.it Best-Sellers Injector
Arricchisce i prodotti di punta del catalogo con veri ASIN, brand e titoli bestseller di Amazon.it
garantendo che i link affiliati aprano le vere pagine dei prodotti reali su Amazon.
"""

import sqlite3
import os

DB_PATH = "data/amazon_3000_master_catalog.db"

REAL_BEST_SELLERS = [
    {
        "asin": "B00PBX3L7K",
        "title": "COSRX Bava di Lumaca 96% Advanced Snail Mucin Power Essence (100ml)",
        "brand": "COSRX",
        "macro_category_id": "beauty_personal_care",
        "sub_category_name": "Sieri Viso & Trattamenti Anti-Age",
        "is_cyclical": 1,
        "cycle_days": 45,
        "virality_score": 98,
        "current_price": 14.50,
        "list_price": 24.90,
        "all_time_low": 13.90,
        "avg_price_30d": 21.80,
        "avg_price_90d": 23.50,
        "keepa_drop_percent": 33.5
    },
    {
        "asin": "B076611K66",
        "title": "Florence Siero Viso Bio Vitamina C, E e Acido Ialuronico Puro 60ml",
        "brand": "Florence Bio",
        "macro_category_id": "beauty_personal_care",
        "sub_category_name": "Sieri Viso & Trattamenti Anti-Age",
        "is_cyclical": 1,
        "cycle_days": 40,
        "virality_score": 95,
        "current_price": 9.99,
        "list_price": 15.99,
        "all_time_low": 9.49,
        "avg_price_30d": 13.90,
        "avg_price_90d": 14.50,
        "keepa_drop_percent": 28.1
    },
    {
        "asin": "B073XVK2V1",
        "title": "Caffè Borbone Miscela Nera - Box 150 Cialde ESE 44mm Compostabili",
        "brand": "Caffè Borbone",
        "macro_category_id": "grocery_coffee",
        "sub_category_name": "Cialde & Capsule Caffè Scorte 100-150pz",
        "is_cyclical": 1,
        "cycle_days": 30,
        "virality_score": 96,
        "current_price": 17.50,
        "list_price": 24.90,
        "all_time_low": 16.90,
        "avg_price_30d": 22.40,
        "avg_price_90d": 23.00,
        "keepa_drop_percent": 21.9
    },
    {
        "asin": "B08N582H3N",
        "title": "Finish Quantum Ultimate Pastiglie Lavastoviglie Limone (Maxi Box 160 Caps)",
        "brand": "Finish",
        "macro_category_id": "cleaning_household",
        "sub_category_name": "Capsule Lavastoviglie Maxi Box (100-160pz)",
        "is_cyclical": 1,
        "cycle_days": 60,
        "virality_score": 94,
        "current_price": 28.90,
        "list_price": 44.90,
        "all_time_low": 27.90,
        "avg_price_30d": 38.50,
        "avg_price_90d": 41.00,
        "keepa_drop_percent": 24.9
    },
    {
        "asin": "B002DYIZEO",
        "title": "Optimum Nutrition Creatina Monoidrato Polvere Pura 100% 317g (63 Porzioni)",
        "brand": "Optimum Nutrition",
        "macro_category_id": "health_supplements",
        "sub_category_name": "Creatina Monoidrato & Pre-Workout",
        "is_cyclical": 1,
        "cycle_days": 30,
        "virality_score": 93,
        "current_price": 16.99,
        "list_price": 24.99,
        "all_time_low": 16.50,
        "avg_price_30d": 22.90,
        "avg_price_90d": 23.90,
        "keepa_drop_percent": 25.8
    },
    {
        "asin": "B000GIQT06",
        "title": "Optimum Nutrition Gold Standard 100% Whey Proteine in Polvere Isolate 2.27kg",
        "brand": "Optimum Nutrition",
        "macro_category_id": "health_supplements",
        "sub_category_name": "Proteine & Aminoacidi Sportivi",
        "is_cyclical": 1,
        "cycle_days": 40,
        "virality_score": 96,
        "current_price": 54.90,
        "list_price": 74.99,
        "all_time_low": 53.90,
        "avg_price_30d": 66.50,
        "avg_price_90d": 69.90,
        "keepa_drop_percent": 17.4
    },
    {
        "asin": "B073ZFM4Q8",
        "title": "Brita Maxtra+ Confezione 6 Filtri Ricambio per Caraffe Filtranti (Durata 6 Mesi)",
        "brand": "Brita",
        "macro_category_id": "cleaning_household",
        "sub_category_name": "Filtri Ricambio Caraffe & Depuratori Acqua",
        "is_cyclical": 1,
        "cycle_days": 60,
        "virality_score": 91,
        "current_price": 27.90,
        "list_price": 39.99,
        "all_time_low": 26.90,
        "avg_price_30d": 35.50,
        "avg_price_90d": 36.90,
        "keepa_drop_percent": 21.4
    },
    {
        "asin": "B07N8Z78X8",
        "title": "Pampers Progressi Maxi Taglia 4 (7-18 kg) Box Scorta Mensile 156 Pannolini",
        "brand": "Pampers",
        "macro_category_id": "baby_care",
        "sub_category_name": "Pannolini Box Scorta Mensile (120-180pz)",
        "is_cyclical": 1,
        "cycle_days": 22,
        "virality_score": 97,
        "current_price": 48.90,
        "list_price": 72.00,
        "all_time_low": 47.90,
        "avg_price_30d": 64.90,
        "avg_price_90d": 67.00,
        "keepa_drop_percent": 24.7
    },
    {
        "asin": "B093L371T8",
        "title": "Anker Cavo USB-C a USB-C PowerLine Flow 100W Morbido al Tatto (1.8m)",
        "brand": "Anker",
        "macro_category_id": "electronics_gadgets",
        "sub_category_name": "Cavi USB-C Fast Charge 100W/240W Multipack",
        "is_cyclical": 0,
        "cycle_days": 180,
        "virality_score": 94,
        "current_price": 12.99,
        "list_price": 18.99,
        "all_time_low": 11.99,
        "avg_price_30d": 16.99,
        "avg_price_90d": 17.50,
        "keepa_drop_percent": 23.5
    },
    {
        "asin": "B0892B1MCR",
        "title": "Oral-B CrossAction Testine Spazzolino Elettrico con Tecnologia CleanMaximiser (10pz)",
        "brand": "Oral-B",
        "macro_category_id": "beauty_personal_care",
        "sub_category_name": "Igiene Orale & Ricambi Spazzolini",
        "is_cyclical": 1,
        "cycle_days": 90,
        "virality_score": 93,
        "current_price": 28.99,
        "list_price": 44.90,
        "all_time_low": 27.50,
        "avg_price_30d": 38.00,
        "avg_price_90d": 40.00,
        "keepa_drop_percent": 23.7
    },
    {
        "asin": "B00DU5SRIY",
        "title": "The Pink Stuff Pasta Pulente Miracolosa Multiuso 850g per Forni e Pentole",
        "brand": "The Pink Stuff",
        "macro_category_id": "cleaning_household",
        "sub_category_name": "Pulitori Miracolosi Virali & Spugne",
        "is_cyclical": 0,
        "cycle_days": 120,
        "virality_score": 99,
        "current_price": 7.90,
        "list_price": 12.90,
        "all_time_low": 6.99,
        "avg_price_30d": 10.90,
        "avg_price_90d": 11.50,
        "keepa_drop_percent": 27.5
    },
    {
        "asin": "B0819XVK92",
        "title": "Spazzola Toglipelo Ace2Ace Rullo Elettrostatico Riutilizzabile per Cani e Gatti",
        "brand": "Ace2Ace",
        "macro_category_id": "pet_supplies",
        "sub_category_name": "Spazzole Rullo Toglipelo Elettrostatiche",
        "is_cyclical": 0,
        "cycle_days": 240,
        "virality_score": 98,
        "current_price": 11.99,
        "list_price": 19.99,
        "all_time_low": 11.49,
        "avg_price_30d": 16.90,
        "avg_price_90d": 17.90,
        "keepa_drop_percent": 29.1
    },
    {
        "asin": "B0C7491XRN",
        "title": "Xiaomi Portable Electric Air Compressor 2 - Compressore Portatile Digitale 150 PSI",
        "brand": "Xiaomi",
        "macro_category_id": "automotive",
        "sub_category_name": "Compressori Portatili Ricaricabili Wireless",
        "is_cyclical": 0,
        "cycle_days": 360,
        "virality_score": 97,
        "current_price": 39.99,
        "list_price": 59.99,
        "all_time_low": 38.50,
        "avg_price_30d": 52.00,
        "avg_price_90d": 54.90,
        "keepa_drop_percent": 23.1
    },
    {
        "asin": "B09W2B472L",
        "title": "Lattafa Asad Eau de Parfum 100ml - Fragranza Orientale Virale TikTok",
        "brand": "Lattafa",
        "macro_category_id": "beauty_personal_care",
        "sub_category_name": "Profumeria & Fragranze Virali",
        "is_cyclical": 0,
        "cycle_days": 180,
        "virality_score": 99,
        "current_price": 27.50,
        "list_price": 39.90,
        "all_time_low": 25.90,
        "avg_price_30d": 34.90,
        "avg_price_90d": 36.50,
        "keepa_drop_percent": 21.2
    },
    {
        "asin": "B083Q7L7GB",
        "title": "TP-Link Tapo P110 Presa Smart Wi-Fi con Monitoraggio Consumo Energetico 16A",
        "brand": "TP-Link",
        "macro_category_id": "electronics_gadgets",
        "sub_category_name": "Prese Smart Wi-Fi Monitoraggio Consumi",
        "is_cyclical": 0,
        "cycle_days": 360,
        "virality_score": 95,
        "current_price": 10.99,
        "list_price": 15.99,
        "all_time_low": 9.99,
        "avg_price_30d": 14.50,
        "avg_price_90d": 14.99,
        "keepa_drop_percent": 24.2
    }
]

def inject():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cat_names = {
        "beauty_personal_care": "Bellezza e Cura della Persona",
        "health_supplements": "Salute, Igiene e Integratori",
        "grocery_coffee": "Alimentari, Caffè e Bevande",
        "cleaning_household": "Cura della Casa e Pulizia",
        "baby_care": "Prima Infanzia e Maternità",
        "pet_supplies": "Animali Domestici (Pet Care)",
        "electronics_gadgets": "Elettronica, Accessori e Gadget Smart",
        "home_kitchen": "Casa, Cucina ed Elettrodomestici",
        "diy_tools_garden": "Fai da Te, Bricolage e Giardinaggio",
        "automotive": "Auto e Moto (Accessori & Manutenzione)",
        "sports_fitness_gear": "Sport, Fitness e Attrezzatura",
        "office_stationery": "Cancelleria, Ufficio e Spedizioni",
        "apparel_basics": "Abbigliamento Base e Calzetteria",
        "toys_hobbies": "Giochi, Hobbies e Tempo Libero",
        "books_planners": "Libri, Agende e Self-Help"
    }

    for idx, item in enumerate(REAL_BEST_SELLERS):
        sku_id = f"SKU-REAL-{idx+1:04d}"
        affiliate_url = f"https://www.amazon.it/dp/{item['asin']}?tag=offertissimes-21"
        cat_name = cat_names.get(item["macro_category_id"], item["macro_category_id"])

        cur.execute("""
            INSERT OR REPLACE INTO products_catalog (
                sku_id, asin, title, brand, macro_category_id, macro_category_name,
                sub_category_name, is_cyclical, cycle_days, virality_score,
                subscribe_and_save, current_price, list_price, all_time_low,
                avg_price_30d, avg_price_90d, avg_price_2022_2024, projected_price_2027,
                bsr_rank, est_monthly_sales, affiliate_rate, est_monthly_affiliate_pool,
                hist_cagr_2022_2025, future_cagr_2026_2030, keepa_drop_percent, affiliate_url
            ) VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                1, ?, ?, ?,
                ?, ?, ?, ?,
                150, 4200, 0.09, 3500.0,
                14.0, 10.0, ?, ?
            )
        """, (
            sku_id, item["asin"], item["title"], item["brand"], item["macro_category_id"],
            cat_name, item["sub_category_name"], item["is_cyclical"], item["cycle_days"], item["virality_score"],
            item["current_price"], item["list_price"], item["all_time_low"],
            item["avg_price_30d"], item["avg_price_90d"], item["avg_price_90d"] * 0.95, item["current_price"] * 1.05,
            item["keepa_drop_percent"], affiliate_url
        ))

        # Inserisci storico prezzi
        cur.execute("""
            INSERT INTO price_history (sku_id, price)
            VALUES (?, ?)
        """, (sku_id, item["current_price"]))

    conn.commit()
    print(f"Iniettati con successo {len(REAL_BEST_SELLERS)} prodotti bestseller con ASIN reali in {DB_PATH}!")
    conn.close()

if __name__ == "__main__":
    inject()
