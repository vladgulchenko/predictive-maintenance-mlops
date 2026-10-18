#!/usr/bin/env bash
# Поднимаем платформу. Данные, первый champion, runner и deploy API — по README.
set -euo pipefail
cd "$(dirname "$0")/.."

# Файлы доверенные: обычные Bash-присваивания, без собственного парсера.
source .env.example
if [[ -f .env ]]; then source .env; fi

for cmd in docker kind kubectl helm curl; do
  command -v "$cmd" >/dev/null || { echo "Не найден $cmd: установи и добавь в PATH" >&2; exit 1; }
done
docker info >/dev/null
[[ "$S3_BUCKET" == pred-main-dvc ]] || { echo 'Имя бакета должно совпадать с .dvc/config: pred-main-dvc' >&2; exit 1; }

echo "== кластер $CLUSTER"
clusters=$(kind get clusters)
if ! grep -Fxq "$CLUSTER" <<< "$clusters"; then
  kind create cluster --name "$CLUSTER" --config platform/kind-config.yaml --wait 5m
fi
kind export kubeconfig --name "$CLUSTER"
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo '== перенос заранее скачанных образов'
# Архив одной платформы обходит ошибку content digest ... not found в Docker Desktop.
ARCH=$(docker version --format '{{.Server.Arch}}')
ARCHIVE=$(mktemp)
trap 'rm -f -- "$ARCHIVE"' EXIT
for img in apache/airflow:3.3.2 ghcr.io/mlflow/mlflow:v3.16.1 rustfs/rustfs:1.0.0; do
  if docker image inspect "$img" >/dev/null 2>&1; then
    if ! { docker save --platform "linux/$ARCH" "$img" -o "$ARCHIVE" &&
           kind load image-archive "$ARCHIVE" --name "$CLUSTER"; }; then
      echo "Не удалось перенести $img; kubelet попробует скачать его из registry" >&2
    fi
  fi
done

echo '== MLflow, RustFS, Airflow'
kubectl apply -f platform/mlflow.yaml
kubectl -n mlops create secret generic s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
  --from-literal=AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f platform/s3.yaml -f platform/airflow.yaml

echo '== Traefik, Prometheus/Grafana и metrics-server'
helm repo add traefik https://traefik.github.io/charts --force-update
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ --force-update
helm repo update
helm upgrade --install traefik traefik/traefik --version 41.6.0 \
  -n traefik --create-namespace -f platform/traefik-values.yaml --wait --timeout 15m
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 91.5.2 \
  -n monitoring --create-namespace -f platform/monitoring-values.yaml --wait --timeout 15m
helm upgrade --install metrics-server metrics-server/metrics-server --version 3.13.0 \
  -n kube-system -f platform/metrics-server-values.yaml --wait --timeout 5m
kubectl apply -f platform/ingress.yaml

echo '== ждем готовности'
for deploy in mlflow rustfs airflow; do
  kubectl -n mlops rollout status "deploy/$deploy" --timeout=15m
done
kubectl -n monitoring rollout status deploy/monitoring-grafana --timeout=15m

echo "== бакет $S3_BUCKET через Ingress"
ready=false
for ((i=1; i<=30; i++)); do
  code=$(curl -sS --connect-timeout 5 --max-time 20 -o /dev/null -w '%{http_code}' \
    --aws-sigv4 'aws:amz:us-east-1:s3' --user "$S3_ACCESS_KEY:$S3_SECRET_KEY" \
    -X PUT "$S3_ENDPOINT_EXTERNAL/$S3_BUCKET") || code=000
  if [[ "$code" == 200 || "$code" == 409 ]]; then
    head=$(curl -sS --head --connect-timeout 5 --max-time 20 -o /dev/null -w '%{http_code}' \
      --aws-sigv4 'aws:amz:us-east-1:s3' --user "$S3_ACCESS_KEY:$S3_SECRET_KEY" \
      "$S3_ENDPOINT_EXTERNAL/$S3_BUCKET") || head=000
    if [[ "$head" == 200 ]]; then ready=true; break; fi
  fi
  sleep 2
done
[[ "$ready" == true ]] || { echo 'Бакет недоступен: проверь credentials, DNS s3.localhost и Traefik' >&2; exit 1; }

echo 'Платформа готова:'
echo '  http://mlflow.localhost  http://airflow.localhost'
echo '  http://grafana.localhost (admin/admin)'
echo '  http://s3-console.localhost/rustfs/console/index.html'
echo 'Далее по README: данные, первый champion, свой runner и deploy API.'
