FROM python:3.12-slim
WORKDIR /app
COPY server.py index.html ./
RUN mkdir -p /data && useradd --system --uid 10001 arena && chown -R arena:arena /app /data
USER arena
ENV ARENA_DB=/data/multiplicative.sqlite3 PORT=8000
EXPOSE 8000
CMD ["python", "server.py", "--host", "0.0.0.0"]
