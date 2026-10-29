FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
# 供应链加固：requirements.txt 为 pip-compile 生成的哈希锁定文件，--require-hashes 强制校验每个包的哈希
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY . .

# 运行时数据目录（索引、会话）
RUN mkdir -p /app/data/kb /app/data/sessions

EXPOSE 8000

# 以模块方式运行，保证 `from app.xxx` 可解析
CMD ["sh", "-c", "python -m app.main"]
