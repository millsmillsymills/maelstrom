# Docker Management API

Secure FastAPI service to query and manage Docker using the Docker SDK.

- Auth: Bearer API key via `Authorization: Bearer <API_KEY>` (load from environment/.env)
- Endpoints:
  - GET `/containers` (filters: `status`, `label`, `name_regex`)
  - GET `/containers/{id}`
  - POST `/containers/{id}/start|stop|restart`
  - DELETE `/containers/{id}`
  - GET `/containers/{id}/stats`
  - POST `/containers/{id}/exec` {"cmd":["ls","-la","/"]}
  - GET `/system/info`
  - GET `/images` and `/system/images`
  - WS `/ws/logs/{id}` (query: `keyword`, `tail`)

## Run locally

```bash
export API_KEY=changeme
uvicorn docker_api.app.main:app --reload --port 8080
```

## Docker Compose

See `docker_api/docker-compose.yml` (mounts `/var/run/docker.sock`).
