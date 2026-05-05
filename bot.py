import asyncio
import logging
import re
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import DeleteWebhook
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

# Внутренние курсы (не показываются пользователям)
USDT_RATE = Decimal("90")
TON_RATE = Decimal("95")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
EMOJI = {
    # Основные
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
    # Страны
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
    "usa": "США",
    "russia": "Россия",
    "ukraine": "Украина",
    "belarus": "Беларусь",
    "kazakhstan": "Казахстан",
    "uzbekistan": "Узбекистан",
    "china": "Китай",
    "myanmar": "Мьянма",
    "india": "Индия",
    "bangladesh": "Бангладеш",
    "pakistan": "Пакистан",
    "nigeria": "Нигерия",
    "spain": "Испания",
    "france": "Франция",
    "uk": "Великобритания",
    "romania": "Румыния",
    "japan": "Япония",
    "egypt": "Египет",
    "sweden": "Швеция",
    "tajikistan": "Таджикистан",
    "brazil": "Бразилия",
    "argentina": "Аргентина",
    "canada": "Канада",
}

ACCOUNT_TYPES = {
    "newreg": "Новореги",
    "leaved": "С отлёгой",
    "warmed": "Прогретые",
}


def msk_time() -> datetime:
    """Возвращает текущее московское время"""
    return datetime.now(timezone(timedelta(hours=3)))


