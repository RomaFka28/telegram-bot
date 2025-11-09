from typing import Iterable, List

import aiohttp

from config import settings


async def check_interactions(new_med_name: str, existing_names: Iterable[str]) -> List[str]:
    warnings: List[str] = []
    if not existing_names:
        return warnings

    async with aiohttp.ClientSession() as session:
        for other in existing_names:
            params = {"drug1": new_med_name, "drug2": other}
            try:
                async with session.get(settings.knowledge_api_url, params=params, timeout=8) as response:
                    if response.status != 200:
                        continue
                    data = await response.json()
                    if "fullInteractionTypeGroup" in data:
                        warnings.append(
                            f"Возможное взаимодействие между {new_med_name} и {other}. "
                            "Обсудите это с врачом."
                        )
            except aiohttp.ClientError:
                continue
    return warnings
