FROM python:3.11-slim

WORKDIR /app

# instalace závislostí
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# <-- Přidej sem toto:
RUN playwright install chromium --with-deps
# kopie všech souborů projektu
COPY . .

# výchozí příkaz (přepisovaný docker-compose)
CMD ["echo", "Image built successfully!"]