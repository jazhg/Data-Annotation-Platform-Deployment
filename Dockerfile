FROM python:3.13-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY annotator ./annotator
COPY config ./config
COPY templates ./templates
COPY Images ./Images
COPY manage.py ./
COPY gunicorn.conf.py ./
RUN DJANGO_DEBUG=1 uv run manage.py collectstatic --noinput
RUN useradd --uid 10001 --create-home app
USER app
ENV DJANGO_SETTINGS_MODULE=config.settings
EXPOSE 8000
CMD ["/app/.venv/bin/gunicorn", "config.wsgi:application", "--config", "gunicorn.conf.py"]
