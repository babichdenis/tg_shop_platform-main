# bot/handlers/cart/models.py
import os
import django
from asgiref.sync import sync_to_async

# Инициализация Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.config.settings")
django.setup()

def _get_or_create_user_sync(tg_id: int):
    from django_app.shop.models import TelegramUser
    user, created = TelegramUser.objects.get_or_create(
        telegram_id=tg_id,
        defaults={'is_active': True}
    )
    return user, created

def _get_cart_sync(user):
    from django_app.shop.models import Cart
    cart, _ = Cart.objects.get_or_create(user=user, is_active=True)
    return cart

def _get_cart_items_sync(user):
    from django_app.shop.models import CartItem
    return list(CartItem.objects.filter(
        cart__user=user,
        cart__is_active=True,
        is_active=True
    ).select_related("product").select_related("cart"))

def _update_cart_item_quantity_sync(user, product_id, delta):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(user=user, is_active=True)
    item = CartItem.objects.filter(cart=cart, product_id=product_id, is_active=True).first()
    if item:
        new_quantity = item.quantity + delta
        if new_quantity <= 0:
            item.is_active = False
            item.save()
        else:
            item.quantity = new_quantity
            item.save()
        if not CartItem.objects.filter(cart=cart, is_active=True).exists():
            cart.is_active = False
            cart.save()

def _remove_item_from_cart_sync(user, product_id):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(user=user, is_active=True)
    items = CartItem.objects.filter(cart=cart, product_id=product_id, is_active=True)
    for item in items:
        item.is_active = False
        item.save()
    if not CartItem.objects.filter(cart=cart, is_active=True).exists():
        cart.is_active = False
        cart.save()

def _clear_cart_sync(user):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(user=user, is_active=True)
    CartItem.objects.filter(cart=cart, is_active=True).update(is_active=False)
    cart.is_active = False
    cart.save()

def _create_order_sync(user_id, address, phone, wishes=None, desired_delivery_time=None):
    from django_app.shop.models import Cart, Order, OrderItem, TelegramUser
    user = TelegramUser.objects.get(telegram_id=user_id)
    cart = Cart.objects.get(user=user, is_active=True)
    
    total = sum(item.product.price * item.quantity for item in cart.items.filter(is_active=True))
    
    order = Order.objects.create(
        user=user,
        address=address,
        phone=phone,
        wishes=wishes,
        desired_delivery_time=desired_delivery_time,
        total=total
    )
    
    for cart_item in cart.items.filter(is_active=True):
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            quantity=cart_item.quantity
        )
    
    cart.is_active = False
    cart.save()
    
    return order

def _get_cart_quantity_sync(user):
    from django_app.shop.models import Cart
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if cart:
        return sum(item.quantity for item in cart.items.filter(is_active=True))
    return 0

def _get_cart_total_sync(user):
    from django_app.shop.models import Cart
    cart = Cart.objects.filter(user=user, is_active=True).first()
    if cart:
        return sum(item.product.price * item.quantity for item in cart.items.filter(is_active=True))
    return 0

def _get_cart_details_sync(cart_id):
    from django_app.shop.models import Cart, CartItem
    cart = Cart.objects.get(id=cart_id)
    items = CartItem.objects.filter(cart=cart, is_active=True).select_related('product')
    items_text = "\n".join(
        f"{item.product.name}, {item.quantity} шт., {item.quantity * item.product.price}₽"
        for item in items
    )
    total = sum(item.product.price * item.quantity for item in items)
    first_item_photo = items[0].product.photo.url if items and items[0].product.photo else None
    return items_text, total, first_item_photo

def _get_order_details_sync(order_id):
    from django_app.shop.models import OrderItem
    items = OrderItem.objects.filter(order_id=order_id).select_related('product')
    items_text = "\n".join(
        f"{item.product.name}, {item.quantity} шт., {item.quantity * item.product.price}₽"
        for item in items
    )
    total = sum(item.product.price * item.quantity for item in items)
    return items_text, total

# Асинхронные обертки
@sync_to_async
def get_or_create_user(tg_id: int):
    return _get_or_create_user_sync(tg_id)

@sync_to_async
def get_cart(user):
    return _get_cart_sync(user)

@sync_to_async
def get_cart_items(user):
    return _get_cart_items_sync(user)

@sync_to_async
def update_cart_item_quantity(user, product_id, delta):
    return _update_cart_item_quantity_sync(user, product_id, delta)

@sync_to_async
def remove_item_from_cart(user, product_id):
    return _remove_item_from_cart_sync(user, product_id)

@sync_to_async
def clear_cart(user):
    return _clear_cart_sync(user)

@sync_to_async
def create_order(user_id, address, phone, wishes=None, desired_delivery_time=None):
    return _create_order_sync(user_id, address, phone, wishes, desired_delivery_time)

@sync_to_async
def get_cart_quantity(user):
    return _get_cart_quantity_sync(user)

@sync_to_async
def get_cart_total(user):
    return _get_cart_total_sync(user)

@sync_to_async
def get_cart_details(cart_id):
    return _get_cart_details_sync(cart_id)

@sync_to_async
def get_order_details(order_id):
    return _get_order_details_sync(order_id)
