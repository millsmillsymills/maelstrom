# Health Check Endpoints (Reference)

Use these endpoints for readiness in checks and automation:

- Prometheus: `GET http://localhost:9090/-/ready`
- Grafana: `GET http://localhost:3000/api/health`
- Alertmanager: `GET http://localhost:9093/-/ready`
- InfluxDB 1.8: `GET http://localhost:8086/ping`
- Loki: `GET http://localhost:3100/ready`

Notes:
- Grafana’s root (`/`) may issue a 302 redirect to login; avoid HEAD on `/`.
- Alertmanager may return 405 to HEAD; use GET on `/-/ready`.
- Prefer probe jobs (blackbox) for end-to-end http checks where applicable.

