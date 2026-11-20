FROM python:3.12-slim

WORKDIR /srv
# 上传的视频转成 720p MP4 再存（app/media.py）
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
RUN pip install --no-cache-dir .

EXPOSE 8000
# 非 dev 环境启动前先迁移数据库（非 dev 不会自动建表）；dev 沿用应用自带的自动建表与种子数据。
CMD ["sh", "-c", "[ \"$APP_ENV\" = dev ] || alembic upgrade head; exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
