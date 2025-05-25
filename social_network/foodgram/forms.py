from typing import Any, Dict

from django import forms

from .models import Recipe, Ingredient


class IngredientForm(forms.Form):
    ingredient = forms.ModelChoiceField(queryset=Ingredient.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}))
    amount = forms.FloatField(min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Количество', 'step': '0.1'}))


class RecipeForm(forms.ModelForm):
    steps = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5,
        'placeholder': 'Введите шаги приготовления (каждый шаг с новой строки)'}), required=False)

    class Meta:
        model = Recipe
        fields = ['name', 'text', 'cooking_time', 'image', 'tags', 'difficulty', 'steps']
        widgets: Dict[str, Any] = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Название рецепта'}),
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Описание рецепта'}),
            'cooking_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}), 'tags': forms.CheckboxSelectMultiple(),
            'difficulty': forms.Select(attrs={'class': 'form-control'},
                choices=[('easy', 'Легкий'), ('medium', 'Средний'), ('hard', 'Сложный')])}
