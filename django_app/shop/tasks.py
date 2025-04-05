import logging
import openpyxl
from django.core.files.storage import default_storage
from .models import Order, OrderItem

# Настройка логирования для данного модуля
logger = logging.getLogger(__name__)

def export_orders_to_excel(queryset=None):
    """
    Экспорт заказов в Excel-файл.

    Args:
        queryset: QuerySet заказов для экспорта. Если None, экспортируются все активные заказы.

    Создаёт Excel-файл с информацией о заказах, включая ID заказа, пользователя,
    адрес доставки, телефон, пожелания, желаемое время доставки, статус и список товаров.

    Возвращает путь к сохранённому Excel-файлу.
    """
    logger.info('Начало экспорта заказов в Excel.')

    try:
        # Создание новой рабочей книги и настройка листа
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Заказы"
        logger.debug('Создана новая рабочая книга Excel.')

        # Установка заголовков столбцов
        headers = [
            "ID заказа",
            "Пользователь",
            "Адрес доставки",
            "Телефон",
            "Пожелания",
            "Желаемое время доставки",
            "Статус",
            "Товары"
        ]
        sheet.append(headers)
        logger.debug('Установлены заголовки столбцов в Excel.')

        # Инициализация номера строки для заполнения данных
        row_number = 2

        # Получение заказов для экспорта
        if queryset is None:
            orders = Order.objects.filter(is_active=True)
        else:
            orders = queryset
        logger.info(f'Получено {orders.count()} заказов для экспорта.')

        for order in orders:
            # Получение товаров, связанных с заказом
            order_items = OrderItem.objects.filter(order=order, is_active=True)
            logger.debug(f'Получено {order_items.count()} товаров для заказа №{order.id}.')

            items_list = [f"{item.product.name} x {item.quantity}" for item in order_items]

            # Заполнение строки данными заказа
            sheet.cell(row=row_number, column=1, value=order.id)
            sheet.cell(row=row_number, column=2, value=order.user.username or f"User {order.user.telegram_id}")
            sheet.cell(row=row_number, column=3, value=order.address)
            sheet.cell(row=row_number, column=4, value=order.phone or "-")  # Добавили or "-"
            sheet.cell(row=row_number, column=5, value=order.wishes or "-")
            sheet.cell(row=row_number, column=6, value=order.desired_delivery_time or "-")
            sheet.cell(row=row_number, column=7, value=order.get_status_display())
            sheet.cell(row=row_number, column=8, value=", ".join(items_list) if items_list else "Нет товаров")

            logger.debug(f'Заполнена строка для заказа №{order.id}.')
            row_number += 1

        # Определение имени файла и сохранение рабочей книги
        excel_filename = "orders_export.xlsx"
        workbook_path = default_storage.path(excel_filename)
        workbook.save(workbook_path)
        logger.info(f'Экспорт заказов завершён. Файл сохранён по пути: {workbook_path}')

        return workbook_path

    except Exception as e:
        logger.error(f"Ошибка при экспорте заказов в Excel: {e}", exc_info=True)
        return None
