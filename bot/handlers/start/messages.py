from asgiref.sync import sync_to_async
from django_app.shop.models import TelegramUser, Order, Product, Category

ITEMS_PER_PAGE = 10

@sync_to_async
def get_user_info(user: TelegramUser) -> str:
    return (
        f"👤 Имя: {user.first_name or 'Не указано'}\n"
        f"Фамилия: {user.last_name or 'Не указана'}\n"
        f"Username: @{user.username if user.username else 'Не указан'}\n"
        f"Язык: {user.language_code or 'Не указан'}\n"
        f"ID: {user.telegram_id}"
    )

@sync_to_async
def get_user_orders(user: TelegramUser, limit: int = 5) -> list[Order]:
    return list(Order.objects.filter(user=user, is_active=True).order_by('-created_at')[:limit])

@sync_to_async
def get_pending_orders(user: TelegramUser) -> list[Order]:
    return list(Order.objects.filter(
        user=user,
        is_active=True,
        status__in=['Ожидает оплаты', 'Оплачен', 'В доставке']
    ).order_by('-created_at'))

@sync_to_async
def get_price_list(page: int) -> tuple[str, int]:
    products = Product.objects.filter(is_active=True).order_by('category__name', 'name')
    total_products = products.count()
    total_pages = (total_products + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    products_on_page = products[start:end]

    text = "📋 Прайс-лист\n\n"
    current_category = None
    for product in products_on_page:
        if product.category != current_category:
            current_category = product.category
            text += f"**{current_category.name}**\n"
        text += f"• {product.name} — {product.price} ₽\n"
    if not products_on_page:
        text += "Товаров пока нет.\n"
    return text, total_pages

async def format_user_profile(user: TelegramUser) -> str:
    """Формирование текста профиля"""
    user_info = await get_user_info(user)
    orders = await get_user_orders(user)
    pending_orders = await get_pending_orders(user)

    text = f"👤 Профиль\n\n{user_info}\n\n"
    if pending_orders:
        text += "📬 Текущие заказы (не доставлены):\n\n"
        for order in pending_orders:
            text += (
                f"Заказ #{order.id} от {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Сумма: {order.total} ₽\n"
                f"Статус: {order.get_status_display()}\n"
                f"Адрес: {order.address}\n\n"
            )
    else:
        text += "📬 Нет текущих заказов.\n\n"

    if not orders:
        text += "📦 Заказов пока нет. Загляни в каталог!"
    else:
        text += "📦 Последние заказы:\n\n"
        for order in orders:
            text += (
                f"Заказ #{order.id} от {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                f"Сумма: {order.total} ₽\n"
                f"Статус: {order.get_status_display()}\n"
                f"Адрес: {order.address}\n\n"
            )
    return text

def welcome_message(user_name: str, has_cart: bool = False) -> str:
    """Приветственное сообщение"""
    return (
        f"👋 Добро пожаловать, {user_name}!\n\n"
        "Мы рады видеть вас в нашем магазине! 🛍️\n"
        "Выберите действие в меню ниже:\n\n"
        "🔹 Каталог\n"
        "🔹 Прайс-лист\n"
        "🔹 Профиль\n"
        "🔹 FAQ\n"
        "🔹 Корзина\n"
    )
