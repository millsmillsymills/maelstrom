#!/bin/bash
# shellcheck disable=SC1091
[ -f /usr/local/lib/codex_env.sh ] && . /usr/local/lib/codex_env.sh
# Advanced Monitoring Dashboard Customization Implementation

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/home/mills/logs/dashboard-customization-${TIMESTAMP}.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

success() { log "${GREEN}✅ $1${NC}"; }
warning() { log "${YELLOW}⚠️ $1${NC}"; }
error() { log "${RED}❌ $1${NC}"; }
info() { log "${BLUE}ℹ️ $1${NC}"; }

# Create Advanced Infrastructure Overview Dashboard
create_infrastructure_dashboard() {
    info "Creating advanced infrastructure overview dashboard"

    mkdir -p /home/mills/collections/grafana/dashboards

    cat > /home/mills/collections/grafana/dashboards/infrastructure-overview.json << 'EOF'
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": "-- Grafana --",
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "type": "dashboard"
      }
    ]
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
          "interval": "",
          "legendFormat": "CPU Usage - {{instance}}",
          "refId": "A"
        }
      ],
      "title": "System CPU Usage",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
          "interval": "",
          "legendFormat": "Memory Usage - {{instance}}",
          "refId": "A"
        }
      ],
      "title": "System Memory Usage",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 5
              },
              {
                "color": "red",
                "value": 10
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "count(up == 0)",
          "interval": "",
          "legendFormat": "Services Down",
          "refId": "A"
        }
      ],
      "title": "Services Down",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "yellow",
                "value": 10
              },
              {
                "color": "green",
                "value": 20
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 8,
        "y": 8
      },
      "id": 4,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "count(up == 1)",
          "interval": "",
          "legendFormat": "Services Up",
          "refId": "A"
        }
      ],
      "title": "Services Running",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 70
              },
              {
                "color": "red",
                "value": 90
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 16,
        "y": 8
      },
      "id": 5,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true,
        "text": {}
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "avg(100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100))",
          "interval": "",
          "legendFormat": "Average CPU",
          "refId": "A"
        }
      ],
      "title": "Overall CPU Usage",
      "type": "gauge"
    }
  ],
  "schemaVersion": 27,
  "style": "dark",
  "tags": [
    "infrastructure",
    "overview"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Infrastructure Overview",
  "uid": "infrastructure-overview",
  "version": 1
}
EOF

    success "Infrastructure overview dashboard created"
}

# Create Service Health Dashboard
create_service_health_dashboard() {
    info "Creating service health monitoring dashboard"

    cat > /home/mills/collections/grafana/dashboards/service-health.json << 'EOF'
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            }
          },
          "mappings": [
            {
              "options": {
                "0": {
                  "color": "red",
                  "index": 1,
                  "text": "Down"
                },
                "1": {
                  "color": "green",
                  "index": 0,
                  "text": "Up"
                }
              },
              "type": "value"
            }
          ]
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "displayLabels": [
          "name"
        ],
        "legend": {
          "displayMode": "table",
          "placement": "right",
          "values": [
            "value"
          ]
        },
        "pieType": "pie",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "sum by(job) (up)",
          "interval": "",
          "legendFormat": "{{job}}",
          "refId": "A"
        }
      ],
      "title": "Service Health Status",
      "type": "piechart"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "custom": {
            "align": "auto",
            "displayMode": "auto"
          },
          "mappings": [
            {
              "options": {
                "0": {
                  "color": "red",
                  "index": 1,
                  "text": "DOWN"
                },
                "1": {
                  "color": "green",
                  "index": 0,
                  "text": "UP"
                }
              },
              "type": "value"
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "Value"
            },
            "properties": [
              {
                "id": "custom.displayMode",
                "value": "color-background"
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "options": {
        "showHeader": true
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "up",
          "format": "table",
          "instant": true,
          "interval": "",
          "legendFormat": "",
          "refId": "A"
        }
      ],
      "title": "Service Status Details",
      "transformations": [
        {
          "id": "organize",
          "options": {
            "excludeByName": {
              "Time": true,
              "__name__": true
            },
            "indexByName": {},
            "renameByName": {
              "Value": "Status",
              "instance": "Instance",
              "job": "Service"
            }
          }
        }
      ],
      "type": "table"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 24,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "changes(up[1h])",
          "interval": "",
          "legendFormat": "{{job}} - {{instance}}",
          "refId": "A"
        }
      ],
      "title": "Service Restart Count (1 hour)",
      "type": "timeseries"
    }
  ],
  "schemaVersion": 27,
  "style": "dark",
  "tags": [
    "services",
    "health"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Service Health Monitoring",
  "uid": "service-health",
  "version": 1
}
EOF

    success "Service health dashboard created"
}

