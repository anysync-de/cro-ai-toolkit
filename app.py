from flask import Flask, render_template, request, jsonify
import json
import os
import threading
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# Hilfsfunktion für das Crawling

def crawl_website(start_url, max_pages=50, max_depth=2):
    visited = set()
    queue = [(start_url, 0)]
    result = {
        'homepage': None,
        'category_pages': [],
        'product_pages': [],
        'cart_pages': [],
        'checkout_pages': [],
        'content_pages': []
    }
    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            visited.add(url)
            # Seitentyp-Erkennung (vereinfachte Muster)
            if depth == 0:
                result['homepage'] = url
            elif re.search(r'(kategorie|category|shop|products|plp)', url, re.I):
                result['category_pages'].append(url)
            elif re.search(r'(produkt|product|pdp|item|detail)', url, re.I):
                result['product_pages'].append(url)
            elif re.search(r'(cart|warenkorb)', url, re.I):
                result['cart_pages'].append(url)
            elif re.search(r'(checkout|kasse|zahlung)', url, re.I):
                result['checkout_pages'].append(url)
            elif re.search(r'(blog|about|ueber-uns|impressum|content)', url, re.I):
                result['content_pages'].append(url)
            # Links sammeln
            for a in soup.find_all('a', href=True):
                link = a['href']
                if link.startswith('/'):
                    link = requests.compat.urljoin(url, link)
                if link.startswith(start_url) and link not in visited:
                    queue.append((link, depth + 1))
        except Exception:
            continue
    # Nur eindeutige URLs
    for key in result:
        if isinstance(result[key], list):
            result[key] = list(dict.fromkeys(result[key]))
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

if __name__ == '__main__':
    app.run(debug=True) 