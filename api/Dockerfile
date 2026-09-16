FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY api/requirements.txt api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt
COPY api/ api/
COPY tools/validate_contrib.py tools/validate_contrib.py
COPY json-schema/ json-schema/
COPY contrib/ contrib/
ARG SOURCE_REVISION
RUN python -m api.hosted.catalog --revision "$SOURCE_REVISION" --output api/catalog.json
RUN useradd --uid 10001 --create-home apiuser
USER apiuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4)"
CMD ["uvicorn", "api.hosted.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log", "--no-proxy-headers"]
