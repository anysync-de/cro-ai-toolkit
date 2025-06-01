from flask import Flask, render_template, request, jsonify
import json
import os
import threading
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# Hilfsfunktion für das Crawling

def crawl_website(start_url, max_categories=50, max_products_per_category=5):
    visited = set()
    result = {
        'homepage': start_url,
        'category_pages': [],
        'product_pages': [],
        'cart_pages': [],
        'checkout_pages': [],
        'content_pages': []
    }
    try:
        resp = requests.get(start_url, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # 1. Kategorieseiten aus Hauptnavigation (max 50)
        category_links = set()
        for nav in soup.find_all(['nav', 'ul', 'div'], class_=re.compile(r'(nav|menu|main|categories|hauptnavigation|kategorien)', re.I)):
            for a in nav.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = requests.compat.urljoin(start_url, href)
                if href.startswith(start_url) and href != start_url and href not in category_links:
                    # Heuristik: keine Service/Info/Content-Links, keine Warenkorb/Checkout
                    if not re.search(r'(service|hilfe|blog|impressum|kontakt|warenkorb|checkout|kasse|zahlung|agb|datenschutz|newsletter|login|faq|content|about|ueber-uns)', href, re.I):
                        category_links.add(href)
                if len(category_links) >= max_categories:
                    break
            if len(category_links) >= max_categories:
                break
        # Fallback: Wenn keine Kategorien gefunden, nimm alle Links von der Startseite, die wie Kategorie aussehen
        if not category_links:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    href = requests.compat.urljoin(start_url, href)
                if href.startswith(start_url) and href != start_url and href not in category_links:
                    if re.search(r'(mode|herren|damen|schuhe|kinder|wohnen|technik|sale|neu|trend|shop|kategorie|category|plp)', href, re.I):
                        category_links.add(href)
                if len(category_links) >= max_categories:
                    break
        result['category_pages'] = list(category_links)[:max_categories]
        # 2. Produktdetailseiten pro Kategorie (max 5 pro Kategorie)
        product_links = set()
        for cat_url in result['category_pages']:
            try:
                cat_resp = requests.get(cat_url, timeout=8)
                cat_soup = BeautifulSoup(cat_resp.text, 'html.parser')
                found = 0
                for a in cat_soup.find_all('a', href=True):
                    href = a['href']
                    if href.startswith('/'):
                        href = requests.compat.urljoin(cat_url, href)
                    if href.startswith(start_url) and href != cat_url and href not in product_links:
                        # Heuristik: Produktseiten haben oft Produktnummern, /artikel/, /p/, /product/, /details/
                        if re.search(r'(artikel|product|pdp|details|sku|id=|/p/|/prd/|/detail/|/artikel/|/prod/|/item/)', href, re.I) or re.search(r'\d{6,}', href):
                            product_links.add(href)
                            found += 1
                    if found >= max_products_per_category:
                        break
            except Exception:
                continue
        result['product_pages'] = list(product_links)
        # 3. Warenkorb/Checkout/Content wie bisher
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                href = requests.compat.urljoin(start_url, href)
            if href.startswith(start_url):
                if re.search(r'(cart|warenkorb)', href, re.I):
                    result['cart_pages'].append(href)
                elif re.search(r'(checkout|kasse|zahlung)', href, re.I):
                    result['checkout_pages'].append(href)
                elif re.search(r'(blog|about|ueber-uns|impressum|content)', href, re.I):
                    result['content_pages'].append(href)
        # Nur eindeutige URLs
        for key in result:
            if isinstance(result[key], list):
                result[key] = list(dict.fromkeys(result[key]))
    except Exception:
        pass
    return result

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_project', methods=['POST'])
def create_project():
    data = request.get_json()
    project = {
        'projectName': data.get('projectName'),
        'websiteUrl': data.get('websiteUrl'),
        'kpis': data.get('kpis'),
        'brandGuidelines': data.get('brandGuidelines'),
        'personas': data.get('personas'),
        'site_structure': None
    }
    projects_file = 'projects.json'
    if os.path.exists(projects_file):
        with open(projects_file, 'r', encoding='utf-8') as f:
            try:
                projects = json.load(f)
            except json.JSONDecodeError:
                projects = []
    else:
        projects = []
    projects.append(project)
    with open(projects_file, 'w', encoding='utf-8') as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)
    # Starte das Crawling im Hintergrund
    def crawl_and_update():
        structure = crawl_website(project['websiteUrl'])
        # Lade Projekte erneut, um Race Conditions zu vermeiden
        with open(projects_file, 'r', encoding='utf-8') as f:
            projects_latest = json.load(f)
        # Finde das zuletzt gespeicherte Projekt (by name & url)
        for p in projects_latest[::-1]:
            if p['projectName'] == project['projectName'] and p['websiteUrl'] == project['websiteUrl']:
                p['site_structure'] = structure
                break
        with open(projects_file, 'w', encoding='utf-8') as f:
            json.dump(projects_latest, f, ensure_ascii=False, indent=2)
    threading.Thread(target=crawl_and_update).start()
    return jsonify({'message': 'Projekt gespeichert, Crawling läuft im Hintergrund.'}), 200

@app.route('/project_status')
def project_status():
    project_name = request.args.get('projectName')
    website_url = request.args.get('websiteUrl')
    projects_file = 'projects.json'
    if not (project_name and website_url):
        return jsonify({'error': 'Missing parameters'}), 400
    if not os.path.exists(projects_file):
        return jsonify({'error': 'No projects found'}), 404
    with open(projects_file, 'r', encoding='utf-8') as f:
        try:
            projects = json.load(f)
        except json.JSONDecodeError:
            return jsonify({'error': 'Corrupt projects file'}), 500
    for p in projects[::-1]:
        if p['projectName'] == project_name and p['websiteUrl'] == website_url:
            if p.get('site_structure'):
                return jsonify({'status': 'done', 'site_structure': p['site_structure']}), 200
            else:
                return jsonify({'status': 'crawling'}), 200
    return jsonify({'error': 'Project not found'}), 404

if __name__ == '__main__':
    app.run(debug=True) 