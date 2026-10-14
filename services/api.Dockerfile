# ourfos-api's image: the UI, and the API that serves it

# The UI, built where Node is, and only its files kept
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# The services' packages, all of them: one list for both images, though the API imports few
FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
COPY wheels/ wheels/
RUN pip install --no-cache-dir -r requirements.txt wheels/*.whl
COPY services/ ./
COPY --from=web /web/dist static/
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
