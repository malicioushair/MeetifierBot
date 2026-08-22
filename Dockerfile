FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY meetifier ./meetifier
RUN pip install --no-cache-dir .
CMD ["python", "-m", "meetifier"]
