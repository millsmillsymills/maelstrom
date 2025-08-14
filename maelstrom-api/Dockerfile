FROM python:3.12-slim-bookworm

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import sys,urllib.request;\n\
try:\n\
  r=urllib.request.urlopen('http://localhost:8000/health', timeout=5);\n\
  sys.exit(0 if getattr(r,'status',200)==200 else 1)\n\
except Exception:\n\
  sys.exit(1)"

# Non-root user
RUN useradd --create-home --shell /usr/sbin/nologin api_user
USER api_user

# Expose port
EXPOSE 8000

# Run as non-root
USER api_user

# Run the application
CMD ["python", "main.py"]
