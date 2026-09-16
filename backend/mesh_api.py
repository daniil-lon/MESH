import httpx
from typing import Optional
import os

MESH_BASE_URL = os.getenv("MESH_API_URL", "https://api.mos.ru")


class MeshAPIClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = MESH_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def get_profile(self) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/user/profile",
                headers=self.headers,
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_schedule(self, class_id: str, week_number: int = 0) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/schedule",
                headers=self.headers,
                params={"classId": class_id, "weekNumber": week_number},
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_grades(self, class_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/grades",
                headers=self.headers,
                params={"classId": class_id},
            )
            if response.status_code == 200:
                return response.json()
            return None

    async def get_homework(self, class_id: str) -> list:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/v2/homework",
                headers=self.headers,
                params={"classId": class_id},
            )
            if response.status_code == 200:
                return response.json()
            return []