# 3D Ring Generator

AI-сервис для генерации 3D-моделей колец по текстовому описанию.

## Требования

- Python ≥ 3.12
- uv или pip
- Docker и Docker Compose

## Начало работы

Клонируйте репозиторий и перейдите в папку

`git clone https://github.com/N1k1f0rM/3d-ring.git`
`cd 3d-ring`
`mv env.example .env`

Установите зависимости 

`uv sync`

Запуск инфраструктуры

`cd infra/`
`docker compose --env-file ../.env up`

Перейдите по адресу и наслаждайтесь использованием

`localhost:8501`

## Порты и сервисы

| Сервис | Доступ |
|--------|--------|
| **Backend** | [http://localhost:8000](http://localhost:8000) |
| **Frontend** | [http://localhost:8501](http://localhost:8501) |
| **PostgreSQL** | [http://localhost:5432] |
| **MinIO (API)** | [http://localhost:9002] |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) |
| **Prometheus** | [http://localhost:9090](http://localhost:9090) |
| **Grafana** | [http://localhost:3000](http://localhost:3000) |
| **Node Exporter** | [http://localhost:9100/metrics] |
| **DCGM Exporter** | [http://localhost:9400/metrics] |

### 🔑 Быстрый доступ

```bash
# Backend API
curl http://localhost:8000/generate?prompt="silver%20ring"

# Метрики Prometheus
curl http://localhost:9090/metrics

# Health check MinIO
curl http://localhost:9002/minio/health/live
