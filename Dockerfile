FROM python:3.11-slim

WORKDIR /app

# Dependências do sistema operacional
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalação das dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cópia do código-fonte
COPY . .

# Diretórios de trabalho com permissões adequadas
RUN mkdir -p data_cache exports

EXPOSE 5001

ENV PORT=5001
ENV PYTHONUNBUFFERED=1

CMD ["python3", "app.py"]