def format_date(dt: datetime) -> str:
    """Форматирует дату в московском времени"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%d.%m.%Y %H:%M")


def calc_usdt(rub: Decimal) -> Decimal:
    """Пересчитывает рубли в USDT"""
    return (rub / USDT_RATE).quantize(Decimal("0.01"))


def calc_ton(rub: Decimal) -> Decimal:
    """Пересчитывает рубли в TON"""
    return (rub / TON_RATE).quantize(Decimal("0.01"))


# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Подключается к базе данных"""
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)

    async def init_tables(self):
        """Создаёт таблицы, если их нет"""
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
                    purchase_date TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS prices (
                    id SERIAL PRIMARY KEY,
                    account_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    price_rub DECIMAL DEFAULT 0,
                    UNIQUE(account_type, country)
                );

                CREATE TABLE IF NOT EXISTS crypto_payments (
                    id SERIAL PRIMARY KEY,
                    invoice_id TEXT UNIQUE,
                    user_id BIGINT,
                    amount DECIMAL,
                    currency TEXT,
                    status TEXT DEFAULT 'pending',
                    account_type TEXT DEFAULT '',
                    country TEXT DEFAULT '',
                    is_topup BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

    # ==================== ПОЛЬЗОВАТЕЛИ ====================
    async def get_or_create_user(self, user_id: int, username: str = None) -> Dict[str, Any]:
        """Получает или создаёт пользователя"""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                    user_id, username
                )
                return {
                    "user_id": user_id,
                    "username": username,
                    "balance": 0,
                    "purchases_count": 0
                }
            return dict(user)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает пользователя по ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            return dict(row) if row else None

    async def add_balance(self, user_id: int, amount: Decimal) -> None:
        """Пополняет баланс пользователя"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )

    async def deduct_balance(self, user_id: int, amount: Decimal) -> None:
        """Списывает средства с баланса"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                amount, user_id
            )

    # ==================== АККАУНТЫ ====================
    async def get_available_account(self, account_type: str, country: str) -> Optional[Dict[str, Any]]:
        """Получает первый доступный аккаунт"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM accounts 
                   WHERE account_type = $1 AND country = $2 AND is_sold = FALSE 
                   LIMIT 1""",
                account_type, country
            )

    async def mark_account_sold(self, account_id: int, user_id: int) -> None:
        """Помечает аккаунт как проданный"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE accounts SET is_sold = TRUE, sold_to = $1, sold_at = NOW() 
                   WHERE id = $2""",
                user_id, account_id
            )

    async def add_account(
        self,
        account_type: str,
        country: str,
        phone: str,
        session_string: str = None,
        password: str = None,
        price_rub: Decimal = Decimal("0")
    ) -> int:
        """Добавляет новый аккаунт"""
        pu = calc_usdt(price_rub)
        pt = calc_ton(price_rub)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO accounts 
                   (account_type, country, phone, session_string, password, 
                    price_rub, price_usdt, price_ton)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
                   RETURNING id""",
                account_type, country, phone, session_string, password,
                price_rub, pu, pt
            )

    async def get_account_by_id(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Получает аккаунт по ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM accounts WHERE id = $1", account_id)
            return dict(row) if row else None

    async def update_account_code(self, account_id: int, code: str) -> None:
        """Обновляет код подтверждения аккаунта"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE accounts SET code = $1 WHERE id = $2",
                code, account_id
            )

    # ==================== ПОКУПКИ ====================
    async def add_purchase(
        self, user_id: int, account_id: int, price: Decimal, currency: str
    ) -> int:
        """Добавляет покупку"""
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

    async def get_user_purchases(self, user_id: int) -> list:
        """Получает все покупки пользователя"""
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

    async def get_purchase_by_id(
        self, purchase_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Получает покупку по ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT p.*, a.phone, a.code, a.session_string, a.account_type, a.country
                   FROM purchases p 
                   JOIN accounts a ON p.account_id = a.id 
                   WHERE p.id = $1 AND p.user_id = $2""",
                purchase_id, user_id
            )
            return dict(row) if row else None

    # ==================== ЦЕНЫ ====================
    async def set_price(
        self,
        account_type: str,
        country: str,
        price_rub: Decimal
    ) -> None:
        """Устанавливает цену для типа и страны (USDT и TON считаются автоматически)"""
        pu = calc_usdt(price_rub)
        pt = calc_ton(price_rub)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO prices (account_type, country, price_rub)
                   VALUES ($1, $2, $3)
                   ON CONFLICT (account_type, country) 
                   DO UPDATE SET price_rub = $3""",
                account_type, country, price_rub
            )
            # Обновляем цены у непроданных аккаунтов
            await conn.execute(
                """UPDATE accounts 
                   SET price_rub = $1, price_usdt = $2, price_ton = $3 
                   WHERE account_type = $4 AND country = $5 AND is_sold = FALSE""",
                price_rub, pu, pt, account_type, country
            )

    async def get_price(
        self, account_type: str, country: str
    ) -> Optional[Dict[str, Any]]:
        """Получает цену для типа и страны"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT price_rub FROM prices WHERE account_type = $1 AND country = $2",
                account_type, country
            )
            if row:
                pr = Decimal(str(row["price_rub"]))
                return {
                    "price_rub": pr,
                    "price_usdt": calc_usdt(pr),
                    "price_ton": calc_ton(pr)
                }
            # Возвращаем значения по умолчанию
            return {
                "price_rub": Decimal("100"),
                "price_usdt": calc_usdt(Decimal("100")),
                "price_ton": calc_ton(Decimal("100"))
            }

    # ==================== СТАТИСТИКА ====================
    async def get_all_users(self) -> list:
        """Получает ID всех пользователей"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row["user_id"] for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Получает общую статистику"""
        async with self.pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_accounts = await conn.fetchval("SELECT COUNT(*) FROM accounts")
            sold_accounts = await conn.fetchval(
                "SELECT COUNT(*) FROM accounts WHERE is_sold = TRUE"
            )
            total_purchases = await conn.fetchval("SELECT COUNT(*) FROM purchases")
            return {
                "total_users": total_users,
                "total_accounts": total_accounts,
                "sold_accounts": sold_accounts,
                "available": total_accounts - sold_accounts,
                "total_purchases": total_purchases
            }

    # ==================== CRYPTO PAY ====================
    async def add_crypto_payment(
        self,
        invoice_id: str,
        user_id: int,
        amount: Decimal,
        currency: str,
        account_type: str = "",
        country: str = "",
        is_topup: bool = False
    ) -> None:
        """Добавляет крипто-платёж"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO crypto_payments 
                   (invoice_id, user_id, amount, currency, account_type, country, is_topup)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                invoice_id, user_id, amount, currency, account_type, country, is_topup
            )

    async def update_crypto_payment(
        self, invoice_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        """Обновляет статус крипто-платежа"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE crypto_payments SET status = $1 WHERE invoice_id = $2 RETURNING *",
                status, invoice_id
            )

    async def get_pending_crypto_payments(self) -> list:
        """Получает все незавершённые крипто-платежи"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM crypto_payments WHERE status = 'pending'"
            )
            return [dict(row) for row in rows]

    async def get_expired_crypto_payments(self) -> list:
        """Получает просроченные крипто-платежи (старше 10 минут)"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM crypto_payments 
                   WHERE status = 'pending' 
                   AND created_at < NOW() - INTERVAL '10 minutes'"""
            )
            return [dict(row) for row in rows]


db = Database()


# ==================== FSM СОСТОЯНИЯ ====================
class AdminStates(StatesGroup):
    """Состояния для админ-панели"""
    waiting_broadcast = State()
    waiting_balance_user = State()
    waiting_balance_amount = State()
    waiting_add_account_phone = State()
    waiting_add_account_code = State()
    waiting_add_account_password = State()
    waiting_change_price_type = State()
    waiting_change_price_country = State()
    waiting_change_price_rub = State()


class TopupStates(StatesGroup):
    """Состояния для пополнения баланса"""
    waiting_amount_usdt = State()
    waiting_amount_ton = State()
    waiting_amount_ym = State()


# ==================== CRYPTO PAY API ====================
class CryptoPayAPI:
    """API для работы с Crypto Pay"""
    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        self.token = token

    async def create_invoice(
        self, amount: Decimal, currency: str = "USDT", description: str = ""
    ) -> Optional[Dict]:
        """Создаёт счёт на оплату"""
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
        """Получает информацию о счёте"""
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


# ==================== YOOMONEY QUICKPAY (без токена) ====================
def create_yoomoney_link(amount: Decimal, label: str, comment: str = "") -> str:
    """Создаёт ссылку на оплату через YooMoney QuickPay форму"""
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": comment or "Оплата",
        "paymentType": "AC",
        "sum": str(amount),
        "label": label,
    }
    return f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(params)}"


# ==================== TElethon КЛИЕНТ ====================
telethon_client = TelegramClient(StringSession(), API_ID, API_HASH)


async def fetch_code_from_telegram(session_string: str) -> Optional[str]:
    """Получает код подтверждения из аккаунта Telegram"""
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return None

        # Получаем последние диалоги
        dialogs = await client.get_dialogs(limit=10)
        for dialog in dialogs:
            # Получаем сообщения из диалога
            messages = await client.get_messages(dialog, limit=20)
            for msg in messages:
                if msg.message:
                    # Ищем 5-6 значный код
                    code_match = re.search(r'\b(\d{5,6})\b', msg.message)
                    if code_match:
                        code = code_match.group(1)
                        # Проверяем что это не год (20xx)
                        if not code.startswith("20"):
                            await client.disconnect()
                            return code
        await client.disconnect()
    except Exception as e:
        logger.error(f"Ошибка получения кода: {e}")
    return None


# ==================== БОТ ====================
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ==================== КЛАВИАТУРЫ ====================
def main_menu_keyboard() -> types.InlineKeyboardMarkup:
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Купить аккаунт",
            callback_data="buy_account",
            style="primary",
            icon_custom_emoji_id=EMOJI["box"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Профиль",
            callback_data="profile",
            style="default",
            icon_custom_emoji_id=EMOJI["profile"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Поддержка",
            callback_data="support",
            style="default",
            icon_custom_emoji_id=EMOJI["info"]
        ),
        types.InlineKeyboardButton(
            text="Проекты",
            callback_data="projects",
            style="default",
            icon_custom_emoji_id=EMOJI["link"]
        )
    )
    return builder.as_markup()


def back_to_main_keyboard() -> types.InlineKeyboardMarkup:
    """Кнопка назад в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад в меню",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def back_to_profile_keyboard() -> types.InlineKeyboardMarkup:
    """Кнопка назад в профиль"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def profile_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура профиля"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Мои покупки",
            callback_data="my_purchases",
            style="default",
            icon_custom_emoji_id=EMOJI["box"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Пополнить баланс",
            callback_data="top_up",
            style="success",
            icon_custom_emoji_id=EMOJI["wallet"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def account_type_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура выбора типа аккаунта"""
    builder = InlineKeyboardBuilder()
    for key, name in ACCOUNT_TYPES.items():
        builder.row(
            types.InlineKeyboardButton(
                text=name,
                callback_data=f"acc_type_{key}",
                style="default",
                icon_custom_emoji_id=EMOJI["tag"]
            )
        )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def countries_keyboard(
    account_type: str, page: int = 0, per_page: int = 8
) -> types.InlineKeyboardMarkup:
    """Клавиатура выбора страны с пагинацией"""
    builder = InlineKeyboardBuilder()
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    for country in page_countries:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"country_{account_type}_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="◁",
                callback_data=f"page_{account_type}_{page - 1}",
                icon_custom_emoji_id=EMOJI["down"]
            )
        )
    nav_buttons.append(
        types.InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="ignore"
        )
    )
    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="▷",
                callback_data=f"page_{account_type}_{page + 1}",
                icon_custom_emoji_id=EMOJI["send"]
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="buy_account",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


