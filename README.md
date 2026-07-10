# Perevozki

Одностраничный шаблон маршрутной SEO-страницы для Perewozki.by.

## Что реализовано

- демонстрационная страница «Перевозка грузов Минск — Узда»;
- адаптивный дизайн для desktop, tablet и mobile;
- реальные фотографии автопарка и выполненных работ клиента;
- цены, частные и корпоративные сценарии, этапы заказа, автопарк, преимущества, FAQ, галерея, заявка и города;
- рабочие ссылки телефона и мессенджеров;
- локальная демонстрация формы без передачи данных.

Генерация страниц из Excel и массовая публикация пока не подключены.

## Локальный просмотр

Из корня проекта:

```powershell
C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m http.server 4173 --bind 127.0.0.1
```

Открыть `http://127.0.0.1:4173/`.

## Проверка

```powershell
C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_template -v
C:\Users\user\.codex\scripts\harness.cmd smoke
```

## Фотографии

В `assets/photos/` находятся выбранные исходные фотографии клиента без генеративной замены и цветной тонировки. Визуальные концепты хранятся отдельно в `design/` и не используются как растровая подмена интерфейса.

## Публикация

Тестовая страница: [https://perewozki.by/seo-preview-2026/](https://perewozki.by/seo-preview-2026/).

В MODX создан отдельный скрытый ресурс и отдельный шаблон. Шаблон подключает существующие чанки `head`, `header`, `index-menu`, `s-services`, `s-question`, `s-about`, `s-adv` и `footer`; заново свёрстан только маршрутный контент. Стили и фотографии изолированы в `/assets/seo-preview-2026/`, главная страница не изменена.

Для повторной публикации нужны переменные окружения `FTP_HOST`, `FTP_USERNAME`, `FTP_PASSWORD`, `MODX_USERNAME`, `MODX_PASSWORD`, после чего запускается:

```powershell
python scripts\deploy_modx_preview.py
```
