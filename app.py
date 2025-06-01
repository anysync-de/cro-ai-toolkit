from flask import Flask, render_template, request, jsonify
import json
import os

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_project', methods=['POST'])
def create_project():
    data = request.get_json()
    project = {
        'projectName': data.get('projectName'),
        'websiteUrl': data.get('websiteUrl')
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
    return jsonify({'message': 'Projekt gespeichert'}), 200

if __name__ == '__main__':
    app.run(debug=True) 