async def payment_methods_keyboard(
    account_type: str, country: str
) -> types.InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты"""
    price = await db.get_price(account_type, country)

    builder = InlineKeyboardBuilder()

    # Кнопка оплаты балансом - primary (синяя)
    builder.row(
        types.InlineKeyboardButton(
            text=f"Оплатить балансом ({price['price_rub']} ₽)",
            callback_data=f"pay_balance_{account_type}_{country}",
            style="primary",
            icon_custom_emoji_id=EMOJI["wallet"]
        )
    )

    # USDT - default
    builder.row(
        types.InlineKeyboardButton(
            text=f"USDT ({price['price_usdt']} USDT)",
            callback_data=f"pay_usdt_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )

    # TON - default
    builder.row(
        types.InlineKeyboardButton(
            text=f"TON ({price['price_ton']} TON)",
            callback_data=f"pay_ton_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )

    # YooMoney - default
    builder.row(
        types.InlineKeyboardButton(
            text=f"YooMoney ({price['price_rub']} ₽)",
            callback_data=f"pay_ym_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["money"]
        )
    )

    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data=f"acc_type_{account_type}",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def get_code_keyboard(purchase_id: int) -> types.InlineKeyboardMarkup:
    """Клавиатура для получения кода"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Получить код",
            callback_data=f"get_code_{purchase_id}",
            style="success",
            icon_custom_emoji_id=EMOJI["code"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="my_purchases",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def topup_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура пополнения баланса"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Crypto Bot (USDT)",
            callback_data="topup_crypto_usdt",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Crypto Bot (TON)",
            callback_data="topup_crypto_ton",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="YooMoney (Рубли)",
            callback_data="topup_yoomoney",
            style="default",
            icon_custom_emoji_id=EMOJI["money"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def admin_panel_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Статистика",
            callback_data="admin_stats",
            style="default",
            icon_custom_emoji_id=EMOJI["stats"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Рассылка",
            callback_data="admin_broadcast",
            style="primary",
            icon_custom_emoji_id=EMOJI["megaphone"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Выдать баланс",
            callback_data="admin_give_balance",
            style="success",
            icon_custom_emoji_id=EMOJI["money_send"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Добавить аккаунт",
            callback_data="admin_add_account",
            style="default",
            icon_custom_emoji_id=EMOJI["add_text"]
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="Изменить цены",
            callback_data="admin_change_price",
            style="default",
            icon_custom_emoji_id=EMOJI["pencil"]
        )
    )
    return builder.as_markup()


def add_account_type_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура выбора типа при добавлении аккаунта"""
    builder = InlineKeyboardBuilder()
    for key, name in ACCOUNT_TYPES.items():
        builder.row(
            types.InlineKeyboardButton(
                text=name,
                callback_data=f"addacc_type_{key}",
                style="default",
                icon_custom_emoji_id=EMOJI["tag"]
            )
        )
    return builder.as_markup()


def change_price_type_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура выбора типа при изменении цен"""
    builder = InlineKeyboardBuilder()
    for key, name in ACCOUNT_TYPES.items():
        builder.row(
            types.InlineKeyboardButton(
                text=name,
                callback_data=f"chprice_type_{key}",
                style="default",
                icon_custom_emoji_id=EMOJI["tag"]
            )
        )
    return builder.as_markup()


def countries_add_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура стран для добавления аккаунта"""
    builder = InlineKeyboardBuilder()
    for country in list(COUNTRY_NAMES.keys())[:8]:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"addacc_country_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="admin_add_account",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def countries_price_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура стран для изменения цен"""
    builder = InlineKeyboardBuilder()
    for country in list(COUNTRY_NAMES.keys())[:8]:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"chprice_country_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="admin_change_price",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


# ==================== ОБРАБОТЧИКИ: СТАРТ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    await db.get_or_create_user(message.from_user.id, message.from_user.username)

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> Добро пожаловать в Vest Traff Accs!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> Покупка аккаунтов Telegram с разных стран\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Выберите действие в меню:'
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    """Обработчик возврата в главное меню"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> Главное меню</b>\n\n'
        f'Выберите действие:'
    )
    await callback.message.edit_text(text, reply_markup=main_menu_keyboard())
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: ПРОЕКТЫ ====================
@dp.callback_query(F.data == "projects")
async def projects_callback(callback: types.CallbackQuery):
    """Обработчик раздела Проекты"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["link"]}">🔗</tg-emoji> Наши проекты:</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> <b>Телеграмм комбайны:</b>\n'
        f'• @VestTrafferBot\n'
        f'• @VestTraffer2bot\n'
        f'• @VestTraffer3bot\n\n'
        f'<tg-emoji emoji-id="{EMOJI["megaphone"]}">📣</tg-emoji> <b>Канал:</b> @VestTraffer'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: ПОДДЕРЖКА ====================
@dp.callback_query(F.data == "support")
async def support_callback(callback: types.CallbackQuery):
    """Обработчик раздела Поддержка"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Поддержка</b>\n\n'
        f'По всем вопросам обращайтесь:\n'
        f'@VestSupport'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def profile_callback(callback: types.CallbackQuery):
    """Обработчик профиля"""
    user = await db.get_or_create_user(
        callback.from_user.id, callback.from_user.username
    )

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> Профиль</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Юзернейм:</b> @{user.get("username") or "нет"}\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> <b>ID:</b> <code>{user["user_id"]}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> <b>Баланс:</b> {user["balance"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> <b>Количество покупок:</b> {user["purchases_count"]}'
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard())
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: МОИ ПОКУПКИ ====================
@dp.callback_query(F.data == "my_purchases")
async def my_purchases_callback(callback: types.CallbackQuery):
    """Обработчик списка покупок"""
    purchases = await db.get_user_purchases(callback.from_user.id)

    if not purchases:
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> Мои покупки</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> У вас пока нет покупок.'
        )
        await callback.message.edit_text(
            text, reply_markup=back_to_profile_keyboard()
        )
        await callback.answer()
        return

    text = f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> Мои покупки:</b>\n\n'
    builder = InlineKeyboardBuilder()

    for i, purchase in enumerate(purchases[:10], 1):
        date_str = format_date(purchase["purchase_date"])
        text += (
            f'{i}. <tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> <b>Дата:</b> {date_str}\n'
            f'   <tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Номер:</b> <code>{purchase["phone"]}</code>\n'
            f'   <tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> <b>Цена:</b> {purchase["price"]} {purchase["currency"]}\n\n'
        )
        builder.row(
            types.InlineKeyboardButton(
                text=f"Получить код #{purchase['id']}",
                callback_data=f"get_code_{purchase['id']}",
                style="success",
                icon_custom_emoji_id=EMOJI["code"]
            )
        )

    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: ПОЛУЧЕНИЕ КОДА ====================
@dp.callback_query(F.data.startswith("get_code_"))
async def get_code_callback(callback: types.CallbackQuery):
    """Обработчик получения кода подтверждения"""
    purchase_id = int(callback.data.split("_")[2])
    purchase = await db.get_purchase_by_id(purchase_id, callback.from_user.id)

    if not purchase:
        await callback.answer("Покупка не найдена", show_alert=True)
        return

    # Пытаемся получить свежий код через Telethon
    await callback.answer()
    status_msg = await callback.message.answer(
        f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> Ищу код подтверждения...'
    )

    session_string = purchase.get("session_string")
    if session_string:
        code = await fetch_code_from_telegram(session_string)
        if code:
            await db.update_account_code(purchase["account_id"], code)
            await status_msg.edit_text(
                f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> Код подтверждения:</b>\n\n'
                f'<code>{code}</code>\n\n'
                f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Номер:</b> <code>{purchase["phone"]}</code>'
            )
            return

    # Если есть сохранённый код
    if purchase.get("code"):
        await status_msg.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> Код подтверждения:</b>\n\n'
            f'<code>{purchase["code"]}</code>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Номер:</b> <code>{purchase["phone"]}</code>'
        )
        return

    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Код пока не получен. '
        f'Попробуйте позже или обратитесь в поддержку @VestSupport'
    )


# ==================== ОБРАБОТЧИКИ: ПОПОЛНЕНИЕ БАЛАНСА ====================
@dp.callback_query(F.data == "top_up")
async def top_up_callback(callback: types.CallbackQuery):
    """Обработчик пополнения баланса"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> Пополнение баланса</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Выберите способ пополнения:'
    )
    await callback.message.edit_text(text, reply_markup=topup_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "topup_crypto_usdt")
async def topup_crypto_usdt_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик пополнения USDT через кнопку"""
    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Пополнение USDT</b>\n\n'
        f'Отправьте сумму в USDT:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_usdt)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_usdt)
async def process_topup_usdt(message: types.Message, state: FSMContext):
    """Обработчик получения суммы USDT"""
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        await state.clear()
        return

    try:
        amount = Decimal(message.text.strip())
    except:
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    invoice = await crypto_pay.create_invoice(
        amount, "USDT", f"Пополнение баланса {message.from_user.id}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), message.from_user.id, amount, "USDT", is_topup=True
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Счёт USDT создан!</b>\n\n'
            f'Сумма: {amount} USDT\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> Баланс пополнится автоматически'
        )
        await message.answer(text, reply_markup=profile_keyboard())
    else:
        await message.answer("Ошибка создания счёта")
    await state.clear()


@dp.callback_query(F.data == "topup_crypto_ton")
async def topup_crypto_ton_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик пополнения TON через кнопку"""
    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Пополнение TON</b>\n\n'
        f'Отправьте сумму в TON:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ton)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_ton)
async def process_topup_ton(message: types.Message, state: FSMContext):
    """Обработчик получения суммы TON"""
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        await state.clear()
        return

    try:
        amount = Decimal(message.text.strip())
    except:
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    invoice = await crypto_pay.create_invoice(
        amount, "TON", f"Пополнение баланса {message.from_user.id}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), message.from_user.id, amount, "TON", is_topup=True
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Счёт TON создан!</b>\n\n'
            f'Сумма: {amount} TON\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> Баланс пополнится автоматически'
        )
        await message.answer(text, reply_markup=profile_keyboard())
    else:
        await message.answer("Ошибка создания счёта")
    await state.clear()


@dp.callback_query(F.data == "topup_yoomoney")
async def topup_yoomoney_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик пополнения YooMoney через кнопку"""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> Пополнение YooMoney</b>\n\n'
        f'Отправьте сумму в рублях:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ym)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_ym)
async def process_topup_ym(message: types.Message, state: FSMContext):
    """Обработчик получения суммы YooMoney"""
    try:
        amount = Decimal(message.text.strip())
    except:
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    label = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
    payment_link = create_yoomoney_link(
        amount, label, f"Пополнение баланса {message.from_user.id}"
    )

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> Пополнение YooMoney</b>\n\n'
        f'Сумма: {amount} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> После оплаты отправьте чек в @VestSupport\n'
        f'Баланс будет пополнен после проверки.'
    )
    await message.answer(text, reply_markup=profile_keyboard())
    await state.clear()


# ==================== ОБРАБОТЧИКИ: КУПИТЬ АККАУНТ ====================
@dp.callback_query(F.data == "buy_account")
async def buy_account_callback(callback: types.CallbackQuery):
    """Обработчик покупки аккаунта"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> Купить аккаунт</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> Выберите тип аккаунта:'
    )
    await callback.message.edit_text(text, reply_markup=account_type_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("acc_type_"))
async def account_type_callback(callback: types.CallbackQuery):
    """Обработчик выбора типа аккаунта"""
    account_type = callback.data.split("_")[2]

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Выберите страну:'
    )
    await callback.message.edit_text(
        text, reply_markup=countries_keyboard(account_type, 0)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page_"))
async def countries_page_callback(callback: types.CallbackQuery):
    """Обработчик пагинации стран"""
    parts = callback.data.split("_")
    account_type = parts[1]
    page = int(parts[2])

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Выберите страну:'
    )
    await callback.message.edit_text(
        text, reply_markup=countries_keyboard(account_type, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("country_"))
async def country_callback(callback: types.CallbackQuery):
    """Обработчик выбора страны"""
    parts = callback.data.split("_")
    account_type = parts[1]
    country = parts[2]

    # Получаем цену
    price = await db.get_price(account_type, country)

    # Проверяем наличие
    account = await db.get_available_account(account_type, country)

    if not account:
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
            f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> <b>Нет в наличии</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Попробуйте другую страну или тип аккаунта.'
        )
        await callback.message.edit_text(
            text, reply_markup=countries_keyboard(account_type, 0)
        )
        await callback.answer("Нет в наличии", show_alert=True)
        return

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> <b>Цены:</b>\n'
        f'• {price["price_rub"]} ₽\n'
        f'• {price["price_usdt"]} USDT\n'
        f'• {price["price_ton"]} TON\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> Выберите способ оплаты:'
    )

    await callback.message.edit_text(
        text, reply_markup=await payment_methods_keyboard(account_type, country)
    )
    await callback.answer()


