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

### Evidence placeholders

Add screenshots here after the green run:

```text
reports/hw4/grafana-dashboard.png
reports/hw4/prometheus-targets.png
reports/hw4/actions-monitoring-green.png
reports/hw4/metrics-endpoint.png
```
