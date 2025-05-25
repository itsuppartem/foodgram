from typing import Any, Dict
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
import requests
from django.conf import settings

from .models import Recipe


TELEGRAM_API_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"


def custom_post(self: Any, request: Any, id: int, custom_serializer: Any, field: str) -> Response:
    user = request.user
    data = {"user": user.id, field: id}
    serializer = custom_serializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


def custom_delete(self: Any, request: Any, id: int, model: Any) -> Response:
    user = request.user
    recipe = get_object_or_404(Recipe, id=id)
    deleting_obj = model.objects.all().filter(user=user, recipe=recipe)
    deleting_obj.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


def send_telegram_notify(telegram_id: str, message: str) -> None:
    print(f"[TELEGRAM_NOTIFY] Попытка отправки: {telegram_id=}, {message=}")
    if not telegram_id:
        print("[TELEGRAM_NOTIFY] Нет telegram_id, не отправляю")
        return
    data = {
        "chat_id": telegram_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        resp = requests.post(TELEGRAM_API_URL, data=data, timeout=5)
        print(f"[TELEGRAM_NOTIFY] Ответ Telegram: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[TELEGRAM_NOTIFY] Ошибка отправки: {e}")
