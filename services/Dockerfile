FROM python:3.13-slim
WORKDIR /app
# requirements.txt is generated from uv.lock at package time, never committed
COPY requirements.txt .
# The connector, built by make package: the image never fetches it (docs/phase11/adr.md 1)
COPY wheels/ wheels/
RUN pip install --no-cache-dir -r requirements.txt wheels/*.whl
COPY . .
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
