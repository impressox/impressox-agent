FROM python:3.12-slim

WORKDIR /app
COPY run_code.py requirements.txt .

RUN pip install -r requirements.txt --no-cache-dir

ENTRYPOINT ["python", "run_code.py"]
