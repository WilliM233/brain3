FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN addgroup --system brain3 && adduser --system --ingroup brain3 brain3

# Copy migration config and scripts
COPY alembic.ini .
COPY alembic/ alembic/

# Copy application code
COPY app/ app/

# Copy and prepare entrypoint
COPY scripts/entrypoint.sh scripts/entrypoint.sh
RUN chmod +x scripts/entrypoint.sh

# Switch to non-root user
USER brain3

EXPOSE 8000

ENTRYPOINT ["scripts/entrypoint.sh"]
