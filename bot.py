import asyncio
import logging
import re
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeExpiredError,
    PhoneCodeInvalidError, FloodWaitError
)
from telethon.sessions import StringSession
import asyncpg
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# ==================== КОНФИГУРАЦИЯ ====================
API_ID = 32480523
API_HASH = "147839735c9fa4e83451209e9b55cfc5"
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")
ADMIN_IDS = [7973988177]
YOOMONEY_WALLET = "4100119286550472"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
# ID для tg-emoji в сообщениях
EMOJI_ID = {
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "people": "5870772616305839506",
    "file": "5870528606328852614",
    "smile": "5870764288364252592",
    "stats_grow": "5870930636742595124",
    "stats": "5870921681735781843",
    "house": "5873147866364514353",
    "lock_closed": "6037249452824072506",
    "lock_open": "6037496202990194718",
    "megaphone": "6039422865189638057",
    "check": "5870633910337015697",
    "cross": "5870657884844462243",
    "pencil": "5870676941614354370",
    "trash": "5870875489362513438",
    "down": "5893057118545646106",
    "clip": "6039451237743595514",
    "link": "5769289093221454192",
    "info": "6028435952299413210",
    "bot": "6030400221232501136",
    "eye": "6037397706505195857",
    "eye_hidden": "6037243349675544634",
    "send": "5963103826075456248",
    "download": "6039802767931871481",
    "bell": "6039486778597970865",
    "gift": "6032644646587338669",
    "clock": "5983150113483134607",
    "celebrate": "6041731551845159060",
    "wallet": "5769126056262898415",
    "box": "5884479287171485878",
    "cryptobot": "5260752406890711732",
    "calendar": "5890937706803894250",
    "tag": "5886285355279193209",
    "clock_past": "5775896410780079073",
    "apps": "5778672437122045013",
    "brush": "6050679691004612757",
    "add_text": "5771851822897566479",
    "money": "5904462880941545555",
    "money_send": "5890848474563352982",
    "money_accept": "5879814368572478751",
    "code": "5940433880585605708",
    "loading": "5345906554510012647",
    "usa": "5202021044105257611",
    "russia": "5449408995691341691",
    "ukraine": "5447309366568953338",
    "belarus": "5382219601054544127",
    "kazakhstan": "5228718354658769982",
    "uzbekistan": "5449829434334912605",
    "china": "5431782733376399004",
    "myanmar": "5188162778073935826",
    "india": "5447419223242449630",
    "bangladesh": "5222131025877936317",
    "pakistan": "5269660289321679111",
    "nigeria": "5411568100430587798",
    "spain": "5201957744877248121",
    "france": "5202132623060640759",
    "uk": "5202196682497859879",
    "romania": "5411159898148840778",
    "japan": "5456261908069885892",
    "egypt": "5226476858471626962",
    "sweden": "5384542551296455687",
    "tajikistan": "5427304285077516492",
    "brazil": "5202074005346983800",
    "argentina": "5262873863036872166",
    "canada": "5382084502858249131",
}

COUNTRY_NAMES = {
    "usa": "США", "russia": "Россия", "ukraine": "Украина",
    "belarus": "Беларусь", "kazakhstan": "Казахстан", "uzbekistan": "Узбекистан",
    "china": "Китай", "myanmar": "Мьянма", "india": "Индия",
    "bangladesh": "Бангладеш", "pakistan": "Пакистан", "nigeria": "Нигерия",
    "spain": "Испания", "france": "Франция", "uk": "Великобритания",
    "romania": "Румыния", "japan": "Япония", "egypt": "Египет",
    "sweden": "Швеция", "tajikistan": "Таджикистан", "brazil": "Бразилия",
    "argentina": "Аргентина", "canada": "Канада"
}

ACCOUNT_TYPES = {
    "newreg": "Новореги",
    "leaved": "С отлёгой",
    "warmed": "Прогретые"
}


def t(key: str) -> str:
    """Тег для премиум эмодзи в тексте сообщения"""
    return f'<tg-emoji emoji-id="{EMOJI_ID[key]}"></tg-emoji>'


def icon(key: str) -> str:
    """ID эмодзи для icon_custom_emoji_id в кнопках"""
    return EMOJI_ID[key]


def msk_time() -> datetime:
    return datetime.now(timezone(timedelta(hours=3)))


