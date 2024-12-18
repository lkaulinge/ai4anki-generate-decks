FROM python:3.12.8-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8579
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8579"]