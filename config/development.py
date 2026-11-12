"""Explicit settings for local manage.py commands, never the WSGI deployment."""
import os

os.environ.setdefault('DJANGO_DEBUG', '1')
from .settings import *  # noqa: F403,E402
