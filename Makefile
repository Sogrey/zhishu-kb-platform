.PHONY: help deps up down api worker frontend smoke fixtures

help:
	@echo "知枢开发命令："
	@echo "  make deps       安装 Python 依赖"
	@echo "  make up         启动 pg + valkey"
	@echo "  make down       停止依赖容器"
	@echo "  make api        启动 API (stub 模式)"
	@echo "  make worker     启动 Celery worker（非 stub）"
	@echo "  make frontend   启动前端"
	@echo "  make smoke      冒烟：上传样例并提问"
	@echo "  make fixtures   写入样例文档"

deps:
	cd server && python -m pip install -r requirements.txt

up:
	docker compose -f deploy/docker-compose.yml up -d

down:
	docker compose -f deploy/docker-compose.yml down

api:
	cd server && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd server && celery -A worker.celery_app.celery_app worker -l info

frontend:
	cd frontend && npm run dev

fixtures:
	python scripts/make_fixtures.py

smoke:
	python scripts/smoke.py
