# One image, one process: company systems + assistant API + built web app (see server.py)
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npx vite build

FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY world world
COPY eval eval
COPY server.py .
COPY --from=web /web/dist web/dist
RUN mkdir -p /data
ENV PORT=8000 DOCFLOW_DB=/data/nowhere.db
EXPOSE 8000
CMD ["sh", "-c", "uvicorn server:combined --host 0.0.0.0 --port ${PORT}"]
