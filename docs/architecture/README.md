# Архитектура

| Схема | SVG | Редактируемый исходник |
| --- | --- | --- |
| Общая архитектура платформы | [architecture.svg](architecture.svg) | [architecture.excalidraw](architecture.excalidraw) |
| Жизненный цикл модели и три исхода DAG | [model-lifecycle.svg](model-lifecycle.svg) | [model-lifecycle.excalidraw](model-lifecycle.excalidraw) |
| Доставка кода: CI, GHCR, deploy и smoke-проверки | [code-delivery.svg](code-delivery.svg) | [code-delivery.excalidraw](code-delivery.excalidraw) |
| Хранение данных и состояния | [state-storage.svg](state-storage.svg) | [state-storage.excalidraw](state-storage.excalidraw) |

[Таблица хранилищ, путей и восстановления](storage-map.md) дополняет карту хранения ссылками на исходные манифесты и код.

SVG встроены в корневой README. Исходники открываются импортом файла на https://excalidraw.com/.

После редактирования исходника экспортируй SVG заново, чтобы оба файла оставались согласованы. Экспериментальные варианты и генератор в этот каталог не включаются.

Иконки технологий хранятся отдельно в `docs/assets/icons/`.
