from typing import Any
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import Recipe, IngredientInRecipe

@receiver(pre_save, sender=Recipe)
def validate_recipe(sender: Any, instance: Recipe, **kwargs: Any) -> None:
    if instance.cooking_time < 0:
        raise ValidationError('Время приготовления должно быть не меньше 0')
    if not instance.ingredients.exists():
        raise ValidationError('Рецепт должен содержать хотя бы один ингредиент')
    if not instance.tags.exists():
        raise ValidationError('Рецепт должен содержать хотя бы один тег')

@receiver(pre_save, sender=IngredientInRecipe)
def validate_ingredient_amount(sender: Any, instance: IngredientInRecipe, **kwargs: Any) -> None:
    if instance.amount is not None and instance.amount < 0:
        raise ValidationError('Количество ингредиента должно быть не меньше 0') 