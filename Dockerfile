# Use Python 3.11 as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create requirements.txt with necessary dependencies
RUN echo "apscheduler==3.10.4\n\
python-telegram-bot==20.7\n\
tweepy==4.14.0\n\
python-dotenv==1.0.0\n\
requests==2.31.0\n\
langchain==0.1.0\n\
chromadb==0.4.22\n\
sentence-transformers==2.2.2\n\
pydantic==2.5.2\n\
fastapi==0.104.1\n\
uvicorn==0.24.0" > requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python", "workers/rag_processor/scheduler.py"] 