# ==================== ОБРАБОТЧИКИ: ОПЛАТА БАЛАНСОМ ====================
@dp.callback_query(F.data.startswith("pay_balance_"))
async def pay_balance_callback(callback: types.CallbackQuery):
    """Обработчик оплаты балансом"""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    price = await db.get_price(account_type, country)
    user = await db.get_user(callback.from_user.id)

    if user["balance"] < price["price_rub"]:
        await callback.answer(
            f"Недостаточно средств. Баланс: {user['balance']} ₽, необходимо: {price['price_rub']} ₽",
            show_alert=True
        )
        return

    account = await db.get_available_account(account_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    # Списываем и выдаём
    await db.deduct_balance(callback.from_user.id, price["price_rub"])
    await db.mark_account_sold(account["id"], callback.from_user.id)
    purchase_id = await db.add_purchase(
        callback.from_user.id, account["id"],
        price["price_rub"], "RUB"
    )

    new_balance = user["balance"] - price["price_rub"]

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> Покупка успешна!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Номер:</b> <code>{account["phone"]}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> <b>Списано с баланса:</b> {price["price_rub"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> <b>Остаток:</b> {new_balance} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> <b>Дата:</b> {format_date(msk_time())}'
    )
    await callback.message.edit_text(
        text, reply_markup=get_code_keyboard(purchase_id)
    )
    await callback.answer("Покупка успешна!", show_alert=True)


# ==================== ОБРАБОТЧИКИ: ОПЛАТА USDT ====================
@dp.callback_query(F.data.startswith("pay_usdt_"))
async def pay_usdt_callback(callback: types.CallbackQuery):
    """Обработчик оплаты USDT"""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    price = await db.get_price(account_type, country)

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    account = await db.get_available_account(account_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        price["price_usdt"], "USDT",
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), callback.from_user.id,
            price["price_usdt"], "USDT", account_type, country
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Оплата USDT</b>\n\n'
            f'Сумма: {price["price_usdt"]} USDT\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> После оплаты аккаунт будет выдан автоматически.'
        )
        await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


# ==================== ОБРАБОТЧИКИ: ОПЛАТА TON ====================
@dp.callback_query(F.data.startswith("pay_ton_"))
async def pay_ton_callback(callback: types.CallbackQuery):
    """Обработчик оплаты TON"""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    price = await db.get_price(account_type, country)

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    account = await db.get_available_account(account_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        price["price_ton"], "TON",
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]), callback.from_user.id,
            price["price_ton"], "TON", account_type, country
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> Оплата TON</b>\n\n'
            f'Сумма: {price["price_ton"]} TON\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> После оплаты аккаунт будет выдан автоматически.'
        )
        await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


