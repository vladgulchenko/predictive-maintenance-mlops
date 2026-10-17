"""Переобучение модели предиктивного обслуживания.

validate  отдельный под: dvc pull из S3, app.validate, результаты проверки в MLflow
train     отдельный под из того же образа: dvc pull из S3, app.train, модель в MLflow
promoted  дальше идём, только если гейт в train.py отдал новой версии алиас champion
rollout   перезапуск predictive-maintenance-api: новые поды загрузят champion из реестра

Образ берётся из переменной pred_main_image, её выставляет CI при каждом деплое.
"""
from datetime import UTC, datetime

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.sdk import CronTriggerTimetable, Param, dag, task
from kubernetes.client import models as k8s


@dag(
    # Каждый день в 03:00 по Минску; пропущенные запуски не догоняем.
    schedule=CronTriggerTimetable("0 3 * * *", timezone="Europe/Minsk"),
    catchup=False,
    max_active_runs=1,
    params={"n_estimators": Param(300, type="integer", minimum=1, description="Количество деревьев RandomForest"),
            "max_depth": Param(None, type=["null", "integer"], minimum=1, description="Глубина деревьев RandomForest"),
            "min_samples_leaf": Param(2, type="integer",  minimum=1, description="Количество элементов в листе дерева RandomForest")},
    tags=["predictive-maintenance", "retraining"],
)
def pred_main_retrain():
    validate = KubernetesPodOperator(
        task_id="validate",
        name="pred-main-validate",
        namespace="mlops",
        in_cluster=True,
        image="{{ var.value.pred_main_image }}",
        image_pull_policy="IfNotPresent",
        cmds=[
            "sh", "-c",
            (
                "uv run --no-sync dvc pull -r cluster data/raw/ai4i2020.csv.dvc"
                " && uv run --no-sync python -m app.validate"
            ),
        ],
        env_vars={"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000"},
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
        # Следующая задача зависит от exit code, результат XCom не нужен.
        do_xcom_push=False,
        get_logs=True,
        on_finish_action="delete_pod",
    )

    train = KubernetesPodOperator(
        task_id="train",
        name="pred-main-train",
        namespace="mlops",
        in_cluster=True,
        # сеттится в ci
        image="{{ var.value.pred_main_image }}",
        image_pull_policy="IfNotPresent",
        # данных в образе нет: DVC берёт их из S3 по адресу изнутри кластера (remote cluster)
        cmds=[
            "sh", "-c",
            (
                "uv run --no-sync dvc pull -r cluster data/raw/ai4i2020.csv.dvc"
                " && uv run --no-sync python -m app.train"
            ),
        ],
        env_vars={"MLFLOW_TRACKING_URI": "http://mlflow.mlops:5000", "N_ESTIMATORS": "{{ params.n_estimators }}", "MAX_DEPTH": "{{ params.max_depth }}", "MIN_SAMPLES_LEAF": "{{ params.min_samples_leaf }}"},
        env_from=[k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name="s3-credentials"))],
        do_xcom_push=True,
        get_logs=True,
        on_finish_action="delete_pod",
    )

    @task.short_circuit
    def promoted(result: dict) -> bool:
        print(f"версия {result['version']}, pr_auc {result['pr_auc']}, champion до этого {result['champion_before']}")
        return result["promoted"]

    @task
    def rollout():
        from kubernetes import client, config

        config.load_incluster_config()
        now = datetime.now(UTC).isoformat()
        client.AppsV1Api().patch_namespaced_deployment(
            "predictive-maintenance-api", "default",
            {"spec": {"template": {"metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": now}}}}},
        )
        print("predictive-maintenance-api перезапущен", now)

    validate >> train
    promoted(train.output) >> rollout()


pred_main_retrain()
