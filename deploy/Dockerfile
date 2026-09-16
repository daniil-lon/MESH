FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY css ./css
COPY js ./js
COPY icons ./icons
COPY index.html ./index.html
COPY admin.html ./admin.html
COPY manifest.json ./manifest.json
COPY sw.js ./sw.js

RUN mkdir -p /app/backend/data /app/uploads

ENV MESH_BASE_DIR=/app
ENV MESH_DATA_DIR=/app/backend/data
ENV MESH_UPLOADS_DIR=/app/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health',timeout=4).status==200 else 1)"

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]