FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 运行时数据目录（索引、会话）
RUN mkdir -p /app/data/kb /app/data/sessions

EXPOSE 8000

# 以模块方式运行，保证 `from app.xxx` 可解析
CMD ["sh", "-c", "python -m app.main"]
