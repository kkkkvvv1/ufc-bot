import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.tapology.com"

async def get_fight_stats(event_name: str, f1_name: str, f2_name: str) -> dict:
    """
    Находит турнир по названию (или номеру) и возвращает статистику двух бойцов по Tapology.
    """
    async with httpx.AsyncClient(timeout=15) as client:
        # 1. Загружаем страницу UFC событий
        events_page = await client.get(f"{BASE_URL}/fightcenter?group=ufc")
        events_page.raise_for_status()
        soup = BeautifulSoup(events_page.text, "html.parser")

        # 2. Ищем турнир
        event_link_tag = None
        for a in soup.select("a.border-b"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if event_name.lower() in text.lower() or event_name in href:
                event_link_tag = a
                break

        if not event_link_tag:
            return {"error": f"Турнир '{event_name}' не найден на Tapology"}

        event_url = BASE_URL + event_link_tag["href"]

        # 3. Загружаем страницу турнира
        event_page = await client.get(event_url)
        event_page.raise_for_status()
        soup = BeautifulSoup(event_page.text, "html.parser")

        # 4. Находим ссылки на бойцов по английским именам
        fighter_links = {}
        for a in soup.select("a.link-primary-red"):
            name = a.get_text(strip=True)
            if f1_name.lower() in name.lower():
                fighter_links[f1_name] = BASE_URL + a["href"]
            elif f2_name.lower() in name.lower():
                fighter_links[f2_name] = BASE_URL + a["href"]

        if f1_name not in fighter_links or f2_name not in fighter_links:
            return {"error": f"Не удалось найти ссылки на бойцов {f1_name} или {f2_name}"}

        # 5. Парсим данные бойца
        async def parse_fighter(fighter_url):
            resp = await client.get(fighter_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            stats_block = soup.find("div", id="mobileHighlights")
            if not stats_block:
                return {}

            data = {}
            for div in stats_block.find_all("div", class_="flex flex-col"):
                label_div = div.find("div", class_="text-xs")
                value_div = div.find("div", class_="text-3xl")
                extra_div = div.find("div", class_="text-xs11")
                if label_div and value_div:
                    label = label_div.get_text(strip=True)
                    value = value_div.get_text(strip=True)
                    extra = extra_div.get_text(strip=True) if extra_div else ""
                    if label.lower() == "age":
                        data["Возраст"] = value
                    elif label.lower() == "height":
                        data["Рост"] = f"{value} ({extra})"
                    elif label.lower() == "reach":
                        data["Размах рук"] = f"{value} ({extra})"
                    elif label.lower() == "weight":
                        data["Вес"] = f"{value} ({extra})"
            return data

        # 6. Получаем данные обоих бойцов
        fighter_data = {}
        fighter_data[f1_name] = await parse_fighter(fighter_links[f1_name])
        fighter_data[f2_name] = await parse_fighter(fighter_links[f2_name])
        fighter_data["Ссылка"] = event_url

        return fighter_data
