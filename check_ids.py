import re

with open('static/app.js', 'r', encoding='utf-8') as f:
    js = f.read()

with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

js_ids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))

missing = [i for i in js_ids if i not in html_ids]
print("Missing in HTML:", missing)