def format_date(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%d.%m.%Y %H:%M")


# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

    async def init_tables(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance DECIMAL DEFAULT 0,
                    purchases_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    account_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    session_string TEXT,
                    password TEXT,
                    code TEXT,
                    price_rub DECIMAL DEFAULT 0,
                    price_usdt DECIMAL DEFAULT 0,
                    price_ton DECIMAL DEFAULT 0,
                    is_sold BOOLEAN DEFAULT FALSE,
                    sold_to BIGINT,
                    sold_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS purchases (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    account_id INT REFERENCES accounts(id),
                    price DECIMAL,
                    currency TEXT,
                    purchase_date TIMESTAMP DEFAULT NOW(),
                    code_received BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS prices (
                    id SERIAL PRIMARY KEY,
                    account_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    price_rub DECIMAL DEFAULT 0,
                    price_usdt DECIMAL DEFAULT 0,
                    price_ton DECIMAL DEFAULT 0,
                    UNIQUE(account_type, country)
                );

                CREATE TABLE IF NOT EXISTS crypto_payments (
                    id SERIAL PRIMARY KEY,
                    invoice_id TEXT UNIQUE,
                    user_id BIGINT,
                    amount DECIMAL,
                    currency TEXT,
                    status TEXT DEFAULT 'pending',
                    account_type TEXT,
                    country TEXT,
                    is_topup BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

    async def get_or_create_user(self, user_id: int, username: str = None):
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                    user_id, username
                )
                return {"user_id": user_id, "username": username, "balance": 0, "purchases_count": 0}
            return dict(user)

    async def get_user(self, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None

    async def add_balance(self, user_id: int, amount: Decimal):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )

    async def deduct_balance(self, user_id: int, amount: Decimal):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                amount, user_id
            )

    async def get_available_account(self, account_type: str, country: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM accounts 
                   WHERE account_type = $1 AND country = $2 AND is_sold = FALSE 
                   LIMIT 1""",
                account_type, country
            )

    async def mark_account_sold(self, account_id: int, user_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE accounts SET is_sold = TRUE, sold_to = $1, sold_at = NOW() 
                   WHERE id = $2""",
                user_id, account_id
            )

    async def add_purchase(self, user_id: int, account_id: int, price: Decimal, currency: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET purchases_count = purchases_count + 1 WHERE user_id = $1",
                user_id
            )
            return await conn.fetchval(
                """INSERT INTO purchases (user_id, account_id, price, currency) 
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                user_id, account_id, price, currency
            )

    async def get_user_purchases(self, user_id: int):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT p.*, a.phone, a.code, a.country, a.account_type 
                   FROM purchases p 
                   JOIN accounts a ON p.account_id = a.id 
                   WHERE p.user_id = $1 
                   ORDER BY p.purchase_date DESC""",
                user_id
            )
            return [dict(row) for row in rows]

    async def get_purchase_by_id(self, purchase_id: int, user_id: int):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT p.*, a.phone, a.code, a.session_string, a.account_type, a.country
                   FROM purchases p 
                   JOIN accounts a ON p.account_id = a.id 
                   WHERE p.id = $1 AND p.user_id = $2""",
                purchase_id, user_id
            )
            return dict(row) if row else None

    async def update_account_code(self, account_id: int, code: str):
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE accounts SET code = $1 WHERE id = $2", code, account_id)

    async def set_price(self, account_type: str, country: str,
                        price_rub: Decimal, price_usdt: Decimal, price_ton: Decimal):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO prices (account_type, country, price_rub, price_usdt, price_ton)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (account_type, country) 
                   DO UPDATE SET price_rub = $3, price_usdt = $4, price_ton = $5""",
                account_type, country, price_rub, price_usdt, price_ton
            )

    async def get_price(self, account_type: str, country: str):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prices WHERE account_type = $1 AND country = $2",
                account_type, country
            )
            return dict(row) if row else None

    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row["user_id"] for row in rows]

    async def get_stats(self):
        async with self.pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_accounts = await conn.fetchval("SELECT COUNT(*) FROM accounts")
            sold_accounts = await conn.fetchval("SELECT COUNT(*) FROM accounts WHERE is_sold = TRUE")
            return {
                "total_users": total_users,
                "total_accounts": total_accounts,
                "sold_accounts": sold_accounts,
                "available": total_accounts - sold_accounts
            }

    async def add_crypto_payment(self, invoice_id: str, user_id: int, amount: Decimal,
                                  currency: str, account_type: str = "", country: str = "",
                                  is_topup: bool = False):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO crypto_payments (invoice_id, user_id, amount, currency, 
                   account_type, country, is_topup)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                invoice_id, user_id, amount, currency, account_type, country, is_topup
            )

    async def update_crypto_payment(self, invoice_id: str, status: str):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE crypto_payments SET status = $1 WHERE invoice_id = $2 RETURNING *",
                status, invoice_id
            )

    async def get_pending_crypto_payments(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM crypto_payments WHERE status = 'pending'")
            return [dict(row) for row in rows]

    async def add_account(self, account_type: str, country: str, phone: str,
                          session_string: str = None, password: str = None,
                          price_rub: Decimal = 0, price_usdt: Decimal = 0, price_ton: Decimal = 0):
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO accounts (account_type, country, phone, session_string, 
                   password, price_rub, price_usdt, price_ton)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING id""",
                account_type, country, phone, session_string, password,
                price_rub, price_usdt, price_ton
            )


db = Database()

# ==================== FSM ====================
class AdminStates(StatesGroup):
    waiting_broadcast = State()
    waiting_balance_user = State()
    waiting_balance_amount = State()
    waiting_add_account_phone = State()
    waiting_add_account_code = State()
    waiting_add_account_password = State()
    waiting_change_price_type = State()
    waiting_change_price_rub = State()
    waiting_change_price_usdt = State()
    waiting_change_price_ton = State()


# ==================== CRYPTO PAY API ====================
class CryptoPayAPI:
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        self.token = token

    async def create_invoice(self, amount: Decimal, currency: str = "USDT",
                              description: str = "") -> Optional[Dict]:
        url = f"{self.BASE_URL}/createInvoice"
        headers = {"Crypto-Pay-API-Token": self.token}
        data = {
            "asset": currency,
            "amount": str(amount),
            "description": description,
            "allow_comments": False,
            "allow_anonymous": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result.get("result")
                logger.error(f"Crypto Pay error: {resp.status}")
                return None

    async def get_invoice(self, invoice_id: int) -> Optional[Dict]:
        url = f"{self.BASE_URL}/getInvoices"
        headers = {"Crypto-Pay-API-Token": self.token}
        params = {"invoice_ids": str(invoice_id)}
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    items = result.get("result", {}).get("items", [])
                    return items[0] if items else None
                return None


crypto_pay = CryptoPayAPI(CRYPTO_BOT_TOKEN) if CRYPTO_BOT_TOKEN else None

# ==================== TElethon ====================
telethon_client = TelegramClient(StringSession(), API_ID, API_HASH)


async def fetch_code_from_telegram(session_string: str) -> Optional[str]:
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None

        dialogs = await client.get_dialogs(limit=10)
        for dialog in dialogs:
            messages = await client.get_messages(dialog, limit=20)
            for msg in messages:
                if msg.message:
                    code_match = re.search(r'\b(\d{5,6})\b', msg.message)
                    if code_match:
                        code = code_match.group(1)
                        await client.disconnect()
                        return code
        await client.disconnect()
    except Exception as e:
        logger.error(f"Error fetching code: {e}")
    return None


# ==================== КЛАВИАТУРЫ (строго icon_custom_emoji_id) ====================
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Купить аккаунт",
            callback_data="buy_account",
            icon_custom_emoji_id=icon("box")
        )],
        [InlineKeyboardButton(
            text="Профиль",
            callback_data="profile",
            icon_custom_emoji_id=icon("profile")
        )],
        [
            InlineKeyboardButton(
                text="Поддержка",
                callback_data="support",
                icon_custom_emoji_id=icon("info")
            ),
            InlineKeyboardButton(
                text="Проекты",
                callback_data="projects",
                icon_custom_emoji_id=icon("link")
            )
        ]
    ])


def back_to_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Назад в меню",
            callback_data="main_menu",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def back_to_profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Назад",
            callback_data="profile",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Мои покупки",
            callback_data="my_purchases",
            icon_custom_emoji_id=icon("box")
        )],
        [InlineKeyboardButton(
            text="Пополнить баланс",
            callback_data="top_up",
            icon_custom_emoji_id=icon("wallet")
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def account_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=name,
            callback_data=f"acc_type_{key}",
            icon_custom_emoji_id=icon("tag")
        )]
        for key, name in ACCOUNT_TYPES.items()
    ] + [
        [InlineKeyboardButton(
            text="Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def countries_kb(account_type: str, page: int = 0, per_page: int = 8) -> InlineKeyboardMarkup:
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page
    start = page * per_page
    page_countries = countries[start:start + per_page]

    keyboard = []
    for country in page_countries:
        keyboard.append([InlineKeyboardButton(
            text=COUNTRY_NAMES[country],
            callback_data=f"country_{account_type}_{country}",
            icon_custom_emoji_id=icon(country)
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◁",
            callback_data=f"page_{account_type}_{page - 1}",
            icon_custom_emoji_id=icon("down")
        ))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(
            text="▷",
            callback_data=f"page_{account_type}_{page + 1}",
            icon_custom_emoji_id=icon("send")
        ))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(
        text="Назад",
        callback_data="buy_account",
        icon_custom_emoji_id=icon("down")
    )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def payment_methods_kb(account_type: str, country: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="USDT",
            callback_data=f"pay_usdt_{account_type}_{country}",
            icon_custom_emoji_id=icon("money")
        )],
        [InlineKeyboardButton(
            text="TON",
            callback_data=f"pay_ton_{account_type}_{country}",
            icon_custom_emoji_id=icon("money")
        )],
        [InlineKeyboardButton(
            text="Рубли",
            callback_data=f"pay_rub_{account_type}_{country}",
            icon_custom_emoji_id=icon("money_accept")
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=f"acc_type_{account_type}",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def get_code_kb(purchase_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Получить код",
            callback_data=f"get_code_{purchase_id}",
            icon_custom_emoji_id=icon("code")
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="my_purchases",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Crypto Bot (USDT/TON)",
            callback_data="topup_crypto",
            icon_custom_emoji_id=icon("cryptobot")
        )],
        [InlineKeyboardButton(
            text="YooMoney (Рубли)",
            callback_data="topup_yoomoney",
            icon_custom_emoji_id=icon("money")
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="profile",
            icon_custom_emoji_id=icon("down")
        )]
    ])


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Статистика",
            callback_data="admin_stats",
            icon_custom_emoji_id=icon("stats")
        )],
        [InlineKeyboardButton(
            text="Рассылка",
            callback_data="admin_broadcast",
            icon_custom_emoji_id=icon("megaphone")
        )],
        [InlineKeyboardButton(
            text="Выдать баланс",
            callback_data="admin_give_balance",
            icon_custom_emoji_id=icon("money_send")
        )],
        [InlineKeyboardButton(
            text="Добавить аккаунт",
            callback_data="admin_add_account",
            icon_custom_emoji_id=icon("add_text")
        )],
        [InlineKeyboardButton(
            text="Изменить цены",
            callback_data="admin_change_price",
            icon_custom_emoji_id=icon("pencil")
        )]
    ])


def add_account_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=name,
            callback_data=f"addacc_type_{key}",
            icon_custom_emoji_id=icon("tag")
        )]
        for key, name in ACCOUNT_TYPES.items()
    ])


def change_price_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=name,
            callback_data=f"chprice_type_{key}",
            icon_custom_emoji_id=icon("tag")
        )]
        for key, name in ACCOUNT_TYPES.items()
    ])


# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ==================== СТАРТ ====================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await db.get_or_create_user(message.from_user.id, message.from_user.username)
    text = (
        f'{t("bot")} Добро пожаловать в <b>Vest Traff Accs</b>!\n\n'
        f'{t("box")} Покупка аккаунтов Telegram\n\n'
        f'{t("info")} Выберите действие:'
    )
    await message.answer(text, reply_markup=main_menu_kb())


@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        f'{t("bot")} <b>Главное меню</b>\nВыберите действие:',
        reply_markup=main_menu_kb()
    )
    await callback.answer()


# ==================== ПРОЕКТЫ ====================
@dp.callback_query(F.data == "projects")
async def projects(callback: CallbackQuery):
    text = (
        f'{t("link")} <b>Наши проекты:</b>\n\n'
        f'{t("bot")} <b>Телеграмм комбайны:</b>\n'
        f'• @VestTrafferBot\n• @VestTraffer2bot\n• @VestTraffer3bot\n\n'
        f'{t("megaphone")} <b>Канал:</b> @VestTraffer'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    await callback.answer()


# ==================== ПОДДЕРЖКА ====================
@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.edit_text(
        f'{t("info")} <b>Поддержка</b>\n\nПо всем вопросам: @VestSupport',
        reply_markup=back_to_main_kb()
    )
    await callback.answer()


# ==================== ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user = await db.get_or_create_user(callback.from_user.id, callback.from_user.username)
    text = (
        f'{t("profile")} <b>Профиль</b>\n\n'
        f'{t("tag")} <b>Юзернейм:</b> @{user.get("username") or "нет"}\n'
        f'{t("info")} <b>ID:</b> <code>{user["user_id"]}</code>\n'
        f'{t("wallet")} <b>Баланс:</b> {user["balance"]} ₽\n'
        f'{t("box")} <b>Покупок:</b> {user["purchases_count"]}'
    )
    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()


# ==================== МОИ ПОКУПКИ ====================
@dp.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    purchases = await db.get_user_purchases(callback.from_user.id)
    if not purchases:
        await callback.message.edit_text(
            f'{t("box")} <b>Мои покупки</b>\n\n{t("info")} У вас пока нет покупок.',
            reply_markup=back_to_profile_kb()
        )
        await callback.answer()
        return

    text = f'{t("box")} <b>Мои покупки:</b>\n\n'
    keyboard = []

    for i, p in enumerate(purchases[:10], 1):
        text += (
            f'{i}. {t("calendar")} {format_date(p["purchase_date"])}\n'
            f'   {t("tag")} <code>{p["phone"]}</code>\n'
            f'   {t("money")} {p["price"]} {p["currency"]}\n\n'
        )
        keyboard.append([InlineKeyboardButton(
            text=f"Код #{p['id']}",
            callback_data=f"get_code_{p['id']}",
            icon_custom_emoji_id=icon("code")
        )])

    keyboard.append([InlineKeyboardButton(
        text="Назад",
        callback_data="profile",
        icon_custom_emoji_id=icon("down")
    )])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await callback.answer()


# ==================== ПОЛУЧЕНИЕ КОДА ====================
@dp.callback_query(F.data.startswith("get_code_"))
async def get_code(callback: CallbackQuery):
    purchase_id = int(callback.data.split("_")[2])
    purchase = await db.get_purchase_by_id(purchase_id, callback.from_user.id)

    if not purchase:
        await callback.answer("Покупка не найдена", show_alert=True)
        return

    if purchase.get("code"):
        await callback.message.answer(
            f'{t("code")} <b>Код подтверждения:</b>\n\n'
            f'<code>{purchase["code"]}</code>\n'
            f'{t("tag")} Номер: <code>{purchase["phone"]}</code>'
        )
        await callback.answer()
        return

    await callback.answer(f"{t('loading')} Получаю код...")
    session_string = purchase.get("session_string")
    if session_string:
        code = await fetch_code_from_telegram(session_string)
        if code:
            await db.update_account_code(purchase["account_id"], code)
            await callback.message.answer(
                f'{t("code")} <b>Код подтверждения:</b>\n\n'
                f'<code>{code}</code>\n'
                f'{t("tag")} Номер: <code>{purchase["phone"]}</code>'
            )
            return

    await callback.message.answer(
        f'{t("info")} Код пока не получен. Попробуйте позже или @VestSupport'
    )
    await callback.answer()


# ==================== ПОПОЛНЕНИЕ БАЛАНСА ====================
@dp.callback_query(F.data == "top_up")
async def top_up(callback: CallbackQuery):
    await callback.message.edit_text(
        f'{t("wallet")} <b>Пополнение баланса</b>\n\n{t("info")} Выберите способ:',
        reply_markup=topup_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "topup_crypto")
async def topup_crypto(callback: CallbackQuery):
    text = (
        f'{t("cryptobot")} <b>Пополнение через @CryptoBot</b>\n\n'
        f'Используйте команду:\n'
        f'<code>/topup_usdt сумма</code> или <code>/topup_ton сумма</code>\n\n'
        f'{t("info")} Будет создан счёт в Crypto Bot'
    )
    await callback.message.edit_text(text, reply_markup=back_to_profile_kb())
    await callback.answer()


@dp.message(Command("topup_usdt"))
async def cmd_topup_usdt(message: Message):
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        return

    try:
        amount = Decimal(message.text.split()[1])
    except:
        await message.answer("Использование: /topup_usdt сумма")
        return

    invoice = await crypto_pay.create_invoice(amount, "USDT", f"Пополнение баланса {message.from_user.id}")
    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), message.from_user.id, amount, "USDT", is_topup=True
        )
        await message.answer(
            f'{t("cryptobot")} <b>Счёт создан!</b>\n\n'
            f'<a href="{invoice.get("pay_url", invoice.get("bot_invoice_url", ""))}">Нажмите для оплаты</a>\n'
            f'Сумма: {amount} USDT\n\n'
            f'{t("loading")} Баланс пополнится автоматически после оплаты.'
        )
    else:
        await message.answer("Ошибка создания счёта")


@dp.message(Command("topup_ton"))
async def cmd_topup_ton(message: Message):
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        return

    try:
        amount = Decimal(message.text.split()[1])
    except:
        await message.answer("Использование: /topup_ton сумма")
        return

    invoice = await crypto_pay.create_invoice(amount, "TON", f"Пополнение баланса {message.from_user.id}")
    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), message.from_user.id, amount, "TON", is_topup=True
        )
        await message.answer(
            f'{t("cryptobot")} <b>Счёт создан!</b>\n\n'
            f'<a href="{invoice.get("pay_url", invoice.get("bot_invoice_url", ""))}">Нажмите для оплаты</a>\n'
            f'Сумма: {amount} TON\n\n'
            f'{t("loading")} Баланс пополнится автоматически после оплаты.'
        )
    else:
        await message.answer("Ошибка создания счёта")


@dp.callback_query(F.data == "topup_yoomoney")
async def topup_yoomoney(callback: CallbackQuery):
    text = (
        f'{t("money")} <b>Пополнение через YooMoney</b>\n\n'
        f'Переведите нужную сумму на кошелёк:\n'
        f'<code>{YOOMONEY_WALLET}</code>\n\n'
        f'{t("info")} После перевода отправьте чек в @VestSupport'
    )
    await callback.message.edit_text(text, reply_markup=back_to_profile_kb())
    await callback.answer()


# ==================== КУПИТЬ АККАУНТ ====================
@dp.callback_query(F.data == "buy_account")
async def buy_account(callback: CallbackQuery):
    await callback.message.edit_text(
        f'{t("box")} <b>Купить аккаунт</b>\n\n{t("tag")} Выберите тип:',
        reply_markup=account_type_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("acc_type_"))
async def acc_type_handler(callback: CallbackQuery):
    acc_type = callback.data.split("_")[2]
    await callback.message.edit_text(
        f'{t("box")} <b>{ACCOUNT_TYPES[acc_type]}</b>\n\n{t("info")} Выберите страну:',
        reply_markup=countries_kb(acc_type, 0)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page_"))
async def countries_page(callback: CallbackQuery):
    _, acc_type, page = callback.data.split("_")
    await callback.message.edit_text(
        f'{t("box")} <b>{ACCOUNT_TYPES[acc_type]}</b>\n\n{t("info")} Выберите страну:',
        reply_markup=countries_kb(acc_type, int(page))
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("country_"))
async def country_handler(callback: CallbackQuery):
    _, acc_type, country = callback.data.split("_")

    price = await db.get_price(acc_type, country) or {"price_rub": 100, "price_usdt": 1.2, "price_ton": 1.2}
    account = await db.get_available_account(acc_type, country)

    if not account:
        await callback.message.edit_text(
            f'{t("box")} <b>{ACCOUNT_TYPES[acc_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
            f'{t("cross")} <b>Нет в наличии</b>',
            reply_markup=countries_kb(acc_type, 0)
        )
        await callback.answer("Нет в наличии", show_alert=True)
        return

    text = (
        f'{t("box")} <b>{ACCOUNT_TYPES[acc_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
        f'{t("money")} <b>Цена:</b>\n'
        f'• {price["price_rub"]} ₽\n'
        f'• {price["price_usdt"]} USDT\n'
        f'• {price["price_ton"]} TON\n\n'
        f'Выберите способ оплаты:'
    )
    await callback.message.edit_text(text, reply_markup=payment_methods_kb(acc_type, country))
    await callback.answer()


# ==================== ОПЛАТА РУБЛЯМИ ====================
@dp.callback_query(F.data.startswith("pay_rub_"))
async def pay_rub(callback: CallbackQuery):
    _, _, acc_type, country = callback.data.split("_")
    price = await db.get_price(acc_type, country) or {"price_rub": 100}
    user = await db.get_user(callback.from_user.id)

    if user["balance"] < Decimal(str(price["price_rub"])):
        await callback.answer(f"Недостаточно средств. Баланс: {user['balance']} ₽", show_alert=True)
        return

    account = await db.get_available_account(acc_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    await db.deduct_balance(callback.from_user.id, Decimal(str(price["price_rub"])))
    await db.mark_account_sold(account["id"], callback.from_user.id)
    purchase_id = await db.add_purchase(
        callback.from_user.id, account["id"],
        Decimal(str(price["price_rub"])), "RUB"
    )

    text = (
        f'{t("celebrate")} <b>Покупка успешна!</b>\n\n'
        f'{t("tag")} <b>Номер:</b> <code>{account["phone"]}</code>\n'
        f'{t("money")} <b>Списано:</b> {price["price_rub"]} ₽\n'
        f'{t("calendar")} <b>Дата:</b> {format_date(msk_time())}'
    )
    await callback.message.edit_text(text, reply_markup=get_code_kb(purchase_id))
    await callback.answer("Покупка успешна!", show_alert=True)


# ==================== ОПЛАТА USDT ====================
@dp.callback_query(F.data.startswith("pay_usdt_"))
async def pay_usdt(callback: CallbackQuery):
    _, _, acc_type, country = callback.data.split("_")
    price = await db.get_price(acc_type, country) or {"price_usdt": 1.2}

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    account = await db.get_available_account(acc_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        Decimal(str(price["price_usdt"])), "USDT",
        f"Покупка {ACCOUNT_TYPES[acc_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), callback.from_user.id,
            Decimal(str(price["price_usdt"])), "USDT", acc_type, country
        )
        text = (
            f'{t("cryptobot")} <b>Оплата USDT</b>\n\n'
            f'Сумма: {price["price_usdt"]} USDT\n\n'
            f'<a href="{invoice.get("pay_url", invoice.get("bot_invoice_url", ""))}">Нажмите для оплаты</a>\n\n'
            f'{t("loading")} Ожидание оплаты...'
        )
        await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


# ==================== ОПЛАТА TON ====================
@dp.callback_query(F.data.startswith("pay_ton_"))
async def pay_ton(callback: CallbackQuery):
    _, _, acc_type, country = callback.data.split("_")
    price = await db.get_price(acc_type, country) or {"price_ton": 1.2}

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    account = await db.get_available_account(acc_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        Decimal(str(price["price_ton"])), "TON",
        f"Покупка {ACCOUNT_TYPES[acc_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), callback.from_user.id,
            Decimal(str(price["price_ton"])), "TON", acc_type, country
        )
        text = (
            f'{t("cryptobot")} <b>Оплата TON</b>\n\n'
            f'Сумма: {price["price_ton"]} TON\n\n'
            f'<a href="{invoice.get("pay_url", invoice.get("bot_invoice_url", ""))}">Нажмите для оплаты</a>\n\n'
            f'{t("loading")} Ожидание оплаты...'
        )
        await callback.message.edit_text(text, reply_markup=back_to_main_kb())
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


# ==================== ПРОВЕРКА CRYPTO ПЛАТЕЖЕЙ ====================
async def check_crypto_payments():
    while True:
        await asyncio.sleep(10)
        if not crypto_pay:
            continue
        try:
            pending = await db.get_pending_crypto_payments()
            for payment in pending:
                invoice = await crypto_pay.get_invoice(int(payment["invoice_id"]))
                if invoice and invoice.get("status") == "paid":
                    await db.update_crypto_payment(payment["invoice_id"], "paid")

                    if payment["is_topup"]:
                        await db.add_balance(payment["user_id"], payment["amount"])
                        try:
                            await bot.send_message(
                                payment["user_id"],
                                f'{t("wallet")} <b>Баланс пополнен!</b>\n\n'
                                f'+{payment["amount"]} {payment["currency"]}'
                            )
                        except:
                            pass
                    elif payment["account_type"] and payment["country"]:
                        account = await db.get_available_account(
                            payment["account_type"], payment["country"]
                        )
                        if account:
                            await db.mark_account_sold(account["id"], payment["user_id"])
                            purchase_id = await db.add_purchase(
                                payment["user_id"], account["id"],
                                payment["amount"], payment["currency"]
                            )
                            try:
                                await bot.send_message(
                                    payment["user_id"],
                                    f'{t("celebrate")} <b>Покупка успешна!</b>\n\n'
                                    f'{t("tag")} <b>Номер:</b> <code>{account["phone"]}</code>\n'
                                    f'{t("money")} <b>Оплачено:</b> {payment["amount"]} {payment["currency"]}\n'
                                    f'{t("calendar")} <b>Дата:</b> {format_date(msk_time())}',
                                    reply_markup=get_code_kb(purchase_id)
                                )
                            except:
                                pass
        except Exception as e:
            logger.error(f"Crypto payment check error: {e}")


# ==================== АДМИН ПАНЕЛЬ ====================
@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        f'{t("settings")} <b>Админ панель</b>',
        reply_markup=admin_panel_kb()
    )


@dp.callback_query(F.data == "admin_stats", F.from_user.id.in_(ADMIN_IDS))
async def admin_stats(callback: CallbackQuery):
    stats = await db.get_stats()
    text = (
        f'{t("stats")} <b>Статистика</b>\n\n'
        f'{t("profile")} Пользователей: {stats["total_users"]}\n'
        f'{t("box")} Аккаунтов всего: {stats["total_accounts"]}\n'
        f'{t("check")} Продано: {stats["sold_accounts"]}\n'
        f'{t("tag")} Доступно: {stats["available"]}'
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_kb())
    await callback.answer()


@dp.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f'{t("megaphone")} <b>Рассылка</b>\n\nОтправьте сообщение для рассылки:',
        reply_markup=back_to_main_kb()
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@dp.message(AdminStates.waiting_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast(message: Message, state: FSMContext):
    users = await db.get_all_users()
    sent = 0
    for user_id in users:
        try:
            await message.copy_to(user_id)
            sent += 1
        except:
            pass
        await asyncio.sleep(0.05)

    await message.answer(
        f'{t("check")} Рассылка завершена!\nОтправлено: {sent}/{len(users)}',
        reply_markup=admin_panel_kb()
    )
    await state.clear()


@dp.callback_query(F.data == "admin_give_balance", F.from_user.id.in_(ADMIN_IDS))
async def admin_give_balance(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f'{t("money_send")} <b>Выдать баланс</b>\n\nОтправьте ID пользователя:',
        reply_markup=back_to_main_kb()
    )
    await state.set_state(AdminStates.waiting_balance_user)
    await callback.answer()


@dp.message(AdminStates.waiting_balance_user, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_user(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        user = await db.get_user(user_id)
        if not user:
            await message.answer(f'{t("cross")} Пользователь не найден')
            return
        await state.update_data(balance_user=user_id)
        await message.answer(f"Отправьте сумму для пользователя {user_id}:")
        await state.set_state(AdminStates.waiting_balance_amount)
    except ValueError:
        await message.answer("Неверный ID")


@dp.message(AdminStates.waiting_balance_amount, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_amount(message: Message, state: FSMContext):
    try:
        amount = Decimal(message.text.strip())
        data = await state.get_data()
        user_id = data["balance_user"]
        await db.add_balance(user_id, amount)
        await message.answer(
            f'{t("check")} Баланс пользователя {user_id} пополнен на {amount} ₽',
            reply_markup=admin_panel_kb()
        )
        await state.clear()
    except:
        await message.answer("Неверная сумма")


@dp.callback_query(F.data == "admin_add_account", F.from_user.id.in_(ADMIN_IDS))
async def admin_add_account(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f'{t("add_text")} <b>Добавить аккаунт</b>\n\nВыберите тип:',
        reply_markup=add_account_type_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_type_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_type(callback: CallbackQuery, state: FSMContext):
    acc_type = callback.data.split("_")[2]
    await state.update_data(add_acc_type=acc_type)

    countries = list(COUNTRY_NAMES.keys())[:8]
    keyboard = []
    for country in countries:
        keyboard.append([InlineKeyboardButton(
            text=COUNTRY_NAMES[country],
            callback_data=f"addacc_country_{country}",
            icon_custom_emoji_id=icon(country)
        )])
    keyboard.append([InlineKeyboardButton(
        text="Назад", callback_data="admin_add_account", icon_custom_emoji_id=icon("down")
    )])

    await callback.message.edit_text(
        f'{t("add_text")} <b>Тип: {ACCOUNT_TYPES[acc_type]}</b>\n\nВыберите страну:',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_country_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_country(callback: CallbackQuery, state: FSMContext):
    country = callback.data.split("_")[2]
    await state.update_data(add_acc_country=country)
    await callback.message.edit_text(
        f'{t("add_text")} <b>Страна: {COUNTRY_NAMES[country]}</b>\n\n'
        f'Отправьте номер в формате +79001234567:',
        reply_markup=back_to_main_kb()
    )
    await state.set_state(AdminStates.waiting_add_account_phone)
    await callback.answer()


@dp.message(AdminStates.waiting_add_account_phone, F.from_user.id.in_(ADMIN_IDS))
async def addacc_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("Номер должен начинаться с +")
        return

    await state.update_data(add_acc_phone=phone)

    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        sent = await client.send_code_request(phone)
        await state.update_data(
            add_acc_client=client,
            add_acc_phone_hash=sent.phone_code_hash
        )
        await message.answer(f'{t("code")} Отправьте код с номера {phone}:')
        await state.set_state(AdminStates.waiting_add_account_code)
    except Exception as e:
        await message.answer(f'{t("cross")} Ошибка: {e}')
        await state.clear()


@dp.message(AdminStates.waiting_add_account_code, F.from_user.id.in_(ADMIN_IDS))
async def addacc_code_handler(message: Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    client = data.get("add_acc_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        await client.sign_in(
            phone=data["add_acc_phone"],
            code=code,
            phone_code_hash=data["add_acc_phone_hash"]
        )
        session_string = client.session.save()
        await client.disconnect()

        acc_type = data["add_acc_type"]
        country = data["add_acc_country"]
        price = await db.get_price(acc_type, country) or {"price_rub": 100, "price_usdt": 1.2, "price_ton": 1.2}

        await db.add_account(
            acc_type, country, data["add_acc_phone"],
            session_string=session_string,
            price_rub=price["price_rub"],
            price_usdt=price["price_usdt"],
            price_ton=price["price_ton"]
        )

        await message.answer(
            f'{t("check")} Аккаунт {data["add_acc_phone"]} добавлен!\n'
            f'Тип: {ACCOUNT_TYPES[acc_type]}\nСтрана: {COUNTRY_NAMES[country]}',
            reply_markup=admin_panel_kb()
        )
        await state.clear()

    except SessionPasswordNeededError:
        await state.update_data(add_acc_client=client)
        await message.answer("Требуется 2FA пароль. Отправьте пароль:")
        await state.set_state(AdminStates.waiting_add_account_password)
    except Exception as e:
        await message.answer(f'{t("cross")} Ошибка: {e}')
        if client:
            await client.disconnect()
        await state.clear()


@dp.message(AdminStates.waiting_add_account_password, F.from_user.id.in_(ADMIN_IDS))
async def addacc_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client = data.get("add_acc_client")

    if not client:
        await message.answer("Сессия истекла")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await client.disconnect()

        acc_type = data["add_acc_type"]
        country = data["add_acc_country"]
        price = await db.get_price(acc_type, country) or {"price_rub": 100, "price_usdt": 1.2, "price_ton": 1.2}

        await db.add_account(
            acc_type, country, data["add_acc_phone"],
            session_string=session_string,
            price_rub=price["price_rub"],
            price_usdt=price["price_usdt"],
            price_ton=price["price_ton"]
        )

        await message.answer(
            f'{t("check")} Аккаунт {data["add_acc_phone"]} добавлен!',
            reply_markup=admin_panel_kb()
        )
        await state.clear()
    except Exception as e:
        await message.answer(f'{t("cross")} Ошибка: {e}')
        await client.disconnect()
        await state.clear()


@dp.callback_query(F.data == "admin_change_price", F.from_user.id.in_(ADMIN_IDS))
async def admin_change_price(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        f'{t("pencil")} <b>Изменение цен</b>\n\nВыберите тип:',
        reply_markup=change_price_type_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_type_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_type(callback: CallbackQuery, state: FSMContext):
    acc_type = callback.data.split("_")[2]
    await state.update_data(chprice_type=acc_type)
    await callback.message.edit_text(
        f'{t("pencil")} <b>Тип: {ACCOUNT_TYPES[acc_type]}</b>\n\nОтправьте цену в рублях:'
    )
    await state.set_state(AdminStates.waiting_change_price_rub)
    await callback.answer()


@dp.message(AdminStates.waiting_change_price_rub, F.from_user.id.in_(ADMIN_IDS))
async def chprice_rub(message: Message, state: FSMContext):
    try:
        price_rub = Decimal(message.text.strip())
        await state.update_data(chprice_rub=price_rub)
        await message.answer("Отправьте цену в USDT:")
        await state.set_state(AdminStates.waiting_change_price_usdt)
    except:
        await message.answer("Неверное число")


@dp.message(AdminStates.waiting_change_price_usdt, F.from_user.id.in_(ADMIN_IDS))
async def chprice_usdt(message: Message, state: FSMContext):
    try:
        price_usdt = Decimal(message.text.strip())
        await state.update_data(chprice_usdt=price_usdt)
        await message.answer("Отправьте цену в TON:")
        await state.set_state(AdminStates.waiting_change_price_ton)
    except:
        await message.answer("Неверное число")


@dp.message(AdminStates.waiting_change_price_ton, F.from_user.id.in_(ADMIN_IDS))
async def chprice_ton(message: Message, state: FSMContext):
    try:
        price_ton = Decimal(message.text.strip())
        data = await state.get_data()

        for country in COUNTRY_NAMES.keys():
            await db.set_price(data["chprice_type"], country, data["chprice_rub"], data["chprice_usdt"], price_ton)

        await message.answer(
            f'{t("check")} Цены для {ACCOUNT_TYPES[data["chprice_type"]]} обновлены!\n\n'
            f'₽: {data["chprice_rub"]}\nUSDT: {data["chprice_usdt"]}\nTON: {price_ton}',
            reply_markup=admin_panel_kb()
        )
        await state.clear()
    except:
        await message.answer("Неверное число")


# ==================== ЗАПУСК ====================
async def main():
    await db.connect()
    await db.init_tables()
    await telethon_client.connect()

    asyncio.create_task(check_crypto_payments())

    logger.info("Бот Vest Traff Accs запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
