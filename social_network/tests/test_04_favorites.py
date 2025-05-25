from foodgram.models import Recipe, Favorite, ShoppingCart
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class FavoriteAndCartTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
        self.recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description',
            cooking_time=30)
        self.client.force_authenticate(user=self.user)

    def test_add_to_favorites(self):
        url = f'/api/recipes/{self.recipe.id}/favorite/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_remove_from_favorites(self):
        Favorite.objects.create(user=self.user, recipe=self.recipe)
        url = f'/api/recipes/{self.recipe.id}/favorite/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_add_to_shopping_cart(self):
        url = f'/api/recipes/{self.recipe.id}/shopping_cart/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ShoppingCart.objects.count(), 1)

    def test_remove_from_shopping_cart(self):
        ShoppingCart.objects.create(user=self.user, recipe=self.recipe)
        url = f'/api/recipes/{self.recipe.id}/shopping_cart/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ShoppingCart.objects.count(), 0)

    def test_download_shopping_cart(self):
        ShoppingCart.objects.create(user=self.user, recipe=self.recipe)
        url = '/api/recipes/download_shopping_cart/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
