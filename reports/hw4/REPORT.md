# Homework 4 report

## Monitoring block

This branch adds Prometheus/Grafana monitoring for the predictive maintenance API.

### Application metrics

The FastAPI service exposes `/metrics` through `prometheus-fastapi-instrumentator`.

Standard HTTP metrics are collected automatically:

- request count by handler/status;
- request latency histogram;
- `/metrics` endpoint for Prometheus scraping.

Custom domain metrics are exported from `src/app/service/app.py`:

- `predictive_maintenance_model_info` - loaded model version per pod;
- `predictive_maintenance_predictions_total` - prediction count by `machine_failure` label;
- `predictive_maintenance_score` - prediction score histogram.

### Kubernetes manifests

Monitoring-related files:

```text
platform/monitoring-values.yaml
k8s/monitoring/servicemonitor.yaml
k8s/monitoring/dashboard.yaml
platform/ingress.yaml
k8s/service.yaml
```

`k8s/service.yaml` exposes a named `http` port. `ServiceMonitor` uses this port name to scrape `/metrics` from the API service.

`platform/monitoring-values.yaml` configures `kube-prometheus-stack` for local kind:

- disables unnecessary control-plane targets for local kind;
- enables Grafana dashboard sidecar;
- allows Prometheus to pick up `ServiceMonitor` resources without Helm release labels.

`k8s/monitoring/dashboard.yaml` defines the Grafana dashboard as a ConfigMap with label `grafana_dashboard: "1"`.

### Manual deployment commands

Install or update Prometheus/Grafana:

```powershell
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install monitoring prometheus-community/kube-prometheus-stack `
  -n monitoring `
  -f platform/monitoring-values.yaml
```

Apply monitoring manifests and ingress:

```powershell
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/monitoring/servicemonitor.yaml
kubectl apply -f k8s/monitoring/dashboard.yaml
kubectl apply -f platform/ingress.yaml
```

Check the setup:

```powershell
kubectl get pods -n monitoring
kubectl get servicemonitor -A
kubectl get cm predictive-maintenance-dashboard -n monitoring --show-labels
curl http://pred-main.localhost/metrics
```

Grafana is available at:

```text
http://grafana.localhost
```

Credentials:

```text
admin / admin
```

### CI/CD deployment logic

The deploy job still runs only for manual `workflow_dispatch` on `main` and uses the self-hosted kind runner.

The monitoring step runs after the API service rollout:

1. Ensures Helm is available on the self-hosted runner.
2. Adds and updates the `prometheus-community` Helm repo.
3. Creates the `monitoring` namespace if it does not exist.
4. Installs or upgrades `kube-prometheus-stack` with `platform/monitoring-values.yaml`.
5. Applies `k8s/monitoring/` resources.
6. Re-applies `platform/ingress.yaml`, including `grafana.localhost`.
7. Waits for `monitoring-grafana` rollout.

The smoke step then checks:

- API `/health`;
- API `/ready`;
- prediction response;
- `/metrics` contains predictive maintenance metrics;
- `ServiceMonitor` exists;
- Grafana dashboard ConfigMap exists;
- Grafana answers through ingress on `/api/health`.

## S3 and DVC block

RustFS is used as an S3-compatible object storage for DVC data.

### Storage manifests

RustFS resources are defined in:

```text
platform/s3.yaml
```

The manifest creates:

- `rustfs-data` PVC in namespace `mlops`;
- `rustfs` Deployment;
- `rustfs` Service with two named ports:
  - `9000` for S3 API;
  - `9001` for console UI.

External access is routed through `platform/ingress.yaml`:

```text
http://s3.localhost
http://s3-console.localhost
```

Inside Kubernetes, workloads use:

```text
http://rustfs.mlops:9000
```

### Credentials

Local secrets are described in `.env.example` and are not committed through `.env`.

The Kubernetes secret is created from local values:

```powershell
kubectl create secret generic s3-credentials `
  -n mlops `
  --from-literal=AWS_ACCESS_KEY_ID=$env:S3_ACCESS_KEY `
  --from-literal=AWS_SECRET_ACCESS_KEY=$env:S3_SECRET_KEY `
  --dry-run=client -o yaml | kubectl apply -f -
```

### DVC remotes

DVC uses one bucket with two endpoints:

```ini
[core]
    remote = laptop

['remote "laptop"']
    url = s3://pred-main-dvc
    endpointurl = http://s3.localhost

['remote "cluster"']
    url = s3://pred-main-dvc
    endpointurl = http://rustfs.mlops:9000
```

`laptop` is used from the local machine. `cluster` is prepared for future Airflow/Kubernetes jobs.

Credentials are stored locally in `.dvc/config.local`, which is ignored by git.

The data push was checked with:

```powershell
uv run dvc push data/raw/ai4i2020.csv.dvc -r laptop -v
```

Result:

```text
1 file pushed
```

### Evidence placeholders

Add screenshots here after the green run:

```text
reports/hw4/grafana-dashboard.png
reports/hw4/prometheus-targets.png
reports/hw4/actions-monitoring-green.png
reports/hw4/metrics-endpoint.png
reports/hw4/rustfs-bucket.png
reports/hw4/dvc-push-s3.png
```
