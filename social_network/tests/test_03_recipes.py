from foodgram.models import Recipe, Tag, Ingredient, IngredientInRecipe
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class RecipeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
        self.client.force_authenticate(user=self.user)

        self.tag = Tag.objects.create(name='Test Tag', color='#FF0000', slug='test-tag')

        self.ingredient = Ingredient.objects.create(name='Test Ingredient', measurement_unit='g')

        self.recipe_data = {'name': 'Test Recipe', 'text': 'Test Description', 'cooking_time': 30,
            'tags': [self.tag.id], 'ingredients': [{'id': self.ingredient.id, 'amount': 100}]}

    def test_create_recipe(self):
        url = '/api/recipes/'
        response = self.client.post(url, self.recipe_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Recipe.objects.count(), 1)
        self.assertEqual(Recipe.objects.get().name, 'Test Recipe')

    def test_get_recipe_list(self):
        recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description', cooking_time=30)
        recipe.tags.add(self.tag)
        IngredientInRecipe.objects.create(recipe=recipe, ingredient=self.ingredient, amount=100)
        url = '/api/recipes/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_recipe_detail(self):
        recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description', cooking_time=30)
        recipe.tags.add(self.tag)
        IngredientInRecipe.objects.create(recipe=recipe, ingredient=self.ingredient, amount=100)
        url = f'/api/recipes/{recipe.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Recipe')

    def test_update_recipe(self):
        recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description', cooking_time=30)
        recipe.tags.add(self.tag)
        IngredientInRecipe.objects.create(recipe=recipe, ingredient=self.ingredient, amount=100)
        url = f'/api/recipes/{recipe.id}/'
        updated_data = {'name': 'Updated Recipe', 'text': 'Updated Description', 'cooking_time': 45,
            'tags': [self.tag.id], 'ingredients': [{'id': self.ingredient.id, 'amount': 200}]}
        response = self.client.put(url, updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Recipe.objects.get().name, 'Updated Recipe')

    def test_delete_recipe(self):
        recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description', cooking_time=30)
        recipe.tags.add(self.tag)
        IngredientInRecipe.objects.create(recipe=recipe, ingredient=self.ingredient, amount=100)
        url = f'/api/recipes/{recipe.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Recipe.objects.count(), 0)
