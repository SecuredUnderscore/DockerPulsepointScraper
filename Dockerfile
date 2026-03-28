FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Port flask runs on
EXPOSE 5020

ENV FLASK_APP=app.main:app
ENV FLASK_RUN_HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5020", "--no-reload]
