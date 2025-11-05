# ufc_parser.py
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import re

URL = "https://www.bloodandsweat.ru/events_types/ufc/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Словарь для распознавания русских месяцев
MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12
}

def get_surname(full_name: str) -> str:
    """Оставляет только фамилию, убирает скобки и пометки типа (ч)"""
    full_name = re.sub(r"\(.*?\)", "", full_name)
    full_name = re.sub(r"[^A-Za-zА-Яа-яЁё\- ]", "", full_name)
    parts = full_name.strip().split()
    return parts[-1] if parts else full_name

async def get_event_fighters(session, event_url):
    """Парсит бойцов с конкретной страницы турнира"""
    try:
        async with session.get(event_url, headers=HEADERS) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
    except:
        return []

    soup = BeautifulSoup(html, "html.parser")
    fighters = []

    for p in soup.find_all("p"):
        for strong in p.find_all("strong"):
            text_after = strong.next_sibling
            if not text_after:
                continue
            matches = re.findall(r"([^\—]+)—([^\<\n]+)", str(text_after))
            for f1, f2 in matches:
                f1_surname = get_surname(f1)
                f2_surname = get_surname(f2)
                champ = "(ч)" in f1 or "(ч)" in f2
                fighters.append({
                    "fighter": f"{f1_surname} - {f2_surname}",
                    "champ": champ
                })
    return fighters

async def get_upcoming_ufc_events(limit=5):
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(URL) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        events = []

        for block in soup.select("div.list-block-text"):
            title_tag = block.select_one("h2 a")
            title = title_tag.get_text(strip=True) if title_tag else "Неизвестно"
            link = title_tag["href"] if title_tag and title_tag.has_attr("href") else None

            place, date_text = "Неизвестно", "Неизвестно"
            event_date_obj = None
            info_p = block.select_one("p.content-text-p")

            if info_p:
                for span in info_p.find_all("span"):
                    b = span.find("b")
                    if not b:
                        continue
                    label = b.get_text(strip=True)
                    text_after = span.get_text(strip=True).replace(label, "").strip(": ").strip()

                    if "Место проведения" in label:
                        place = text_after
                    elif "Дата проведения" in label:
                        date_text = text_after
                        try:
                            # Парсим дату вручную через словарь месяцев
                            date_str = text_after.replace(" года", "").strip()  # '1 ноября 2025'
                            day, month_str, year = date_str.split()
                            month = MONTHS.get(month_str.lower())
                            if month:
                                event_date_obj = datetime(int(year), month, int(day))
                        except Exception as e:
                            print(f"Ошибка парсинга даты: {text_after} -> {e}")
                            event_date_obj = None

            # Пропускаем события, которые уже прошли
            if event_date_obj and event_date_obj.date() < datetime.now().date():
                continue

            fighters = await get_event_fighters(session, link) if link else []

            events.append({
                "title": title,
                "place": place,
                "date": date_text,
                "link": link,
                "fighters": fighters
            })

            if len(events) >= limit:
                break

    return events
