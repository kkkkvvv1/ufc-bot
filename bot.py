import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from ufc_parser import get_upcoming_ufc_events
from ufc_fighttime_parser import get_fight_stats

API_TOKEN = "8473903856:AAEqUzedWO8hcCJi5PAt7JIyhyIRkTp4RIE"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

EVENT_CACHE = {}
FIGHT_CACHE = {}
USER_MESSAGES = {}

async def clean_previous_messages(message: types.Message):
    user_id = message.from_user.id
    if user_id in USER_MESSAGES:
        try:
            await bot.delete_message(user_id, USER_MESSAGES[user_id])
        except:
            pass
    USER_MESSAGES[user_id] = message.message_id

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await clean_previous_messages(message)
    sent = await message.answer(
        "👋 Привет! Я UFC бот.\n\n"
        "Используй /ufc, чтобы посмотреть ближайшие турниры UFC 🥊"
    )
    USER_MESSAGES[message.from_user.id] = sent.message_id

@dp.message(Command("ufc"))
async def show_ufc_events(message: types.Message):
    await clean_previous_messages(message)
    sent = await message.answer("⏳ Загружаю список турниров...")
    USER_MESSAGES[message.from_user.id] = sent.message_id

    try:
        events = await get_upcoming_ufc_events(limit=5)
    except Exception as e:
        await sent.edit_text(f"⚠️ Ошибка загрузки данных: {e}")
        return

    if not events:
        await sent.edit_text("😕 Не найдено ближайших турниров UFC.")
        return

    EVENT_CACHE[message.from_user.id] = events
    kb = InlineKeyboardBuilder()
    for i, e in enumerate(events):
        kb.button(text=f"{e['title']} ({e['date']})", callback_data=f"event_{i}")
    kb.adjust(1)
    await sent.edit_text("Выбери турнир:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("event_"))
async def show_event_fights(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    event_index = int(callback.data.split("_")[1])
    events = EVENT_CACHE.get(user_id)
    if not events or event_index >= len(events):
        await callback.answer("⚠️ Список турниров устарел. Нажми /ufc снова.", show_alert=True)
        return

    e = events[event_index]
    fighters_sorted = sorted(e["fighters"], key=lambda f: not f.get("champ", False))
    FIGHT_CACHE[user_id] = fighters_sorted

    kb = InlineKeyboardBuilder()
    for idx, f in enumerate(fighters_sorted):
        text = f["fighter"]
        if f.get("champ"):
            text = f"🏅 {text}"
        elif idx == 0:
            text = f"⭐ {text}"
        elif idx == 1:
            text = f"🔥 {text}"
        kb.button(text=text, callback_data=f"fight_{idx}")
    kb.button(text="⬅️ Назад к турнирам", callback_data="back_to_events")
    kb.adjust(1)

    await callback.message.edit_text(
        f"🏆 <b>{e['title']}</b>\n📅 {e['date']}\n📍 {e['place']}\n\nВыбери бой:",
        parse_mode="HTML",
        reply_markup=kb.as_markup(),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("fight_"))
async def show_fight_comparison(callback: types.CallbackQuery):
    import re
    user_id = callback.from_user.id
    fights = FIGHT_CACHE.get(user_id)
    fight_index = int(callback.data.split("_")[1])
    if not fights or fight_index >= len(fights):
        await callback.answer("⚠️ Ошибка: бой не найден.", show_alert=True)
        return

    fight = fights[fight_index]
    fighter_str = fight["fighter"]
    parts = re.split(r'\s+vs\s+|\s+-\s+', fighter_str)
    if len(parts) != 2:
        await callback.answer("⚠️ Ошибка разбора имён бойцов.", show_alert=True)
        return

    f1_name, f2_name = parts[0].strip(), parts[1].strip()
    event_title = None
    for e in EVENT_CACHE.get(user_id, []):
        if fight in e["fighters"]:
            event_title = e.get("title")
            break
    if not event_title:
        await callback.message.edit_text("⚠️ Не удалось определить турнир.")
        return

    await callback.message.edit_text(f"⏳ Загружаю данные с fighttime.ru: {f1_name} vs {f2_name} ...")

    try:
        print("🔹 Поиск URL турнира на fighttime.ru")
        event_number = re.search(r'\d+', e['title']).group(0)  # берем первый номер из title
        fight_data = await get_fight_stats(event_number, f1_name, f2_name)
        print("🔹 Данные боя получены")
    except Exception as e:
        print("❌ Ошибка на этапе await get_fight_stats:", e)
        await callback.message.edit_text(f"⚠️ Ошибка при получении данных: {e}")
        return

    if "error" in fight_data:
        await callback.message.edit_text(f"⚠️ {fight_data['error']}")
        return

    text = f"🤜 <b>{f1_name}</b> vs <b>{f2_name}</b> 🤛\n\n"
    for fighter, data in fight_data.items():
        if fighter == "Ссылка":
            continue
        text += f"<b>{fighter}</b>:\n"
        for k, v in data.items():
            text += f"{k}: {v}\n"
        text += "\n"
    text += f"<a href='{fight_data['Ссылка']}'>🔗 Подробнее на fighttime.ru</a>"

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад к боям", callback_data="event_back_fights")
    kb.adjust(1)

    await callback.message.edit_text(
        text.strip(),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await callback.answer()

# Остальные callback-обработчики остаются без изменений (back_to_fights, back_to_events)...

async def main():
    print("🚀 UFC бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