# ==================== ОБРАБОТЧИКИ: ОПЛАТА YOOMONEY ====================
@dp.callback_query(F.data.startswith("pay_ym_"))
async def pay_yoomoney_callback(callback: types.CallbackQuery):
    """Обработчик оплаты через YooMoney"""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    price = await db.get_price(account_type, country)
    account = await db.get_available_account(account_type, country)

    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    label = f"buy_{callback.from_user.id}_{uuid.uuid4().hex[:8]}"
    payment_link = create_yoomoney_link(
        price["price_rub"], label,
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> Оплата YooMoney</b>\n\n'
        f'Сумма к оплате: {price["price_rub"]} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'Тип: {ACCOUNT_TYPES[account_type]}\n'
        f'Страна: {COUNTRY_NAMES[country]}\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> После оплаты отправьте чек в @VestSupport\n'
        f'Аккаунт будет выдан после проверки платежа.'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


# ==================== ПРОВЕРКА CRYPTO ПЛАТЕЖЕЙ ====================
async def check_crypto_payments_loop():
    """Фоновый цикл проверки крипто-платежей (каждые 5 секунд)"""
    while True:
        await asyncio.sleep(5)
        if not crypto_pay:
            continue

        try:
            # Отменяем просроченные (старше 10 минут)
            expired = await db.get_expired_crypto_payments()
            for payment in expired:
                await db.update_crypto_payment(payment["invoice_id"], "expired")
                try:
                    await bot.send_message(
                        payment["user_id"],
                        f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
                        f'Время оплаты истекло. Счёт аннулирован.'
                    )
                except:
                    pass

            # Проверяем pending платежи
            pending = await db.get_pending_crypto_payments()
            for payment in pending:
                invoice = await crypto_pay.get_invoice(int(payment["invoice_id"]))

                if invoice and invoice.get("status") == "paid":
                    await db.update_crypto_payment(payment["invoice_id"], "paid")

                    if payment["is_topup"]:
                        # Пополнение баланса
                        await db.add_balance(payment["user_id"], payment["amount"])
                        try:
                            await bot.send_message(
                                payment["user_id"],
                                f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> Баланс пополнен!</b>\n\n'
                                f'+{payment["amount"]} {payment["currency"]}\n'
                                f'<tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> Спасибо!'
                            )
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление о пополнении: {e}")

                    elif payment["account_type"] and payment["country"]:
                        # Выдача аккаунта
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
                                    f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> Покупка успешна!</b>\n\n'
                                    f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Номер:</b> <code>{account["phone"]}</code>\n'
                                    f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> <b>Оплачено:</b> {payment["amount"]} {payment["currency"]}\n'
                                    f'<tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> <b>Дата:</b> {format_date(msk_time())}',
                                    reply_markup=get_code_keyboard(purchase_id)
                                )
                            except Exception as e:
                                logger.error(f"Не удалось отправить аккаунт: {e}")

        except Exception as e:
            logger.error(f"Ошибка проверки крипто-платежей: {e}")


