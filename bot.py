import asyncio
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "/data/anime.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")
if ADMIN_ID <= 0:
    raise RuntimeError("Set ADMIN_ID to your Telegram numeric user ID.")

def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS anime (code TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '')")
    conn.execute("CREATE TABLE IF NOT EXISTS episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, episode_no INTEGER NOT NULL, url TEXT NOT NULL, UNIQUE(code, episode_no))")
    conn.commit()
    return conn

def valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def episode_keyboard(code):
    conn = db()
    rows = conn.execute("SELECT episode_no FROM episodes WHERE code=? ORDER BY episode_no", (code,)).fetchall()
    conn.close()
    builder = InlineKeyboardBuilder()
    for (episode,) in rows:
        builder.button(text=f"{episode}-qism", callback_data=f"ep:{code}:{episode}")
    builder.adjust(3)
    return builder.as_markup() if rows else None

dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("🎬 AnimeTV Uz botiga xush kelibsiz!\n\nAnime kodini yuboring (masalan: 149).\nYordam: /help")

@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "Anime kodini yuboring (masalan: 149).\n\n"
        "Admin buyruqlari:\n"
        "/addanime kod | nomi | tavsif\n"
        "/addepisode kod | qism_raqami | video_havolasi\n"
        "/delanime kod\n"
        "/del episode kod qism_raqami"
    )

@dp.message(Command("addanime"))
async def add_anime(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Bu buyruq faqat admin uchun.")
    parts = [part.strip() for part in message.text.partition(" ")[2].split("|", 2)]
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1]:
        return await message.answer("Format: /addanime 149 | Anime nomi | Tavsif")
    code, title = parts[0], parts[1]
    description = parts[2] if len(parts) > 2 else ""
    conn = db()
    conn.execute(
        "INSERT INTO anime(code,title,description) VALUES(?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET title=excluded.title,description=excluded.description",
        (code, title, description)
    )
    conn.commit()
    conn.close()
    await message.answer(f"✅ {code} kodi uchun «{title}» saqlandi.")

@dp.message(Command("addepisode"))
async def add_episode(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Bu buyruq faqat admin uchun.")
    parts = [part.strip() for part in message.text.partition(" ")[2].split("|", 2)]
    if len(parts) != 3 or not parts[0].isdigit() or not parts[1].isdigit() or not valid_url(parts[2]):
        return await message.answer("Format: /addepisode 149 | 1 | https://video-sayt.uz/video")
    code, episode, url = parts[0], int(parts[1]), parts[2]
    conn = db()
    exists = conn.execute("SELECT 1 FROM anime WHERE code=?", (code,)).fetchone()
    if not exists:
        conn.close()
        return await message.answer("Avval anime qo‘shing: /addanime 149 | Anime nomi")
    conn.execute(
        "INSERT INTO episodes(code,episode_no,url) VALUES(?,?,?) "
        "ON CONFLICT(code,episode_no) DO UPDATE SET url=excluded.url",
        (code, episode, url)
    )
    conn.commit()
    conn.close()
    await message.answer(f"✅ {code} kodi uchun {episode}-qism havolasi saqlandi.")

@dp.message(Command("delanime"))
async def delete_anime(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Bu buyruq faqat admin uchun.")
    code = message.text.partition(" ")[2].strip()
    if not code.isdigit():
        return await message.answer("Format: /delanime 149")
    conn = db()
    conn.execute("DELETE FROM episodes WHERE code=?", (code,))
    cursor = conn.execute("DELETE FROM anime WHERE code=?", (code,))
    conn.commit()
    conn.close()
    await message.answer("Anime o‘chirildi." if cursor.rowcount else "Bunday kod topilmadi.")

@dp.message(Command("del"))
async def delete_episode(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("Bu buyruq faqat admin uchun.")
    parts = message.text.partition(" ")[2].split()
    if len(parts) != 3 or parts[0].lower() != "episode" or not parts[1].isdigit() or not parts[2].isdigit():
        return await message.answer("Format: /del episode 149 1")
    conn = db()
    cursor = conn.execute("DELETE FROM episodes WHERE code=? AND episode_no=?", (parts[1], int(parts[2])))
    conn.commit()
    conn.close()
    await message.answer("Qism o‘chirildi." if cursor.rowcount else "Bunday qism topilmadi.")

@dp.message(F.text)
async def lookup_anime(message: Message):
    code = message.text.strip()
    if not code.isdigit():
        return
    conn = db()
    anime = conn.execute("SELECT title,description FROM anime WHERE code=?", (code,)).fetchone()
    conn.close()
    if not anime:
        return await message.answer("Bu kod bo‘yicha anime topilmadi.")
    title, description = anime
    text = f"🎬 {title}\n🔢 Kod: {code}"
    if description:
        text += f"\n\n{description}"
    text += "\n\nTomosha qilish uchun qismni tanlang:"
    await message.answer(text, reply_markup=episode_keyboard(code))

@dp.callback_query(F.data.startswith("ep:"))
async def choose_episode(callback: CallbackQuery):
    _, code, episode = callback.data.split(":")
    conn = db()
    row = conn.execute("SELECT url FROM episodes WHERE code=? AND episode_no=?", (code, int(episode))).fetchone()
    conn.close()
    if not row:
        await callback.answer("Qism topilmadi.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="▶️ Videoni ko‘rish", url=row[0])
    ]])
    await callback.message.answer(f"{episode}-qism:", reply_markup=keyboard)
    await callback.answer()

async def main():
    conn = db()
    conn.close()
    bot = Bot(TOKEN)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