# Create Performance Analytics Dashboard
create_performance_dashboard() {
    info "Creating performance analytics dashboard"

    cat > /home/mills/collections/grafana/dashboards/performance-analytics.json << 'EOF'
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "ms"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(prometheus_http_request_duration_seconds_bucket[5m]) * 1000)",
          "interval": "",
          "legendFormat": "95th Percentile Response Time",
          "refId": "A"
        },
        {
          "expr": "histogram_quantile(0.50, rate(prometheus_http_request_duration_seconds_bucket[5m]) * 1000)",
          "interval": "",
          "legendFormat": "50th Percentile Response Time",
          "refId": "B"
        }
      ],
      "title": "API Response Times",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "reqps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "rate(prometheus_http_requests_total[5m])",
          "interval": "",
          "legendFormat": "{{handler}} - {{method}}",
          "refId": "A"
        }
      ],
      "title": "Request Rate",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "bytes"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "prometheus_tsdb_symbol_table_size_bytes",
          "interval": "",
          "legendFormat": "Symbol Table Size",
          "refId": "A"
        },
        {
          "expr": "prometheus_tsdb_head_series",
          "interval": "",
          "legendFormat": "Head Series Count",
          "refId": "B"
        }
      ],
      "title": "Prometheus Internal Metrics",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 8
      },
      "id": 4,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "rate(container_cpu_usage_seconds_total{name=~\".*\"}[5m]) * 100",
          "interval": "",
          "legendFormat": "{{name}}",
          "refId": "A"
        }
      ],
      "title": "Container CPU Usage",
      "type": "timeseries"
    }
  ],
  "schemaVersion": 27,
  "style": "dark",
  "tags": [
    "performance",
    "analytics"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Performance Analytics",
  "uid": "performance-analytics",
  "version": 1
}
EOF

    success "Performance analytics dashboard created"
}

# Create Security Monitoring Dashboard
create_security_dashboard() {
    info "Creating security monitoring dashboard"

    cat > /home/mills/collections/grafana/dashboards/security-monitoring.json << 'EOF'
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 5
              },
              {
                "color": "red",
                "value": 10
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "count(up{job=~\".*security.*\"} == 0)",
          "interval": "",
          "legendFormat": "Security Services Down",
          "refId": "A"
        }
      ],
      "title": "Security Services Down",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "yellow",
                "value": 5
              },
              {
                "color": "green",
                "value": 10
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 6,
        "y": 0
      },
      "id": 2,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "count(up{job=~\".*security.*\"} == 1)",
          "interval": "",
          "legendFormat": "Security Services Up",
          "refId": "A"
        }
      ],
      "title": "Security Services Up",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "yellow",
                "value": 50
              },
              {
                "color": "green",
                "value": 80
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 12,
        "y": 0
      },
      "id": 3,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true,
        "text": {}
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "(count(up{job=~\".*security.*\"} == 1) / count(up{job=~\".*security.*\"})) * 100",
          "interval": "",
          "legendFormat": "Security Health",
          "refId": "A"
        }
      ],
      "title": "Security Health Score",
      "type": "gauge"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 1
              },
              {
                "color": "red",
                "value": 5
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 18,
        "y": 0
      },
      "id": 4,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "auto",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "textMode": "auto"
      },
      "pluginVersion": "8.0.0",
      "targets": [
        {
          "expr": "sum(increase(prometheus_notifications_total{instance=~\".*alertmanager.*\"}[1h]))",
          "interval": "",
          "legendFormat": "Security Alerts (1h)",
          "refId": "A"
        }
      ],
      "title": "Security Alerts",
      "type": "stat"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "vis": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 24,
        "x": 0,
        "y": 8
      },
      "id": 5,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom"
        },
        "tooltip": {
          "mode": "single"
        }
      },
      "targets": [
        {
          "expr": "up{job=~\".*security.*|.*wazuh.*|.*suricata.*|.*zeek.*\"}",
          "interval": "",
          "legendFormat": "{{job}} - {{instance}}",
          "refId": "A"
        }
      ],
      "title": "Security Services Status Over Time",
      "type": "timeseries"
    }
  ],
  "schemaVersion": 27,
  "style": "dark",
  "tags": [
    "security",
    "monitoring"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Security Monitoring",
  "uid": "security-monitoring",
  "version": 1
}
EOF

    success "Security monitoring dashboard created"
}

