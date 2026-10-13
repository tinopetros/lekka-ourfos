# The UI, built where Node is, and only its files kept: the API serves them (docs/phase13/adr.md 7)
FROM node:24-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ourfos-services, and ourfos-api from the same image with its own command (docs/phase13/adr.md 2)
FROM python:3.13-slim
WORKDIR /app
# requirements.txt is generated from uv.lock at package time, never committed
COPY requirements.txt .
# The connector, built by make package: the image never fetches it (docs/phase11/tdd.md, step 1)
COPY wheels/ wheels/
RUN pip install --no-cache-dir -r requirements.txt wheels/*.whl
COPY . .
RUN rm -rf web
COPY --from=web /web/dist static/
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
