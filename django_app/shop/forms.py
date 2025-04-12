# django_app/shop/forms.py
from django import forms
from .models import Category

class ProductImportForm(forms.Form):
    file = forms.FileField(label="Выберите файл для импорта")
    file_format = forms.ChoiceField(
        label="Формат файла",
        choices=[
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('xlsx', 'Excel (XLSX)'),
        ]
    )

class ProductExportForm(forms.Form):
    file_format = forms.ChoiceField(
        label="Формат файла",
        choices=[
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('xlsx', 'Excel (XLSX)'),
        ]
    )
    fields = forms.MultipleChoiceField(
        label="Поля для экспорта",
        choices=[
            ('id', 'ID'),
            ('name', 'Название'),
            ('description', 'Описание'),
            ('price', 'Цена'),
            ('category_path', 'Путь категории'),
            ('photo_filename', 'Имя файла фотографии'),
            ('is_active', 'Активен'),
            ('created_at', 'Дата создания'),
        ],
        widget=forms.CheckboxSelectMultiple,
        initial=['id', 'name', 'description', 'price', 'category_path', 'photo_filename', 'is_active']
    )
    category = forms.ModelChoiceField(
        label="Категория (опционально)",
        queryset=Category.objects.all(),
        required=False
    )
    is_active = forms.ChoiceField(
        label="Статус",
        choices=[
            ('', 'Все'),
            ('1', 'Активные'),
            ('0', 'Неактивные'),
        ],
        required=False
    )
    date_from = forms.DateField(
        label="Дата создания (с)",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        label="Дата создания (по)",
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
