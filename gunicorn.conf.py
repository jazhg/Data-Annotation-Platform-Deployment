"""Bind to Render's assigned port; local containers default to 8000."""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "8000")
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
accesslog = "-"
errorlog = "-"
# Let Django interpret forwarded HTTPS only when DJANGO_TRUST_PROXY is enabled.
forwarded_allow_ips = "*" if os.environ.get("DJANGO_TRUST_PROXY") == "1" else "127.0.0.1,::1"
