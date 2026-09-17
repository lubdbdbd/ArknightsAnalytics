FROM node:22-alpine AS frontend
WORKDIR /frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN corepack prepare pnpm@11.19.0 --activate && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[platform]"
COPY data/processed ./data/processed
COPY config ./config
COPY sql ./sql
COPY data/manual/lifecycle_events.json ./data/manual/lifecycle_events.json
COPY data/public/expansion ./data/public/expansion
COPY reports/generated/public_expansion ./reports/generated/public_expansion
COPY --from=frontend /frontend/dist ./frontend/dist
ENV ARK_STATE_DB=/state/platform.db
EXPOSE 8765
CMD ["uvicorn", "arknights_merch_analytics.platform_api:app", "--host", "0.0.0.0", "--port", "8765"]
