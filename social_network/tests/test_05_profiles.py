from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User, Follow


class ProfileTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpass123')
        self.other_user = User.objects.create_user(username='otheruser', email='other@example.com',
            password='testpass123')
        self.client.force_authenticate(user=self.user)

    def test_get_profile(self):
        url = f'/api/users/{self.other_user.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.other_user.id)

    def test_follow_user(self):
        url = f'/api/users/{self.other_user.id}/subscribe/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Follow.objects.count(), 1)

    def test_unfollow_user(self):
        Follow.objects.create(user=self.user, author=self.other_user)
        url = f'/api/users/{self.other_user.id}/subscribe/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Follow.objects.count(), 0)

    def test_get_subscriptions(self):
        Follow.objects.create(user=self.user, author=self.other_user)
        url = '/api/users/subscriptions/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.other_user.id)
