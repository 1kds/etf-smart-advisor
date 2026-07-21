# ─── 빌드 단계 ───
FROM python:3.11-slim AS builder

WORKDIR /app

# 시스템 의존성 설치 (PyMuPDF용)
RUN apt-get update && apt-get install -y \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

# 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── 실행 단계 ───
FROM python:3.11-slim

WORKDIR /app

# 빌드 단계에서 설치된 패키지 복사
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 앱 코드 복사 (.env 제외는 .dockerignore에서 처리)
COPY . .

# Streamlit 설정 (프로덕션 환경)
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 포트 노출
EXPOSE 8080

# 실행 명령
CMD ["python", "-m", "streamlit", "run", "app.py", \
     "--server.port=8080", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
