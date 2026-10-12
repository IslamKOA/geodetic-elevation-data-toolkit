"""Restricted web preview for Render. The local scientific application is unchanged."""
import os
from pathlib import Path
from flask import Flask, Response, jsonify, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
app.config["MAX_FORM_MEMORY_SIZE"] = 32 * 1024

HTML = (ROOT / "geoid_interface.html").read_text(encoding="utf-8")
HTML = HTML.replace("Research software · v2.4", "Research software · v5.0")
HTML = HTML.replace("</head>", '<link rel="stylesheet" href="/web-style.css"></head>', 1)
HTML = HTML.replace(
    '<div class="container">',
    '<div class="container"><div class="web-status" role="status"><span><span class="status-dot"></span><strong>Web preview</strong> · Interface and GPS Time available. Scientific processing is being prepared for hosted use.</span><a href="https://github.com/IslamKOA/geodetic-elevation-data-toolkit" target="_blank" rel="noopener noreferrer">View source ↗</a></div>',
    1,
)
HTML = HTML.replace(
    'Local browser utility. Files are processed by Python on your computer through <code>127.0.0.1</code>.',
    'Hosted web preview. Scientific processing is currently disabled; the local edition remains available for full calculations.',
)

@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' data:; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    )
    return response

@app.get("/")
def index():
    return Response(HTML, content_type="text/html; charset=utf-8")

@app.get("/web-style.css")
def stylesheet():
    return Response((ROOT / "web_style.css").read_text(encoding="utf-8"), content_type="text/css; charset=utf-8")

@app.get("/health")
def health():
    return jsonify(ok=True, service="geodetic-toolkit-web-preview")

@app.get("/assets/<name>")
def asset(name):
    if name not in {"uga.png", "inrae.png", "najah.png", "institute.png"}:
        return jsonify(error="Not found"), 404
    return send_file(ROOT / "assets" / name, mimetype="image/png")

@app.post("/run")
@app.post("/dem")
@app.post("/inspect")
def disabled():
    return jsonify(error=("Hosted scientific processing is not yet enabled. "
                          "Please use the local toolkit while the web backend is validated.")), 503

@app.errorhandler(RequestEntityTooLarge)
def oversize(_):
    return jsonify(error="Request too large for the preview."), 413