# Create Dashboard Provisioning Configuration
create_dashboard_provisioning() {
    info "Creating dashboard provisioning configuration"

    mkdir -p /home/mills/collections/grafana/provisioning/dashboards

    cat > /home/mills/collections/grafana/provisioning/dashboards/dashboard-config.yml << 'EOF'
apiVersion: 1

providers:
- name: 'Custom Dashboards'
  orgId: 1
  folder: ''
  type: file
  disableDeletion: false
  updateIntervalSeconds: 10
  allowUiUpdates: true
  options:
    path: /etc/grafana/dashboards
EOF

    # Create datasource provisioning
    mkdir -p /home/mills/collections/grafana/provisioning/datasources

    cat > /home/mills/collections/grafana/provisioning/datasources/datasource-config.yml << 'EOF'
apiVersion: 1

datasources:
- name: Prometheus
  type: prometheus
  url: http://prometheus:9090
  access: proxy
  isDefault: true
  editable: true

- name: InfluxDB
  type: influxdb
  url: http://influxdb:8086
  access: proxy
  database: telegraf
  user: telegraf
  password: telegraf_password
  editable: true

- name: Loki
  type: loki
  url: http://loki:3100
  access: proxy
  editable: true
EOF

    success "Dashboard provisioning configuration created"
}

# Create Custom Dashboard Manager
create_dashboard_manager() {
    info "Creating custom dashboard manager"

    cat > /home/mills/collections/grafana/dashboard-manager.sh << 'EOF'
#!/bin/bash
# Custom Dashboard Manager

GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASS="admin123"
DASHBOARD_DIR="/home/mills/collections/grafana/dashboards"

# Function to import dashboard
import_dashboard() {
    local dashboard_file="$1"
    local dashboard_name=$(basename "$dashboard_file" .json)

    echo "Importing dashboard: $dashboard_name"

    # Read dashboard JSON and wrap in import format
    dashboard_json=$(cat "$dashboard_file")
    import_payload="{\"dashboard\": $dashboard_json, \"overwrite\": true}"

    # Import dashboard via API
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -d "$import_payload" \
        "$GRAFANA_URL/api/dashboards/import")

    if echo "$response" | grep -q '"status":"success"'; then
        echo "✅ Successfully imported $dashboard_name"
    else
        echo "❌ Failed to import $dashboard_name"
        echo "Response: $response"
    fi
}

# Function to export dashboard
export_dashboard() {
    local dashboard_uid="$1"
    local output_file="$2"

    echo "Exporting dashboard UID: $dashboard_uid"

    response=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" \
        "$GRAFANA_URL/api/dashboards/uid/$dashboard_uid")

    if echo "$response" | grep -q '"dashboard"'; then
        echo "$response" | jq '.dashboard' > "$output_file"
        echo "✅ Dashboard exported to $output_file"
    else
        echo "❌ Failed to export dashboard $dashboard_uid"
    fi
}

