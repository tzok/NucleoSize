FROM python:3.14-slim

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY main.py .

VOLUME /data

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EXPOSE 8000
