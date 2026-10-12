# Hosted web preview (deployment branch)

This branch is an **experimental web preview**, not a public-production release.

- Start command: `python web_app.py`
- Dependency installation: `pip install -r requirements.txt`
- Use Render Python runtime; set `PORT` as supplied by the platform.
- First deployment should be restricted to the owner's testing, not announced as a public service.
- Maximum upload: 12 MB. Local filesystem raster paths and remote DEM acquisition are blocked.
- Advanced / Legacy links point to the GitHub source folder; private access still requires GitHub authorization.

## Required work before public launch

1. Replace the built-in HTTP server with a production-grade WSGI/ASGI implementation.
2. Add strict AOI geometry and raster pixel-count quotas, worker/process timeouts, and file retention cleanup.
3. Validate content type and isolate processing in separate low-privilege workers with resource limits.
4. Avoid relying on ephemeral local disk for large results; use managed object storage.
5. Verify the licensing and redistribution rights for bundled RAF20 data and institutional images.
6. Test all workflows with realistic geodetic validation cases and confirm server costs.
7. Evaluate authentication, rate limiting, abuse prevention, observability, and HTTPS settings.

The tested local toolkit on `main` remains the recommended option for high-resolution DEMs.
