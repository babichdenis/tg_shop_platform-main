#!/bin/sh

# Установка PYTHONPATH на корень проекта
export PYTHONPATH="/app"

# Ожидание готовности базы данных с помощью wait-for-it
echo "Ожидание готовности базы данных..."
/usr/local/bin/wait-for-it.sh db:${POSTGRES_PORT} --timeout=30 -- echo "База данных готова"

# Создание миграций для приложения shop
echo "Создание миграций для приложения shop..."
python django_app/manage.py makemigrations shop

# Применение миграций базы данных
echo "Применение миграций..."
python django_app/manage.py migrate

# Загрузка тестовых данных
# echo "Выполнение скрипта load_data.py..."
# python django_app/load_data.py

# Запуск сервера Django
python django_app/manage.py runserver 0.0.0.0:8000