# ==================== АДМИН-ПАНЕЛЬ ====================
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Обработчик команды /admin"""
    if message.from_user.id not in ADMIN_IDS:
        return

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> Админ панель</b>\n\n'
        f'Выберите действие:'
    )
    await message.answer(text, reply_markup=admin_panel_keyboard())


# ==================== АДМИН: СТАТИСТИКА ====================
@dp.callback_query(F.data == "admin_stats", F.from_user.id.in_(ADMIN_IDS))
async def admin_stats_callback(callback: types.CallbackQuery):
    """Обработчик статистики"""
    stats = await db.get_stats()

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["stats"]}">📊</tg-emoji> Статистика</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> <b>Пользователей:</b> {stats["total_users"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> <b>Аккаунтов всего:</b> {stats["total_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> <b>Продано:</b> {stats["sold_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> <b>Доступно:</b> {stats["available"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> <b>Всего покупок:</b> {stats["total_purchases"]}'
    )
    await callback.message.edit_text(text, reply_markup=admin_panel_keyboard())
    await callback.answer()


# ==================== АДМИН: РАССЫЛКА ====================
@dp.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик начала рассылки"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["megaphone"]}">📣</tg-emoji> Рассылка</b>\n\n'
        f'Отправьте сообщение, которое хотите разослать всем пользователям.'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@dp.message(AdminStates.waiting_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast(message: types.Message, state: FSMContext):
    """Обработчик отправки рассылки"""
    users = await db.get_all_users()
    sent = 0
    failed = 0

    status_msg = await message.answer(
        f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> Начинаю рассылку...'
    )

    for user_id in users:
        try:
            await message.copy_to(user_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> <b>Рассылка завершена!</b>\n\n'
        f'Успешно: {sent}\n'
        f'Ошибок: {failed}\n'
        f'Всего пользователей: {len(users)}',
        reply_markup=admin_panel_keyboard()
    )
    await state.clear()


# ==================== АДМИН: ВЫДАТЬ БАЛАНС ====================
@dp.callback_query(F.data == "admin_give_balance", F.from_user.id.in_(ADMIN_IDS))
async def admin_give_balance_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выдачи баланса"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["money_send"]}">🪙</tg-emoji> Выдать баланс</b>\n\n'
        f'Отправьте ID пользователя:'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await state.set_state(AdminStates.waiting_balance_user)
    await callback.answer()


@dp.message(AdminStates.waiting_balance_user, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_user(message: types.Message, state: FSMContext):
    """Обработчик получения ID пользователя для выдачи баланса"""
    try:
        user_id = int(message.text.strip())
        user = await db.get_user(user_id)

        if not user:
            await message.answer(
                f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Пользователь не найден'
            )
            return

        await state.update_data(balance_user_id=user_id)
        await message.answer(
            f'Пользователь: @{user.get("username") or user_id} (ID: {user_id})\n\n'
            f'Отправьте сумму для пополнения:'
        )
        await state.set_state(AdminStates.waiting_balance_amount)
    except ValueError:
        await message.answer("Неверный ID пользователя")


@dp.message(AdminStates.waiting_balance_amount, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_amount(message: types.Message, state: FSMContext):
    """Обработчик получения суммы для выдачи баланса"""
    try:
        amount = Decimal(message.text.strip())
        if amount <= 0:
            await message.answer("Сумма должна быть больше 0")
            return

        data = await state.get_data()
        user_id = data["balance_user_id"]

        await db.add_balance(user_id, amount)

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Баланс пользователя {user_id} пополнен на {amount} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()
    except:
        await message.answer("Неверная сумма")


# ==================== АДМИН: ДОБАВИТЬ АККАУНТ ====================
@dp.callback_query(F.data == "admin_add_account", F.from_user.id.in_(ADMIN_IDS))
async def admin_add_account_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик добавления аккаунта"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> Добавить аккаунт</b>\n\n'
        f'Выберите тип аккаунта:'
    )
    await callback.message.edit_text(text, reply_markup=add_account_type_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_type_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_type_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора типа при добавлении"""
    account_type = callback.data.split("_")[2]
    await state.update_data(add_account_type=account_type)

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> Тип: {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:'
    )
    await callback.message.edit_text(text, reply_markup=countries_add_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_country_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_country_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора страны при добавлении"""
    country = callback.data.split("_")[2]
    await state.update_data(add_account_country=country)

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> Страна: {COUNTRY_NAMES[country]}</b>\n\n'
        f'Отправьте номер телефона в формате +79001234567:'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await state.set_state(AdminStates.waiting_add_account_phone)
    await callback.answer()


@dp.message(AdminStates.waiting_add_account_phone, F.from_user.id.in_(ADMIN_IDS))
async def addacc_phone_handler(message: types.Message, state: FSMContext):
    """Обработчик получения номера телефона"""
    phone = message.text.strip()

    if not phone.startswith("+"):
        await message.answer("Номер должен начинаться с +")
        return

    await state.update_data(add_account_phone=phone)

    # Авторизуем через Telethon
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        sent = await client.send_code_request(phone)

        await state.update_data(
            add_account_client=client,
            add_account_phone_hash=sent.phone_code_hash
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> Отправьте код подтверждения с номера {phone}:'
        )
        await state.set_state(AdminStates.waiting_add_account_code)
    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Ошибка: {e}'
        )
        await state.clear()


@dp.message(AdminStates.waiting_add_account_code, F.from_user.id.in_(ADMIN_IDS))
async def addacc_code_handler(message: types.Message, state: FSMContext):
    """Обработчик получения кода подтверждения"""
    code = message.text.strip()
    data = await state.get_data()
    client = data.get("add_account_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        await client.sign_in(
            phone=data["add_account_phone"],
            code=code,
            phone_code_hash=data["add_account_phone_hash"]
        )

        session_string = client.session.save()
        await client.disconnect()

        account_type = data["add_account_type"]
        country = data["add_account_country"]

        # Получаем цену для этого типа и страны
        price = await db.get_price(account_type, country)

        # Сохраняем аккаунт
        await db.add_account(
            account_type, country, data["add_account_phone"],
            session_string=session_string,
            price_rub=price["price_rub"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Аккаунт {data["add_account_phone"]} успешно добавлен!\n'
            f'Тип: {ACCOUNT_TYPES[account_type]}\n'
            f'Страна: {COUNTRY_NAMES[country]}\n'
            f'Цена: {price["price_rub"]} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()

    except SessionPasswordNeededError:
        await state.update_data(add_account_client=client)
        await message.answer("Требуется 2FA пароль. Отправьте пароль:")
        await state.set_state(AdminStates.waiting_add_account_password)
    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Ошибка: {e}'
        )
        if client:
            await client.disconnect()
        await state.clear()


@dp.message(AdminStates.waiting_add_account_password, F.from_user.id.in_(ADMIN_IDS))
async def addacc_password_handler(message: types.Message, state: FSMContext):
    """Обработчик 2FA пароля"""
    password = message.text.strip()
    data = await state.get_data()
    client = data.get("add_account_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await client.disconnect()

        account_type = data["add_account_type"]
        country = data["add_account_country"]

        price = await db.get_price(account_type, country)

        await db.add_account(
            account_type, country, data["add_account_phone"],
            session_string=session_string,
            price_rub=price["price_rub"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Аккаунт {data["add_account_phone"]} успешно добавлен!',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()
    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> Ошибка: {e}'
        )
        if client:
            await client.disconnect()
        await state.clear()


# ==================== АДМИН: ИЗМЕНИТЬ ЦЕНЫ ====================
@dp.callback_query(F.data == "admin_change_price", F.from_user.id.in_(ADMIN_IDS))
async def admin_change_price_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик изменения цен"""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> Изменение цен</b>\n\n'
        f'Выберите тип аккаунта:'
    )
    await callback.message.edit_text(text, reply_markup=change_price_type_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_type_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_type_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора типа для изменения цены"""
    account_type = callback.data.split("_")[2]
    await state.update_data(change_price_type=account_type)

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> Тип: {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:'
    )
    await callback.message.edit_text(text, reply_markup=countries_price_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_country_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_country_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик выбора страны для изменения цены"""
    country = callback.data.split("_")[2]
    await state.update_data(change_price_country=country)

    data = await state.get_data()
    current_price = await db.get_price(data["change_price_type"], country)

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> Страна: {COUNTRY_NAMES[country]}</b>\n\n'
        f'Текущая цена: {current_price["price_rub"]} ₽\n\n'
        f'Отправьте новую цену в рублях:'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await state.set_state(AdminStates.waiting_change_price_rub)
    await callback.answer()


@dp.message(AdminStates.waiting_change_price_rub, F.from_user.id.in_(ADMIN_IDS))
async def chprice_rub_handler(message: types.Message, state: FSMContext):
    """Обработчик получения новой цены в рублях"""
    try:
        price_rub = Decimal(message.text.strip())
        if price_rub <= 0:
            await message.answer("Цена должна быть больше 0")
            return

        data = await state.get_data()

        # Сохраняем цену (USDT и TON посчитаются автоматически)
        await db.set_price(
            data["change_price_type"],
            data["change_price_country"],
            price_rub
        )

        new_price = await db.get_price(data["change_price_type"], data["change_price_country"])

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> Цена для '
            f'{ACCOUNT_TYPES[data["change_price_type"]]} - '
            f'{COUNTRY_NAMES[data["change_price_country"]]} обновлена!\n\n'
            f'Новая цена: {new_price["price_rub"]} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()
    except:
        await message.answer("Неверное число. Отправьте цену ещё раз:")


# ==================== ИГНОР ДЛЯ НЕАКТИВНЫХ КНОПОК ====================
@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    """Игнорирует нажатия на неактивные кнопки"""
    await callback.answer()


# ==================== ЗАПУСК БОТА ====================
async def main():
    """Главная функция запуска бота"""
    # Подключаемся к базе данных
    await db.connect()
    await db.init_tables()

    # Подключаем Telethon
    await telethon_client.connect()

    # Запускаем фоновую проверку платежей
    asyncio.create_task(check_crypto_payments_loop())

    # Удаляем вебхук и запускаем поллинг
    await bot(DeleteWebhook(drop_pending_updates=True))

    logger.info("=" * 50)
    logger.info("Бот Vest Traff Accs успешно запущен!")
    logger.info(f"Внутренний курс: 1 USDT = {USDT_RATE} ₽")
    logger.info(f"Внутренний курс: 1 TON = {TON_RATE} ₽")
    logger.info("=" * 50)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
