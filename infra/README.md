# SignalDACH Infrastructure

## Quick Start (Development)

```bash
# Core services only (DB, Redis, Backend, Frontend)
docker compose up -d

# With monitoring stack (Prometheus + Grafana)
docker compose --profile monitoring up -d
```

## Services

| Service        | URL                        | Credentials       |
|----------------|----------------------------|--------------------|
| Backend API    | http://localhost:8000      | -                  |
| Frontend       | http://localhost:3000      | -                  |
| Prometheus     | http://localhost:9090      | -                  |
| Grafana        | http://localhost:3030      | admin / signaldach_dev |

## Monitoring

Grafana dashboards and Prometheus datasource are auto-provisioned on startup.

- **Dashboard**: "SignalDACH Overview" is loaded automatically
- **Alerting rules**: Defined in `prometheus_alerts.yml`, evaluated every 15s

### Prometheus Metrics (exposed at `/monitoring/metrics`)

| Metric | Type | Description |
|--------|------|-------------|
| `signaldach_http_requests_total` | counter | Total HTTP requests |
| `signaldach_http_errors_total` | counter | Total 5xx errors |
| `signaldach_http_latency_avg_ms` | gauge | Average request latency |
| `signaldach_ws_connections_active` | gauge | Active WebSocket connections |
| `signaldach_ws_connections_total` | counter | Total WS connections since start |
| `signaldach_signals_generated_total` | counter | AI signals generated |
| `signaldach_items_total` | counter | Items ingested by scrapers |
| `signaldach_scrapes_total` | counter | Total scrape runs |
| `signaldach_scrape_errors_total` | counter | Total scrape errors |
| `signaldach_uptime_seconds` | gauge | Seconds since startup |
| `signaldach_scrape_duration_seconds` | gauge | Last scrape duration per source |
| `signaldach_endpoint_latency_p50_ms` | gauge | 50th percentile latency per path |
| `signaldach_endpoint_latency_p95_ms` | gauge | 95th percentile latency per path |

### Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| HighErrorRate | > 5% errors over 5m | critical |
| HighLatency | Avg latency > 2s for 5m | warning |
| ScraperFailureRate | > 20% scrape failures for 10m | warning |
| NoScrapeActivity | No scrapes for 1h | warning |
| BackendDown | Metrics endpoint unreachable for 2m | critical |
| HighWebSocketConnections | > 200 active WS for 5m | warning |

## Volumes

- `signaldach-pgdata` - PostgreSQL data
- `signaldach-redis` - Redis AOF persistence
- `signaldach-prometheus` - Prometheus TSDB
- `signaldach-grafana` - Grafana state
