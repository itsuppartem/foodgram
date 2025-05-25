import httpx
from typing import Dict, Any, Optional
from django.conf import settings


class AIService:
    def __init__(self) -> None:
        self.base_url = settings.AI_API_URL
        self.api_key = settings.AI_API_KEY
        self.timeout = 60
        self.headers = {"X-API-Key": self.api_key}

    async def _make_request(
        self,
        endpoint: str,
        json_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=json_data,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.ReadTimeout:
            return {"error": "AI сервис не отвечает (timeout)"}
        except Exception as e:
            return {"error": str(e)}

    async def generate_recipe(
        self,
        prompt: str,
        cooking_time: Optional[int] = None,
        difficulty: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self._make_request(
            "/api/v1/recipes/generate-by-text",
            {
                "prompt": prompt,
                "cooking_time": cooking_time,
                "difficulty": difficulty
            }
        )

    async def generate_image(self, prompt: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/generate-image",
                    json={"prompt": prompt},
                    headers=self.headers
                )
                response.raise_for_status()
                return response.content
        except Exception:
            return None

    async def ask(self, question: str) -> Dict[str, Any]:
        return await self._make_request(
            "/api/v1/recipes/ask",
            {"question": question}
        ) 