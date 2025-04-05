import logging
from django.db import models
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
        default=None,
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
    # Статусы заказа
    STATUS_ACCEPTED = 'accepted'
    STATUS_ASSEMBLING = 'assembling'
    STATUS_ON_WAY = 'on_way'
    STATUS_DELIVERED = 'delivered'

    STATUS_CHOICES = [
        (STATUS_ACCEPTED, 'Принят'),
        (STATUS_ASSEMBLING, 'В сборке'),
        (STATUS_ON_WAY, 'В пути'),
        (STATUS_DELIVERED, 'Доставлен'),
    ]

    user = models.ForeignKey(TelegramUser, on_delete=models.CASCADE, related_name='orders', verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    address = models.CharField(max_length=255, verbose_name="Адрес доставки")
    phone = models.CharField(max_length=20, default="", verbose_name="Телефон")
    wishes = models.TextField(blank=True, null=True, verbose_name="Пожелания к заказу")
    desired_delivery_time = models.CharField(max_length=100, blank=True, null=True, verbose_name="Желаемое время доставки")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Итого")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACCEPTED,
        verbose_name="Статус"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    def save(self, *args, **kwargs):
        # Сохраняем старый статус, если объект уже существует
        old_status = None
        if self.pk:
            try:
                old_instance = Order.objects.get(pk=self.pk)
                old_status = old_instance.status
            except Order.DoesNotExist:
                pass

        # Сохраняем объект
        super().save(*args, **kwargs)

        # Если статус изменился, отправляем уведомление
        if old_status and old_status != self.status:
            logger.info(f"Статус заказа №{self.id} изменён с {old_status} на {self.status}")
            # Импортируем здесь, чтобы избежать циклического импорта
            from .tasks import notify_user_of_status_change
            notify_user_of_status_change(self.id, old_status, self.status)

    def __str__(self):
        return f"Заказ №{self.id} от {self.user.username or self.user.telegram_id}"

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
