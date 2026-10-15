FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY src ./src
COPY frontend ./frontend
COPY examples ./examples
RUN pip install --no-cache-dir .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "mediscribe.main:app", "--host", "0.0.0.0", "--port", "8000"]