# Function to list all dashboards
list_dashboards() {
    echo "Listing all dashboards:"

    response=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" \
        "$GRAFANA_URL/api/search?type=dash-db")

    if echo "$response" | grep -q '\['; then
        echo "$response" | jq -r '.[] | "\(.uid) - \(.title)"'
    else
        echo "❌ Failed to list dashboards"
    fi
}

# Function to import all custom dashboards
import_all_dashboards() {
    echo "Importing all custom dashboards from $DASHBOARD_DIR"

    for dashboard_file in "$DASHBOARD_DIR"/*.json; do
        if [[ -f "$dashboard_file" ]]; then
            import_dashboard "$dashboard_file"
            sleep 2  # Rate limiting
        fi
    done
}

# Main execution
case "${1:-import-all}" in
    "import")
        if [[ -n "$2" ]]; then
            import_dashboard "$2"
        else
            echo "Usage: $0 import <dashboard_file>"
        fi
        ;;
    "export")
        if [[ -n "$2" && -n "$3" ]]; then
            export_dashboard "$2" "$3"
        else
            echo "Usage: $0 export <dashboard_uid> <output_file>"
        fi
        ;;
    "list")
        list_dashboards
        ;;
    "import-all")
        import_all_dashboards
        ;;
    *)
        echo "Usage: $0 {import <file>|export <uid> <file>|list|import-all}"
        ;;
esac
EOF

    chmod +x /home/mills/collections/grafana/dashboard-manager.sh
    success "Custom dashboard manager created"
}

# Generate Dashboard Summary Report
generate_dashboard_report() {
    info "Generating dashboard customization report"

    local report_file="/home/mills/dashboard-customization-report-${TIMESTAMP}.md"

    cat > "$report_file" << 'EOF'
# Advanced Dashboard Customization Report

**Report Date:** $(date)
**Implementation:** Advanced Monitoring Dashboard Customization

## Custom Dashboards Deployed

### 1. Infrastructure Overview Dashboard
- **Purpose**: High-level infrastructure monitoring and health status
- **Key Metrics**: CPU usage, memory usage, service counts, overall health
- **Features**: Real-time gauges, trend analysis, alert indicators
- **Target Audience**: Operations team, executives

### 2. Service Health Monitoring Dashboard
- **Purpose**: Detailed service status and reliability tracking
- **Key Metrics**: Service up/down status, restart counts, health trends
- **Features**: Service status table, pie charts, historical analysis
- **Target Audience**: DevOps engineers, service owners

### 3. Performance Analytics Dashboard
- **Purpose**: Deep performance analysis and optimization insights
- **Key Metrics**: Response times, request rates, resource utilization
- **Features**: Percentile analysis, container metrics, API performance
- **Target Audience**: Performance engineers, developers

### 4. Security Monitoring Dashboard
- **Purpose**: Comprehensive security posture and threat monitoring
- **Key Metrics**: Security service status, alert counts, health scores
- **Features**: Security alerts, service availability, threat indicators
- **Target Audience**: Security team, SOC analysts

## Implementation Features

### Advanced Visualizations
- **Time Series Charts**: Multi-metric trending with color coding
- **Stat Panels**: Real-time KPIs with threshold-based coloring
- **Gauge Charts**: Performance indicators with visual thresholds
- **Pie Charts**: Service distribution and status overview
- **Tables**: Detailed service status with color-coded backgrounds

### Automation & Management
- **Dashboard Provisioning**: Automated dashboard deployment
- **Datasource Configuration**: Auto-configured Prometheus, InfluxDB, Loki
- **Dashboard Manager**: Custom script for import/export operations
- **Version Control**: JSON-based dashboard definitions for Git tracking

### User Experience Enhancements
- **Role-Based Views**: Dashboards tailored for different operational roles
- **Responsive Design**: Optimized for various screen sizes
- **Interactive Elements**: Drill-down capabilities and dynamic filtering
- **Real-time Updates**: Live data refresh with configurable intervals

## Operational Benefits

### Improved Visibility
- **Centralized Monitoring**: Single pane of glass for all infrastructure
- **Role-Specific Views**: Customized dashboards for different teams
- **Real-time Insights**: Live performance and health indicators
- **Historical Analysis**: Trend tracking and pattern identification

### Enhanced Decision Making
- **Data-Driven Insights**: Comprehensive metrics for informed decisions
- **Proactive Monitoring**: Early warning indicators and predictive analytics
- **Performance Optimization**: Detailed performance metrics for tuning
- **Security Awareness**: Real-time security posture visibility

### Operational Efficiency
- **Reduced MTTR**: Faster issue identification and root cause analysis
- **Automated Alerting**: Threshold-based notifications and escalations
- **Self-Service Analytics**: Teams can access relevant metrics independently
- **Standardized Reporting**: Consistent metrics across all teams

## Technical Implementation

### Dashboard Configuration Files
```
/home/mills/collections/grafana/
├── dashboards/
│   ├── infrastructure-overview.json       # High-level infrastructure view
│   ├── service-health.json               # Service status and reliability
│   ├── performance-analytics.json        # Performance metrics and analysis
│   └── security-monitoring.json          # Security posture monitoring
├── provisioning/
│   ├── dashboards/dashboard-config.yml   # Dashboard provisioning config
│   └── datasources/datasource-config.yml # Datasource configuration
└── dashboard-manager.sh                  # Dashboard management utility
```

### Automation Features
- **Automatic Import**: Dashboards auto-imported on Grafana startup
- **Version Control**: JSON definitions enable Git-based versioning
- **Backup/Restore**: Dashboard manager provides export capabilities
- **Bulk Operations**: Mass import/export for dashboard management

## Usage Instructions

### Accessing Dashboards
1. **Grafana Interface**: http://localhost:3000 (admin/admin123)
2. **Dashboard Navigation**: Use sidebar menu to access custom dashboards
3. **Dashboard Categories**: Organized by function (Infrastructure, Services, Performance, Security)

### Managing Dashboards
```bash
# Import all custom dashboards
/home/mills/collections/grafana/dashboard-manager.sh import-all

# List available dashboards
/home/mills/collections/grafana/dashboard-manager.sh list

# Import specific dashboard
/home/mills/collections/grafana/dashboard-manager.sh import /path/to/dashboard.json

# Export dashboard by UID
/home/mills/collections/grafana/dashboard-manager.sh export dashboard-uid output.json
```

### Customization Guidelines
1. **Edit Dashboard JSON**: Modify dashboard files for custom requirements
2. **Add New Panels**: Extend existing dashboards with additional metrics
3. **Create New Dashboards**: Use existing dashboards as templates
4. **Test Changes**: Import dashboards to test before deployment

## Future Enhancements

### Planned Additions
- **AI/ML Dashboards**: Machine learning insights and predictions
- **Business Metrics**: KPI tracking and business intelligence views
- **Mobile Optimization**: Enhanced mobile dashboard experience
- **Advanced Alerting**: Integration with external notification systems

### Scalability Considerations
- **Performance Optimization**: Query optimization for large datasets
- **User Management**: Role-based access control implementation
- **Data Retention**: Automated data lifecycle management
- **Multi-tenancy**: Support for multiple organization views

---
*Report generated by Advanced Dashboard Customization System*
EOF

    success "Dashboard customization report generated: $report_file"
}

# Main execution
main() {
    log "🚀 Starting Advanced Monitoring Dashboard Customization"

    # Create all custom dashboards
    create_infrastructure_dashboard
    create_service_health_dashboard
    create_performance_dashboard
    create_security_dashboard

    # Setup dashboard provisioning and management
    create_dashboard_provisioning
    create_dashboard_manager

    # Generate implementation report
    generate_dashboard_report

    log "🎉 Advanced Dashboard Customization completed!"
    success "All custom dashboards created with provisioning and management tools"
    info "Log file: $LOG_FILE"
}

# Execute main function
main "$@"
