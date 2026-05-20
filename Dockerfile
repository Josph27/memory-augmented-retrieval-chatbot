FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OPENAI_API_KEY=dummy
ENV OPENAI_BASE_URL=http://host.docker.internal:11434/v1
ENV MODEL_NAME=qwen2.5:3b
ENV DATABASE_PATH=/app/data/chatbot.db
ENV RECENT_MESSAGE_LIMIT=12

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py chainlit.md ./
COPY src ./src

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
