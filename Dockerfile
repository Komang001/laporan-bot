FROM python:3.12-slim

WORKDIR /app

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY . .

ENV PYTHONPATH=/app

CMD ["python", "DispatchAssistant/scripts/run_jadwal_bot.py"]
