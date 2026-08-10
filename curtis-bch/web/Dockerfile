FROM python:3.12-alpine
WORKDIR /app
COPY app.py ckpool_user_stats.py ./
COPY index.html app.css app.js icon.svg ./
RUN mkdir -p /app/static && \
    cp /app/index.html /app/static/index.html && \
    cp /app/app.css /app/static/app.css && \
    cp /app/app.js /app/static/app.js && \
    cp /app/icon.svg /app/static/icon.svg
ENV PYTHONUNBUFFERED=1 \
    STATIC_DIR=/app/static \
    APP_VERSION=0.1.0 \
    APP_CHANNEL=CURTIS
EXPOSE 3000
CMD ["python", "/app/app.py"]
