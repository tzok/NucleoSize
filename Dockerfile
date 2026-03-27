FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py .

VOLUME /data

HEALTHCHECK --interval=60s --timeout=5s --start-period=60s --start-interval=1s --retries=3 \
  CMD ["/bin/sh", "-c", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" 2>/dev/null || exit 1"]

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EXPOSE 8000
