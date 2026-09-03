FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY meetifier ./meetifier
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "-m", "meetifier"]
