"""Conservative web preview entry point; keep local geoid_web.py unchanged.
Online preview deliberately disallows DEM acquisition and local file-path access.
"""
from geoid_web import Handler
from http.server import ThreadingHTTPServer
from email.parser import BytesParser
from email.policy import default
import io
import os
import threading

MAX_UPLOAD = 12 * 1024 * 1024
SLOTS = threading.BoundedSemaphore(2)

class WebHandler(Handler):
    def do_GET(self):
        if self.path.split("?")[0] == "/":
            # The existing browser UI stays intact. The banner explains online limitations.
            html = self.server.web_html
            return self.reply(html, mime="text/html; charset=utf-8")
        return super().do_GET()

    def do_POST(self):
        route = self.path.split("?")[0]
        if route == "/dem":
            return self.reply({"error":"Online DEM downloading is not yet enabled. Use the local edition."}, 403)
        if route not in ("/run", "/inspect"):
            return self.reply({"error":"Not found"}, 404)
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply({"error":"Invalid request length"}, 400)
        if size <= 0 or size > MAX_UPLOAD:
            return self.reply({"error":"Online upload limit is 12 MB. For larger rasters, run the local edition."},413)
        if not SLOTS.acquire(blocking=False):
            return self.reply({"error":"The server is busy. Please try again later."},503)
        try:
            body = self.rfile.read(size)
            typ = self.headers.get("Content-Type", "")
            if not typ.startswith("multipart/form-data;"):
                return self.reply({"error":"Expected multipart form data"},400)
            message = BytesParser(policy=default).parsebytes(
                b"Content-Type: "+typ.encode("utf-8")+b"\r\nMIME-Version: 1.0\r\n\r\n"+body
            )
            for part in message.iter_parts():
                field = part.get_param("name",header="content-disposition")
                if field == "raster_path" and (part.get_payload(decode=True) or b"").strip():
                    return self.reply({"error":"Local filesystem paths are disabled in the hosted edition. Upload a small raster instead."},403)
            # Replay the validated request to the original scientific engine.
            self.rfile = io.BytesIO(body)
            return super().do_POST()
        finally:
            SLOTS.release()

if __name__ == "__main__":
    port=int(os.environ.get("PORT","10000"))
    with open("geoid_interface.html","r",encoding="utf-8") as stream:
        html=stream.read()
    notice = '<div style="padding:12px 20px;background:#fff7e5;color:#674b12;text-align:center;font-weight:600">Online preview: 12 MB upload limit. DEM downloads and local raster paths require the desktop version.</div>'
    html=html.replace("<body>","<body>"+notice,1)
    server=ThreadingHTTPServer(("0.0.0.0",port),WebHandler)
    server.web_html=html.encode("utf-8")
    print(f"Web preview listening on port {port}",flush=True)
    server.serve_forever()
