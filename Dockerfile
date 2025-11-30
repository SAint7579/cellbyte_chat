# Combined Dockerfile for CellByte Chat
# Runs both backend (FastAPI) and frontend (Next.js)

# =============================================================================
# Stage 1: Build Frontend
# =============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Create public dir if it doesn't exist (Next.js standalone might not include it)
RUN mkdir -p /frontend/public

# =============================================================================
# Stage 2: Final Image
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install Node.js and supervisor
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    supervisor \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY backend/ ./backend/
COPY .env* ./

# Copy built frontend (standalone output)
COPY --from=frontend-builder /frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /frontend/.next/static ./frontend/.next/static

# Copy public folder (might be empty, but won't fail now)
COPY --from=frontend-builder /frontend/public ./frontend/public

# Create directories for persistent data (will be overwritten by volumes)
RUN mkdir -p /app/database /app/history /app/logs

# Supervisor config
RUN echo '[supervisord]\n\
nodaemon=true\n\
logfile=/dev/null\n\
logfile_maxbytes=0\n\
\n\
[program:backend]\n\
command=python -m uvicorn api:app --host 0.0.0.0 --port 8000\n\
directory=/app/backend\n\
environment=PYTHONPATH="/app/backend:/app/backend/src"\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
\n\
[program:frontend]\n\
command=node server.js\n\
directory=/app/frontend\n\
environment=PORT="3000",HOSTNAME="0.0.0.0",API_URL="http://localhost:8000"\n\
stdout_logfile=/dev/stdout\n\
stdout_logfile_maxbytes=0\n\
stderr_logfile=/dev/stderr\n\
stderr_logfile_maxbytes=0\n\
' > /etc/supervisor/conf.d/cellbyte.conf

# Expose ports
EXPOSE 3000 8000

# Run supervisor
CMD ["supervisord", "-c", "/etc/supervisor/supervisord.conf"]
