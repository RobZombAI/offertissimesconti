"""
Enterprise REST API & Web Server per OFFERTISSIMESCONTI
Serve sia l'applicazione web statica (HTML, CSS, JS) su '/' che tutti gli endpoint
REST API (/api/products, /api/categories, /api/deals, /api/stats, /api/track).
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import sqlite3
import os
import mimetypes

import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "data", "amazon_3000_master_catalog.db")
WEB_DIR = os.path.join(BASE_DIR, "web")

class OffertissimeScontiServer(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        try:
            body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, filepath: str):
        if not os.path.exists(filepath):
            self.send_error(404, "File non trovato")
            return

        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            try:
                self.send_error(500, f"Errore server: {str(e)}")
            except Exception:
                pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Routing Static Web Files
        if path == "/" or path == "/index.html":
            self._serve_static(os.path.join(WEB_DIR, "index.html"))
            return
        elif path in ("/style.css", "/app.js", "/categories.json", "/catalog.json", "/offertissimesconti_posttap_export.csv", "/offertissimesconti_links_only.txt"):
            self._serve_static(os.path.join(WEB_DIR, path.lstrip("/")))
            return

        # 2. Routing REST API
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        try:
            if path == "/api/categories":
                cur.execute("""
                    SELECT 
                        macro_category_id,
                        macro_category_name,
                        COUNT(*) as total_skus,
                        SUM(is_cyclical) as cyclical_skus,
                        COUNT(*) - SUM(is_cyclical) as non_cyclical_skus,
                        ROUND(AVG(current_price), 2) as avg_price,
                        ROUND(AVG(affiliate_rate) * 100, 1) as avg_affiliate_rate_pct,
                        ROUND(AVG(hist_cagr_2022_2025), 1) as avg_hist_cagr,
                        ROUND(AVG(future_cagr_2026_2030), 1) as avg_future_cagr
                    FROM products_catalog
                    GROUP BY macro_category_id, macro_category_name
                    ORDER BY total_skus DESC
                """)
                rows = [dict(r) for r in cur.fetchall()]
                self._send_json(200, {"success": True, "categories": rows})

            elif path == "/api/products":
                conditions = []
                params = []

                if "category" in query and query["category"][0]:
                    conditions.append("macro_category_id = ?")
                    params.append(query["category"][0])

                if "cyclical" in query:
                    val = 1 if query["cyclical"][0] in ("1", "true", "True") else 0
                    conditions.append("is_cyclical = ?")
                    params.append(val)

                if "min_drop" in query:
                    conditions.append("keepa_drop_percent >= ?")
                    params.append(float(query["min_drop"][0]))

                if "min_virality" in query:
                    conditions.append("virality_score >= ?")
                    params.append(int(query["min_virality"][0]))

                if "search" in query and query["search"][0]:
                    conditions.append("(title LIKE ? OR brand LIKE ? OR sub_category_name LIKE ?)")
                    term = f"%{query['search'][0]}%"
                    params.extend([term, term, term])

                limit = int(query.get("limit", [24])[0])
                offset = int(query.get("offset", [0])[0])

                sort_order = "keepa_drop_percent DESC"
                sort_param = query.get("sort", ["drop"])[0]
                if sort_param == "price_asc":
                    sort_order = "current_price ASC"
                elif sort_param == "price_desc":
                    sort_order = "current_price DESC"
                elif sort_param == "atl":
                    sort_order = "(current_price - all_time_low) ASC, keepa_drop_percent DESC"
                elif sort_param == "cycle":
                    sort_order = "is_cyclical DESC, cycle_days ASC"

                where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
                sql = f"""
                    SELECT * FROM products_catalog
                    {where_clause}
                    ORDER BY {sort_order}
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])

                cur.execute(sql, params)
                products = [dict(r) for r in cur.fetchall()]

                # Count total
                count_sql = f"SELECT COUNT(*) FROM products_catalog {where_clause}"
                cur.execute(count_sql, params[:-2])
                total_matched = cur.fetchone()[0]

                self._send_json(200, {
                    "success": True,
                    "total_matched": total_matched,
                    "count": len(products),
                    "limit": limit,
                    "offset": offset,
                    "products": products
                })

            elif path == "/api/deals":
                limit = int(query.get("limit", [20])[0])
                cur.execute("""
                    SELECT * FROM products_catalog
                    ORDER BY keepa_drop_percent DESC
                    LIMIT ?
                """, (limit,))
                deals = [dict(r) for r in cur.fetchall()]
                self._send_json(200, {"success": True, "deals": deals})

            elif path == "/api/stats":
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_products,
                        SUM(is_cyclical) as total_cyclical,
                        COUNT(*) - SUM(is_cyclical) as total_non_cyclical,
                        ROUND(AVG(current_price), 2) as overall_avg_price,
                        ROUND(SUM(est_monthly_affiliate_pool), 2) as total_monthly_affiliate_market_pool,
                        ROUND(AVG(hist_cagr_2022_2025), 1) as market_cagr_2022_2025,
                        ROUND(AVG(future_cagr_2026_2030), 1) as market_cagr_2026_2030
                    FROM products_catalog
                """)
                stats = dict(cur.fetchone())
                self._send_json(200, {"success": True, "stats": stats})

            elif path == "/api/export/posttap.csv":
                csv_path = os.path.join(BASE_DIR, "data", "offertissimesconti_posttap_export.csv")
                if os.path.exists(csv_path):
                    with open(csv_path, "rb") as f:
                        content = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="offertissimesconti_posttap_export.csv"')
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    self._send_json(404, {"error": "File di export non trovato"})
                    return

            elif path == "/api/live_price":
                asin = query.get("asin", [""])[0]
                if not asin:
                    self._send_json(400, {"success": False, "error": "Parametro 'asin' obbligatorio"})
                    return
                from core.amazon_live_price_fetcher import AmazonLivePriceFetcher
                data = AmazonLivePriceFetcher.fetch_asin(asin)
                self._send_json(200, data)

            elif path == "/api/health":
                self._send_json(200, {"status": "healthy", "brand": "OFFERTISSIMESCONTI", "version": "2.0"})

            else:
                self._send_json(404, {"error": "Endpoint non trovato"})

        finally:
            conn.close()

    def do_POST(self):
        if self.path == "/api/track":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
                user_id = payload.get("user_id", "guest_user")
                channel = payload.get("channel", "app_push")
                product_id = payload.get("product_id")
                target_price = float(payload.get("target_price", 0))

                if not product_id or target_price <= 0:
                    self._send_json(400, {"error": "Parametri non validi"})
                    return

                # Salva in tracking database
                with sqlite3.connect(DB_PATH) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO user_alerts (user_id, channel, product_id, target_price)
                        VALUES (?, ?, ?, ?)
                    """, (user_id, channel, product_id, target_price))
                    conn.commit()

                self._send_json(200, {
                    "success": True, 
                    "message": f"Allerta registrata con successo per {product_id} a €{target_price:.2f}"
                })
            except Exception as e:
                self._send_json(400, {"error": str(e)})
        else:
            self._send_json(404, {"error": "Endpoint not found"})

def run_server(port: int = 8000):
    server = HTTPServer(("0.0.0.0", port), OffertissimeScontiServer)
    print(f"🚀 OFFERTISSIMESCONTI Server attivo!")
    print(f"👉 Visita il sito web su: http://localhost:{port}")
    print(f"👉 API endpoint attivi su: http://localhost:{port}/api/products")
    server.serve_forever()

if __name__ == "__main__":
    run_server(8000)
