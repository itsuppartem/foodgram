from foodgram.models import Recipe, Comment
from rest_framework import status
from rest_framework.test import APITestCase
from users.models import User


class CommentTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
        self.recipe = Recipe.objects.create(author=self.user, name='Test Recipe', text='Test Description',
            cooking_time=30)
        self.client.force_authenticate(user=self.user)

    def test_create_comment(self):
        url = f'/api/recipes/{self.recipe.id}/comments/'
        data = {'text': 'Test comment'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 1)
        self.assertEqual(Comment.objects.get().text, 'Test comment')
        self.assertEqual(response.data['text'], 'Test comment')

    def test_delete_comment(self):
        comment = Comment.objects.create(recipe=self.recipe, author=self.user, text='Test comment')
        url = f'/api/recipes/{self.recipe.id}/comments/{comment.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Comment.objects.count(), 0)
