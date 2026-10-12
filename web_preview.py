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
NOTICE = ('<div style="padding:12px 22px;background:#fff6e0;color:#654b12;'
          'font-weight:600;text-align:center">Hosted preview: GPS Time runs in your browser. '
          'Geoid/raster processing and DEM downloads are temporarily disabled until '
          'server security and resource limits are validated. '
          'Use the local v5.0 edition for calculations.</div>')
HTML = HTML.replace("<body>", "<body>" + NOTICE, 1)

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
