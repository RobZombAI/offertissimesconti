"""
Test Suite: Frontend Web Assets Validation (web/index.html, style.css, app.js)
Verifica l'integrità strutturale del frontend, requisiti legali di Amazon Associates,
accessibilità semantica HTML5, responsive CSS e coerenza degli script.
"""

import unittest
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(BASE_DIR, "web")

class TestFrontendAssets(unittest.TestCase):
    def test_index_html_exists_and_valid_doctype(self):
        path = os.path.join(WEB_DIR, "index.html")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertTrue(content.strip().startswith("<!DOCTYPE html>"), "Manca DOCTYPE html5")
        self.assertIn('<html lang="it">', content, "Manca attributo lang='it'")

    def test_meta_tags_and_seo(self):
        path = os.path.join(WEB_DIR, "index.html")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('<meta name="viewport"', content, "Manca meta viewport per mobile")
        self.assertIn('<meta name="description"', content, "Manca meta description per SEO")
        self.assertIn("OffertissimeSconti", content, "Titolo o brand mancante")

    def test_mandatory_amazon_associates_disclosure(self):
        path = os.path.join(WEB_DIR, "index.html")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Amazon richiede esplicitamente la dicitura di affiliazione
        self.assertIn("In qualità di Affiliato Amazon", content, "Manca il disclaimer obbligatorio di Amazon Associates")
        self.assertIn("riceve un guadagno", content)

    def test_critical_dom_elements_present(self):
        path = os.path.join(WEB_DIR, "index.html")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        required_ids = [
            "productsGrid", "resultsCount", "categorySelect",
            "discountSelect", "searchInput", "searchBtn",
            "categoryChips", "alertDialog", "alertForm",
            "targetPriceInput", "contactInput"
        ]
        for el_id in required_ids:
            self.assertIn(f'id="{el_id}"', content, f"Elemento DOM critico mancante: id='{el_id}'")

    def test_css_styles_integrity(self):
        path = os.path.join(WEB_DIR, "style.css")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            css = f.read()

        # Verifica CSS variables e responsive layout
        self.assertIn(":root", css)
        self.assertIn("--primary:", css)
        self.assertIn("@media (max-width:", css, "Mancano media queries per responsive mobile")
        self.assertIn("display: grid", css)
        self.assertIn("display: flex", css)

    def test_javascript_app_integrity(self):
        path = os.path.join(WEB_DIR, "app.js")
        self.assertTrue(os.path.exists(path))
        with open(path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("DOMContentLoaded", js)
        self.assertIn("/api/categories", js)
        self.assertIn("/api/products", js)
        self.assertIn("/api/track", js)
        self.assertTrue("generateRadarSparkline" in js or "generateKeepaSparkline" in js, "Manca funzione generatore sparkline radar")

if __name__ == "__main__":
    unittest.main()
