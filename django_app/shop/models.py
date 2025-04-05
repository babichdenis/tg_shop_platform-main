import logging
from django.conf import settings
from django.db import models
from yookassa import Payment, Configuration
from mptt.models import MPTTModel, TreeForeignKey


logger = logging.getLogger(__name__)

class TelegramUser(models.Model):
    telegram_id = models.BigIntegerField(unique=True, verbose_name="ID в Telegram")
    first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name="Фамилия")
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name="Юзернейм")
    language_code = models.CharField(max_length=10, blank=True, null=True, verbose_name="Язык")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата регистрации")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Последняя активность")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"{self.first_name} (@{self.username})" if self.username else f"User {self.telegram_id}"

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Пользователь Telegram"
        verbose_name_plural = "Пользователи Telegram"

class Category(MPTTModel):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название")
    parent = TreeForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
        verbose_name="Родительская категория"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    class MPTTMeta:
        order_insertion_by = ['name']

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

class Product(models.Model):
    category = TreeForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Категория"
    )
    name = models.CharField(max_length=255, verbose_name="Название товара")
    description = models.TextField(verbose_name="Описание товара", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    photo = models.ImageField(
        upload_to='product_photos/',
        blank=True,
        null=True,
        default='product_photos/placeholder.png',
        verbose_name="Фото товара"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"{self.name} ({self.category.name})"

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

class FAQ(models.Model):
    question = models.CharField(max_length=255, verbose_name="Вопрос")
    answer = models.TextField(verbose_name="Ответ")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return self.question

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Часто задаваемый вопрос"
        verbose_name_plural = "Часто задаваемые вопросы"

class Cart(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='carts', verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    is_active = models.BooleanField(default=True, verbose_name="Активна")

    def __str__(self):
        return f"Корзина пользователя {self.user.username or self.user.telegram_id}"

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Корзина")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"

class Order(models.Model):
    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='orders', verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    address = models.CharField(max_length=255, verbose_name="Адрес доставки")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Итого")
    is_paid = models.BooleanField(default=False, verbose_name="Подтвержден")
    payment_id = models.CharField(max_length=100, blank=True, null=True, verbose_name="ID платежа")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"Заказ №{self.id} от {self.user.username or self.user.telegram_id}"

    def create_payment(self):
        try:
            payment = Payment.create({
                "amount": {
                    "value": f"{float(self.total):.2f}",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": settings.YOOKASSA_RETURN_URL or "https://example.com/payment-callback/"
                },
                "capture": True,
                "description": f"Заказ №{self.id}",
                "metadata": {
                    "order_id": self.id,
                    "user_id": self.user.id
                }
            })
            self.payment_id = payment.id
            self.save()
            logger.info(f'Платеж создан для заказа №{self.id} с payment_id={payment.id}')
            return payment
        except Exception as e:
            logger.error(f"Ошибка при создании платежа для заказа №{self.id}: {e}", exc_info=True)
            self.payment_id = None
            self.save()
            return None

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"

    def soft_delete(self):
        self.is_active = False
        self.save()

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"
