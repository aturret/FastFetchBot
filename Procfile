web: gunicorn -k uvicorn.workers.UvicornWorker app.main:fastapi_application --preload --bind 0.0.0.0:${PORT}
