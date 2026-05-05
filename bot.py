import asyncio
import logging
import re
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import DeleteWebhook, SetMyName
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

# Загрузка переменных окружения
load_dotenv()

# =====================================================================
# КОНФИГУРАЦИЯ БОТА
# =====================================================================

# Данные для Telethon API
API_ID = 32480523
API_HASH = "147839735c9fa4e83451209e9b55cfc5"

# Токены из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")

# Администраторы бота
ADMIN_IDS: List[int] = [7973988177]

# Номер кошелька YooMoney для приёма платежей
YOOMONEY_WALLET = "4100119286550472"

# Внутренние курсы валют (не показываются пользователям)
USDT_RATE = Decimal("90")
TON_RATE = Decimal("95")

# Комиссия платформы с продажи
COMMISSION_RATE = Decimal("0.07")  # 7%

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================================
# ПРЕМИУМ ЭМОДЗИ
# =====================================================================

EMOJI = {
    # Интерфейс
    "settings": "5870982283724328568",
    "profile": "5870994129244131212",
    "people": "5870772616305839506",
    "file": "5870528606328852614",
    "smile": "5870764288364252592",

    # Статистика
    "stats_grow": "5870930636742595124",
    "stats": "5870921681735781843",

    # Элементы
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

    # Время
    "clock": "5983150113483134607",
    "clock_past": "5775896410780079073",
    "calendar": "5890937706803894250",

    # Эмоции
    "celebrate": "6041731551845159060",

    # Финансы
    "wallet": "5769126056262898415",
    "money": "5904462880941545555",
    "money_send": "5890848474563352982",
    "money_accept": "5879814368572478751",

    # Товары
    "box": "5884479287171485878",
    "tag": "5886285355279193209",

    # Крипта
    "cryptobot": "5260752406890711732",

    # Инструменты
    "code": "5940433880585605708",
    "loading": "5345906554510012647",
    "apps": "5778672437122045013",
    "brush": "6050679691004612757",
    "add_text": "5771851822897566479",
    "mirror": "5778672437122045013",

    # Флаги стран
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

# Названия стран
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

# Типы аккаунтов
ACCOUNT_TYPES = {
    "newreg": "Новореги",
    "leaved": "С отлёгой",
    "warmed": "Прогретые",
}


# =====================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =====================================================================

def msk_time() -> datetime:
    """Возвращает текущее московское время."""
    return datetime.now(timezone(timedelta(hours=3)))


def format_date(dt: datetime) -> str:
    """Форматирует дату в московском времени."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%d.%m.%Y %H:%M")


def calc_usdt(rub: Decimal) -> Decimal:
    """Пересчитывает рубли в USDT по внутреннему курсу."""
    return (rub / USDT_RATE).quantize(Decimal("0.01"))


def calc_ton(rub: Decimal) -> Decimal:
    """Пересчитывает рубли в TON по внутреннему курсу."""
    return (rub / TON_RATE).quantize(Decimal("0.01"))


# =====================================================================
# БАЗА ДАННЫХ POSTGRESQL
# =====================================================================

class Database:
    """Класс для работы с базой данных PostgreSQL."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Подключается к базе данных и создаёт пул соединений."""
        self.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        logger.info("Подключение к PostgreSQL установлено")

    async def init_tables(self):
        """Создаёт все необходимые таблицы."""
        async with self.pool.acquire() as conn:
            # Пользователи
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance DECIMAL DEFAULT 0,
                    purchases_count INT DEFAULT 0,
                    sales_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Аккаунты на продажу
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id SERIAL PRIMARY KEY,
                    seller_id BIGINT REFERENCES users(user_id),
                    account_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    description TEXT DEFAULT '',
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
            """)

            # Покупки
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    account_id INT REFERENCES accounts(id),
                    seller_id BIGINT,
                    price DECIMAL,
                    currency TEXT,
                    commission DECIMAL DEFAULT 0,
                    purchase_date TIMESTAMP DEFAULT NOW()
                );
            """)

            # Крипто-платежи
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS crypto_payments (
                    id SERIAL PRIMARY KEY,
                    invoice_id TEXT UNIQUE,
                    user_id BIGINT,
                    amount DECIMAL,
                    currency TEXT,
                    status TEXT DEFAULT 'pending',
                    account_id INT,
                    is_topup BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Заявки на вывод
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS withdraw_requests (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    amount DECIMAL,
                    sbp_details TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Зеркала ботов
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS mirror_bots (
                    id SERIAL PRIMARY KEY,
                    owner_id BIGINT REFERENCES users(user_id),
                    bot_token TEXT NOT NULL,
                    bot_name TEXT DEFAULT '',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Индексы для оптимизации
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_accounts_available 
                ON accounts(is_sold, account_type, country);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_crypto_pending 
                ON crypto_payments(status);
            """)

            logger.info("Таблицы базы данных инициализированы")

    # ==================== ПОЛЬЗОВАТЕЛИ ====================

    async def get_or_create_user(self, uid: int, username: str = None) -> Dict[str, Any]:
        """Получает или создаёт пользователя."""
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", uid)
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                    uid, username
                )
                return {
                    "user_id": uid,
                    "username": username,
                    "balance": Decimal("0"),
                    "purchases_count": 0,
                    "sales_count": 0
                }
            return dict(user)

    async def get_user(self, uid: int) -> Optional[Dict[str, Any]]:
        """Получает пользователя по ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", uid)
            return dict(row) if row else None

    async def add_balance(self, uid: int, amount: Decimal) -> None:
        """Пополняет баланс пользователя."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, uid
            )

    async def deduct_balance(self, uid: int, amount: Decimal) -> None:
        """Списывает средства с баланса."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                amount, uid
            )

    async def increment_sales(self, uid: int) -> None:
        """Увеличивает счётчик продаж."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET sales_count = sales_count + 1 WHERE user_id = $1",
                uid
            )

    # ==================== АККАУНТЫ ====================

    async def get_available_account(self, at: str, cn: str) -> Optional[Dict[str, Any]]:
        """Получает первый доступный аккаунт по типу и стране."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM accounts 
                   WHERE account_type = $1 AND country = $2 AND is_sold = FALSE 
                   ORDER BY created_at LIMIT 1""",
                at, cn
            )

    async def mark_account_sold(self, aid: int, uid: int) -> None:
        """Помечает аккаунт как проданный."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE accounts SET is_sold = TRUE, sold_to = $1, sold_at = NOW() WHERE id = $2",
                uid, aid
            )

    async def add_account(
        self,
        seller_id: int,
        account_type: str,
        country: str,
        phone: str,
        description: str = "",
        session_string: str = None,
        password: str = None,
        price_rub: Decimal = Decimal("0")
    ) -> int:
        """Добавляет новый аккаунт на продажу."""
        pu = calc_usdt(price_rub)
        pt = calc_ton(price_rub)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO accounts 
                   (seller_id, account_type, country, phone, description,
                    session_string, password, price_rub, price_usdt, price_ton)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                   RETURNING id""",
                seller_id, account_type, country, phone, description,
                session_string, password, price_rub, pu, pt
            )

    async def get_account_by_id(self, aid: int) -> Optional[Dict[str, Any]]:
        """Получает аккаунт по ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM accounts WHERE id = $1", aid)
            return dict(row) if row else None

    async def update_account_code(self, aid: int, code: str) -> None:
        """Обновляет код подтверждения аккаунта."""
        async with self.pool.acquire() as conn:
            await conn.execute("UPDATE accounts SET code = $1 WHERE id = $2", code, aid)

    # ==================== ПОКУПКИ ====================

    async def add_purchase(
        self,
        user_id: int,
        account_id: int,
        seller_id: int,
        price: Decimal,
        currency: str,
        commission: Decimal = Decimal("0")
    ) -> int:
        """Добавляет запись о покупке."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET purchases_count = purchases_count + 1 WHERE user_id = $1",
                user_id
            )
            return await conn.fetchval(
                """INSERT INTO purchases (user_id, account_id, seller_id, price, currency, commission)
                   VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
                user_id, account_id, seller_id, price, currency, commission
            )

    async def get_user_purchases(self, uid: int) -> List[Dict[str, Any]]:
        """Получает все покупки пользователя."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT p.*, a.phone, a.code 
                   FROM purchases p JOIN accounts a ON p.account_id = a.id 
                   WHERE p.user_id = $1 ORDER BY p.purchase_date DESC""",
                uid
            )
            return [dict(row) for row in rows]

    async def get_purchase_by_id(self, pid: int, uid: int) -> Optional[Dict[str, Any]]:
        """Получает покупку по ID с проверкой владельца."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT p.*, a.phone, a.code, a.session_string 
                   FROM purchases p JOIN accounts a ON p.account_id = a.id 
                   WHERE p.id = $1 AND p.user_id = $2""",
                pid, uid
            )
            return dict(row) if row else None

    # ==================== CRYPTO PAY ====================

    async def add_crypto_payment(
        self,
        invoice_id: str,
        user_id: int,
        amount: Decimal,
        currency: str,
        account_id: int = None,
        is_topup: bool = False
    ) -> None:
        """Добавляет запись о крипто-платеже."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO crypto_payments 
                   (invoice_id, user_id, amount, currency, account_id, is_topup)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                invoice_id, user_id, amount, currency, account_id, is_topup
            )

    async def update_crypto_payment(self, invoice_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Обновляет статус крипто-платежа."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE crypto_payments SET status = $1 WHERE invoice_id = $2 RETURNING *",
                status, invoice_id
            )

    async def get_pending_payments(self) -> List[Dict[str, Any]]:
        """Получает все ожидающие платежи."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM crypto_payments WHERE status = 'pending'")
            return [dict(row) for row in rows]

    async def get_expired_payments(self) -> List[Dict[str, Any]]:
        """Получает просроченные платежи (старше 10 минут)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM crypto_payments 
                   WHERE status = 'pending' AND created_at < NOW() - INTERVAL '10 minutes'"""
            )
            return [dict(row) for row in rows]

    async def get_crypto_by_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        """Получает платёж по ID счёта."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM crypto_payments WHERE invoice_id = $1", invoice_id
            )
            return dict(row) if row else None

    # ==================== СТАТИСТИКА ====================

    async def get_all_users(self) -> List[int]:
        """Получает ID всех пользователей."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row["user_id"] for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """Получает общую статистику."""
        async with self.pool.acquire() as conn:
            total_users = await conn.fetchval("SELECT COUNT(*) FROM users")
            total_accounts = await conn.fetchval("SELECT COUNT(*) FROM accounts")
            sold_accounts = await conn.fetchval("SELECT COUNT(*) FROM accounts WHERE is_sold = TRUE")
            total_purchases = await conn.fetchval("SELECT COUNT(*) FROM purchases")
            return {
                "total_users": total_users,
                "total_accounts": total_accounts,
                "sold_accounts": sold_accounts,
                "available": total_accounts - sold_accounts,
                "total_purchases": total_purchases
            }

    # ==================== ВЫВОД СРЕДСТВ ====================

    async def add_withdraw_request(self, uid: int, amount: Decimal, sbp: str) -> None:
        """Добавляет заявку на вывод средств."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO withdraw_requests (user_id, amount, sbp_details) VALUES ($1, $2, $3)",
                uid, amount, sbp
            )

    async def get_pending_withdraws(self) -> List[Dict[str, Any]]:
        """Получает все необработанные заявки на вывод."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM withdraw_requests WHERE status = 'pending' ORDER BY created_at"
            )
            return [dict(row) for row in rows]

    # ==================== ЗЕРКАЛА ====================

    async def add_mirror(self, uid: int, token: str, name: str = "") -> None:
        """Добавляет зеркало бота."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO mirror_bots (owner_id, bot_token, bot_name) VALUES ($1, $2, $3)",
                uid, token, name
            )

    async def get_user_mirrors(self, uid: int) -> List[Dict[str, Any]]:
        """Получает зеркала пользователя."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM mirror_bots WHERE owner_id = $1 AND is_active = TRUE",
                uid
            )
            return [dict(row) for row in rows]


# Создаём экземпляр базы данных
db = Database()


# =====================================================================
# СОСТОЯНИЯ FSM
# =====================================================================

class SellStates(StatesGroup):
    """Состояния для продажи аккаунта."""
    waiting_price = State()
    waiting_description = State()
    waiting_phone = State()
    waiting_code = State()
    waiting_password = State()


class TopupStates(StatesGroup):
    """Состояния для пополнения баланса."""
    waiting_amount_usdt = State()
    waiting_amount_ton = State()
    waiting_amount_ym = State()


class WithdrawStates(StatesGroup):
    """Состояния для вывода средств."""
    waiting_amount = State()
    waiting_sbp = State()


class MirrorStates(StatesGroup):
    """Состояния для создания зеркала."""
    waiting_token = State()
    waiting_name = State()


class AdminStates(StatesGroup):
    """Состояния для админ-панели."""
    waiting_broadcast = State()
    waiting_check_invoice = State()


# =====================================================================
# CRYPTO PAY API
# =====================================================================

class CryptoPayAPI:
    """API для работы с Crypto Bot."""

    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        self.token = token

    async def create_invoice(
        self, amount: Decimal, currency: str = "USDT", description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Создаёт счёт на оплату."""
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

    async def get_invoice(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Получает информацию о счёте."""
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


# Создаём экземпляр API
crypto_pay = CryptoPayAPI(CRYPTO_BOT_TOKEN) if CRYPTO_BOT_TOKEN else None


# =====================================================================
# YOOMONEY QUICKPAY
# =====================================================================

def create_yoomoney_link(amount: Decimal, label: str, comment: str = "") -> str:
    """Создаёт ссылку на форму оплаты YooMoney."""
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": comment or "Оплата",
        "paymentType": "AC",
        "sum": str(amount),
        "label": label,
    }
    return f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(params)}"


# =====================================================================
# TELETHON КЛИЕНТ
# =====================================================================

telethon_client = TelegramClient(StringSession(), API_ID, API_HASH)


async def fetch_code_from_telegram(session_string: str) -> Optional[str]:
    """Получает код подтверждения из аккаунта Telegram."""
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
                        if not code.startswith("20"):
                            await client.disconnect()
                            return code
        await client.disconnect()
    except Exception as e:
        logger.error(f"Ошибка получения кода: {e}")
    return None


# =====================================================================
# ИНИЦИАЛИЗАЦИЯ БОТА
# =====================================================================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# =====================================================================
# КЛАВИАТУРЫ
# =====================================================================

def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Купить аккаунт",
            callback_data="buy_account",
            style="primary",
            icon_custom_emoji_id=EMOJI["box"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Продать аккаунт",
            callback_data="sell_account",
            style="success",
            icon_custom_emoji_id=EMOJI["money_send"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Профиль",
            callback_data="profile",
            style="default",
            icon_custom_emoji_id=EMOJI["profile"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Поддержка",
            callback_data="support",
            style="default",
            icon_custom_emoji_id=EMOJI["info"]
        ),
        InlineKeyboardButton(
            text="Проекты",
            callback_data="projects",
            style="default",
            icon_custom_emoji_id=EMOJI["link"]
        )
    )
    return builder.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура профиля."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Мои покупки",
            callback_data="my_purchases",
            style="default",
            icon_custom_emoji_id=EMOJI["box"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Пополнить баланс",
            callback_data="top_up",
            style="success",
            icon_custom_emoji_id=EMOJI["wallet"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Вывод средств",
            callback_data="withdraw",
            style="default",
            icon_custom_emoji_id=EMOJI["money_accept"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Зеркала",
            callback_data="mirrors",
            style="default",
            icon_custom_emoji_id=EMOJI["mirror"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Проверить оплату",
            callback_data="check_payment",
            style="primary",
            icon_custom_emoji_id=EMOJI["bell"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def back_to_main_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◁ Назад в меню",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )]
    ])


def back_to_profile_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в профиль."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )]
    ])


def account_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа аккаунта при покупке."""
    builder = InlineKeyboardBuilder()
    for key, name in ACCOUNT_TYPES.items():
        builder.row(
            InlineKeyboardButton(
                text=name,
                callback_data=f"buy_type_{key}",
                style="default",
                icon_custom_emoji_id=EMOJI["tag"]
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="main_menu",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def sell_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа аккаунта при продаже."""
    builder = InlineKeyboardBuilder()
    for key, name in ACCOUNT_TYPES.items():
        builder.row(
            InlineKeyboardButton(
                text=name,
                callback_data=f"sell_type_{key}",
                style="default",
                icon_custom_emoji_id=EMOJI["tag"]
            )
        )
    return builder.as_markup()


def countries_keyboard(
    prefix: str,
    account_type: str,
    page: int = 0,
    per_page: int = 8
) -> InlineKeyboardMarkup:
    """Клавиатура выбора страны с пагинацией."""
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    builder = InlineKeyboardBuilder()

    for country in page_countries:
        builder.row(
            InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"{prefix}_{account_type}_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◁",
                callback_data=f"spage_{prefix}_{account_type}_{page - 1}",
                icon_custom_emoji_id=EMOJI["down"]
            )
        )
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"{page + 1}/{total_pages}",
            callback_data="ignore"
        )
    )
    if page < total_pages - 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="▷",
                callback_data=f"spage_{prefix}_{account_type}_{page + 1}",
                icon_custom_emoji_id=EMOJI["send"]
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    return builder.as_markup()


async def payment_methods_keyboard(account_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора способа оплаты."""
    account = await db.get_account_by_id(account_id)
    if not account:
        return back_to_main_keyboard()

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=f"Оплатить балансом ({account['price_rub']} ₽)",
            callback_data=f"pay_balance_{account_id}",
            style="primary",
            icon_custom_emoji_id=EMOJI["wallet"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"USDT ({account['price_usdt']} USDT)",
            callback_data=f"pay_usdt_{account_id}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"TON ({account['price_ton']} TON)",
            callback_data=f"pay_ton_{account_id}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"YooMoney ({account['price_rub']} ₽)",
            callback_data=f"pay_ym_{account_id}",
            style="default",
            icon_custom_emoji_id=EMOJI["money"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="buy_account",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def get_code_keyboard(purchase_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для получения кода."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Получить код",
            callback_data=f"get_code_{purchase_id}",
            style="success",
            icon_custom_emoji_id=EMOJI["code"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="my_purchases",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def topup_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура пополнения баланса."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Crypto Bot (USDT)",
            callback_data="top_cusdt",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Crypto Bot (TON)",
            callback_data="top_cton",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="YooMoney (Рубли)",
            callback_data="top_ym",
            style="default",
            icon_custom_emoji_id=EMOJI["money"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def mirror_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура раздела зеркал."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Создать зеркало",
            callback_data="mirror_create",
            style="primary",
            icon_custom_emoji_id=EMOJI["mirror"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Мои зеркала",
            callback_data="mirror_list",
            style="default",
            icon_custom_emoji_id=EMOJI["bot"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="Статистика",
            callback_data="adm_stats",
            style="default",
            icon_custom_emoji_id=EMOJI["stats"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Рассылка",
            callback_data="adm_broadcast",
            style="primary",
            icon_custom_emoji_id=EMOJI["megaphone"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Заявки на вывод",
            callback_data="adm_withdraws",
            style="success",
            icon_custom_emoji_id=EMOJI["money_accept"]
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Зеркала",
            callback_data="adm_mirrors",
            style="default",
            icon_custom_emoji_id=EMOJI["mirror"]
        )
    )
    return builder.as_markup()


# =====================================================================
# ОБРАБОТЧИКИ: СТАРТ
# =====================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    await db.get_or_create_user(message.from_user.id, message.from_user.username)

    welcome_text = (
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'Добро пожаловать в Vest Traff Accs!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Маркетплейс аккаунтов Telegram\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите действие:'
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """Возврат в главное меню."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'Главное меню</b>\n\nВыберите действие:',
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ПРОЕКТЫ И ПОДДЕРЖКА
# =====================================================================

@dp.callback_query(F.data == "projects")
async def projects_callback(callback: CallbackQuery):
    """Раздел проектов."""
    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["link"]}">🔗</tg-emoji> '
        f'Наши проекты:</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'<b>Телеграмм комбайны:</b>\n'
        f'• @VestTrafferBot\n'
        f'• @VestTraffer2bot\n'
        f'• @VestTraffer3bot\n\n'
        f'<tg-emoji emoji-id="{EMOJI["megaphone"]}">📣</tg-emoji> '
        f'<b>Канал:</b> @VestTraffer'
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "support")
async def support_callback(callback: CallbackQuery):
    """Раздел поддержки."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Поддержка</b>\n\n'
        f'По всем вопросам: @VestTrafferSupp',
        reply_markup=back_to_main_keyboard()
    )
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ПРОФИЛЬ
# =====================================================================

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    """Просмотр профиля."""
    user = await db.get_or_create_user(
        callback.from_user.id,
        callback.from_user.username
    )

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> '
        f'Профиль</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'<b>Юзернейм:</b> @{user.get("username") or "нет"}\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'<b>ID:</b> <code>{user["user_id"]}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'<b>Баланс:</b> {user["balance"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'<b>Покупок:</b> {user["purchases_count"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["money_send"]}">🪙</tg-emoji> '
        f'<b>Продаж:</b> {user["sales_count"]}'
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard())
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: МОИ ПОКУПКИ
# =====================================================================

@dp.callback_query(F.data == "my_purchases")
async def my_purchases_callback(callback: CallbackQuery):
    """Список покупок пользователя."""
    purchases = await db.get_user_purchases(callback.from_user.id)

    if not purchases:
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
            f'Мои покупки</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'У вас пока нет покупок.',
            reply_markup=back_to_profile_keyboard()
        )
        await callback.answer()
        return

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Мои покупки:</b>\n\n'
    )
    builder = InlineKeyboardBuilder()

    for i, purchase in enumerate(purchases[:10], 1):
        date_str = format_date(purchase["purchase_date"])
        text += (
            f'{i}. <tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> '
            f'<b>Дата:</b> {date_str}\n'
            f'   <tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
            f'<b>Номер:</b> <code>{purchase["phone"]}</code>\n'
            f'   <tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
            f'<b>Цена:</b> {purchase["price"]} {purchase["currency"]}\n\n'
        )
        builder.row(
            InlineKeyboardButton(
                text=f"Код #{purchase['id']}",
                callback_data=f"get_code_{purchase['id']}",
                style="success",
                icon_custom_emoji_id=EMOJI["code"]
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="◁ Назад",
            callback_data="profile",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ПОЛУЧЕНИЕ КОДА
# =====================================================================

@dp.callback_query(F.data.startswith("get_code_"))
async def get_code_callback(callback: CallbackQuery):
    """Получение кода подтверждения."""
    purchase_id = int(callback.data.split("_")[2])
    purchase = await db.get_purchase_by_id(purchase_id, callback.from_user.id)

    if not purchase:
        await callback.answer("Покупка не найдена", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(
        f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> '
        f'Ищу код подтверждения...'
    )

    # Пытаемся получить свежий код
    session_string = purchase.get("session_string")
    if session_string:
        code = await fetch_code_from_telegram(session_string)
        if code:
            await db.update_account_code(purchase["account_id"], code)
            await status_msg.edit_text(
                f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
                f'Код подтверждения:</b>\n\n'
                f'<code>{code}</code>\n\n'
                f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
                f'<b>Номер:</b> <code>{purchase["phone"]}</code>'
            )
            return

    # Сохранённый код
    if purchase.get("code"):
        await status_msg.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
            f'Код подтверждения:</b>\n\n'
            f'<code>{purchase["code"]}</code>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
            f'<b>Номер:</b> <code>{purchase["phone"]}</code>'
        )
        return

    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Код пока не получен. Обратитесь в @VestTrafferSupp'
    )


# =====================================================================
# ОБРАБОТЧИКИ: ПОПОЛНЕНИЕ БАЛАНСА
# =====================================================================

@dp.callback_query(F.data == "top_up")
async def top_up_callback(callback: CallbackQuery):
    """Меню пополнения баланса."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'Пополнение баланса</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите способ:',
        reply_markup=topup_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "top_cusdt")
async def topup_usdt_callback(callback: CallbackQuery, state: FSMContext):
    """Пополнение USDT."""
    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
        f'Пополнение USDT</b>\n\nОтправьте сумму в USDT:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_usdt)
    await callback.answer()


@dp.callback_query(F.data == "top_cton")
async def topup_ton_callback(callback: CallbackQuery, state: FSMContext):
    """Пополнение TON."""
    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
        f'Пополнение TON</b>\n\nОтправьте сумму в TON:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ton)
    await callback.answer()


@dp.callback_query(F.data == "top_ym")
async def topup_ym_callback(callback: CallbackQuery, state: FSMContext):
    """Пополнение YooMoney."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Пополнение YooMoney</b>\n\nОтправьте сумму в рублях:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ym)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_usdt)
async def process_topup_usdt(message: Message, state: FSMContext):
    """Обработка суммы USDT."""
    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    invoice = await crypto_pay.create_invoice(
        amount, "USDT", f"Пополнение {message.from_user.id}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            message.from_user.id,
            amount,
            "USDT",
            is_topup=True
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Счёт USDT создан!</b>\n\n'
            f'Сумма: {amount} USDT\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=profile_keyboard()
        )
    else:
        await message.answer("Ошибка создания счёта")

    await state.clear()


@dp.message(TopupStates.waiting_amount_ton)
async def process_topup_ton(message: Message, state: FSMContext):
    """Обработка суммы TON."""
    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    invoice = await crypto_pay.create_invoice(
        amount, "TON", f"Пополнение {message.from_user.id}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            message.from_user.id,
            amount,
            "TON",
            is_topup=True
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await message.answer(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Счёт TON создан!</b>\n\n'
            f'Сумма: {amount} TON\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=profile_keyboard()
        )
    else:
        await message.answer("Ошибка создания счёта")

    await state.clear()


@dp.message(TopupStates.waiting_amount_ym)
async def process_topup_ym(message: Message, state: FSMContext):
    """Обработка суммы YooMoney."""
    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer("Неверная сумма. Отправьте число:")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    label = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
    payment_link = create_yoomoney_link(
        amount, label, f"Пополнение {message.from_user.id}"
    )

    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Пополнение YooMoney</b>\n\n'
        f'Сумма: {amount} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'После оплаты отправьте чек в @VestTrafferSupp',
        reply_markup=profile_keyboard()
    )

    await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ: ПРОВЕРИТЬ ОПЛАТУ
# =====================================================================

@dp.callback_query(F.data == "check_payment")
async def check_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Проверка статуса оплаты."""
    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
        f'Проверка оплаты</b>\n\n'
        f'Отправьте ID счёта (invoice_id):',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(AdminStates.waiting_check_invoice)
    await callback.answer()


@dp.message(AdminStates.waiting_check_invoice)
async def process_check_invoice(message: Message, state: FSMContext):
    """Обработка проверки счёта."""
    invoice_id = message.text.strip()
    payment = await db.get_crypto_by_invoice(invoice_id)

    if not payment:
        await message.answer(
            "Счёт не найден в базе данных",
            reply_markup=profile_keyboard()
        )
        await state.clear()
        return

    if payment["status"] == "paid":
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Этот счёт уже оплачен!',
            reply_markup=profile_keyboard()
        )
        await state.clear()
        return

    if payment["status"] == "expired":
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'Время оплаты истекло',
            reply_markup=profile_keyboard()
        )
        await state.clear()
        return

    # Проверяем через API
    invoice = await crypto_pay.get_invoice(int(invoice_id))

    if invoice and invoice.get("status") == "paid":
        await db.update_crypto_payment(invoice_id, "paid")

        if payment["is_topup"]:
            await db.add_balance(payment["user_id"], payment["amount"])
            await message.answer(
                f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
                f'Оплата подтверждена!\n'
                f'Баланс пополнен на {payment["amount"]} {payment["currency"]}',
                reply_markup=profile_keyboard()
            )

        elif payment["account_id"]:
            account = await db.get_account_by_id(payment["account_id"])
            if account and not account["is_sold"]:
                await db.mark_account_sold(account["id"], payment["user_id"])

                commission = (payment["amount"] * COMMISSION_RATE).quantize(Decimal("0.01"))
                seller_amount = payment["amount"] - commission

                await db.add_balance(account["seller_id"], seller_amount)
                await db.increment_sales(account["seller_id"])

                purchase_id = await db.add_purchase(
                    payment["user_id"],
                    account["id"],
                    account["seller_id"],
                    payment["amount"],
                    payment["currency"],
                    commission
                )

                await message.answer(
                    f'<tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
                    f'Оплата подтверждена!\n'
                    f'<code>{account["phone"]}</code>',
                    reply_markup=get_code_keyboard(purchase_id)
                )

                # Уведомляем продавца
                try:
                    await bot.send_message(
                        account["seller_id"],
                        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
                        f'Ваш аккаунт {account["phone"]} продан!\n'
                        f'На баланс: {seller_amount} {payment["currency"]}\n'
                        f'Комиссия: {commission} {payment["currency"]}'
                    )
                except Exception:
                    pass
    else:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'Оплата ещё не прошла. Попробуйте позже.',
            reply_markup=profile_keyboard()
        )

    await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ: ВЫВОД СРЕДСТВ
# =====================================================================

@dp.callback_query(F.data == "withdraw")
async def withdraw_callback(callback: CallbackQuery, state: FSMContext):
    """Вывод средств."""
    user = await db.get_user(callback.from_user.id)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money_accept"]}">🏧</tg-emoji> '
        f'Вывод средств</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'Баланс: {user["balance"]} ₽\n\n'
        f'Отправьте сумму для вывода:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(WithdrawStates.waiting_amount)
    await callback.answer()


@dp.message(WithdrawStates.waiting_amount)
async def process_withdraw_amount(message: Message, state: FSMContext):
    """Обработка суммы вывода."""
    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer("Неверная сумма. Отправьте число:")
        return

    user = await db.get_user(message.from_user.id)

    if amount > user["balance"]:
        await message.answer(
            f"Недостаточно средств. Баланс: {user['balance']} ₽"
        )
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    await state.update_data(withdraw_amount=amount)
    await message.answer(
        "Отправьте реквизиты СБП (номер телефона или карты):"
    )
    await state.set_state(WithdrawStates.waiting_sbp)


@dp.message(WithdrawStates.waiting_sbp)
async def process_withdraw_sbp(message: Message, state: FSMContext):
    """Обработка реквизитов СБП."""
    sbp_details = message.text.strip()
    data = await state.get_data()
    amount = data["withdraw_amount"]

    # Списываем средства и создаём заявку
    await db.deduct_balance(message.from_user.id, amount)
    await db.add_withdraw_request(message.from_user.id, amount, sbp_details)

    # Уведомляем администраторов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f'<tg-emoji emoji-id="{EMOJI["money_accept"]}">🏧</tg-emoji> '
                f'<b>Новая заявка на вывод!</b>\n\n'
                f'От: {message.from_user.id} (@{message.from_user.username})\n'
                f'Сумма: {amount} ₽\n'
                f'СБП: <code>{sbp_details}</code>'
            )
        except Exception:
            pass

    await message.answer(
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'Заявка на вывод создана!\n\n'
        f'Сумма: {amount} ₽\n'
        f'Реквизиты: <code>{sbp_details}</code>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Ожидайте обработки администратором.',
        reply_markup=profile_keyboard()
    )

    await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ: ЗЕРКАЛА
# =====================================================================

@dp.callback_query(F.data == "mirrors")
async def mirrors_callback(callback: CallbackQuery):
    """Раздел зеркал."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["mirror"]}">📦</tg-emoji> '
        f'Зеркала бота</b>\n\n'
        f'Создайте копию бота на своём токене.',
        reply_markup=mirror_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "mirror_create")
async def mirror_create_callback(callback: CallbackQuery, state: FSMContext):
    """Создание зеркала."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["mirror"]}">📦</tg-emoji> '
        f'Создание зеркала</b>\n\n'
        f'Отправьте токен бота от @BotFather:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(MirrorStates.waiting_token)
    await callback.answer()


@dp.message(MirrorStates.waiting_token)
async def process_mirror_token(message: Message, state: FSMContext):
    """Проверка токена бота."""
    token = message.text.strip()

    # Проверяем валидность токена
    try:
        test_bot = Bot(token=token)
        me = await test_bot.get_me()
        await test_bot.session.close()
    except Exception:
        await message.answer(
            "Неверный токен бота. Проверьте и отправьте снова:"
        )
        return

    await state.update_data(mirror_token=token)

    await message.answer(
        f'Бот: @{me.username}\n\n'
        f'Отправьте новое имя для бота '
        f'(или отправьте "-" чтобы оставить текущее):'
    )
    await state.set_state(MirrorStates.waiting_name)


@dp.message(MirrorStates.waiting_name)
async def process_mirror_name(message: Message, state: FSMContext):
    """Создание зеркала."""
    name = message.text.strip()
    data = await state.get_data()
    token = data["mirror_token"]

    # Меняем имя бота если нужно
    if name != "-":
        try:
            temp_bot = Bot(token=token)
            await temp_bot(SetMyName(name=name))
            await temp_bot.session.close()
        except Exception:
            pass

    # Сохраняем в базу
    await db.add_mirror(
        message.from_user.id,
        token,
        name if name != "-" else ""
    )

    # Запускаем зеркало в фоне
    asyncio.create_task(run_mirror_bot(token, message.from_user.id))

    await message.answer(
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'Зеркало успешно создано и запущено!',
        reply_markup=profile_keyboard()
    )
    await state.clear()


async def run_mirror_bot(token: str, owner_id: int):
    """Запускает зеркало бота в отдельном процессе."""
    try:
        mirror_bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        mirror_dp = Dispatcher(storage=MemoryStorage())

        # Регистрируем базовые обработчики для зеркала
        @mirror_dp.message(CommandStart())
        async def mirror_start(msg: Message):
            await msg.answer(
                f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
                f'Vest Traff Mirror</b>\n\n'
                f'Маркетплейс аккаунтов Telegram'
            )

        @mirror_dp.callback_query()
        async def mirror_all_callbacks(cb: CallbackQuery):
            await cb.answer("Зеркало работает")

        logger.info(f"Зеркало бота запущено: {token[:10]}... для {owner_id}")
        await mirror_dp.start_polling(mirror_bot)

    except Exception as e:
        logger.error(f"Ошибка запуска зеркала: {e}")


@dp.callback_query(F.data == "mirror_list")
async def mirror_list_callback(callback: CallbackQuery):
    """Список зеркал пользователя."""
    mirrors = await db.get_user_mirrors(callback.from_user.id)

    if not mirrors:
        await callback.answer("У вас нет активных зеркал", show_alert=True)
        return

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'Мои зеркала:</b>\n\n'
    )

    for i, mirror in enumerate(mirrors, 1):
        created = mirror["created_at"].strftime("%d.%m.%Y")
        text += (
            f'{i}. ID: {mirror["id"]}\n'
            f'   Имя: {mirror["bot_name"] or "Без имени"}\n'
            f'   Создан: {created}\n\n'
        )

    await callback.message.edit_text(text, reply_markup=mirror_keyboard())
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ПРОДАТЬ АККАУНТ
# =====================================================================

@dp.callback_query(F.data == "sell_account")
async def sell_account_callback(callback: CallbackQuery):
    """Начало продажи аккаунта."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money_send"]}">🪙</tg-emoji> '
        f'Продать аккаунт</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'Выберите тип аккаунта:',
        reply_markup=sell_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sell_type_"))
async def sell_type_callback(callback: CallbackQuery, state: FSMContext):
    """Выбор типа аккаунта при продаже."""
    account_type = callback.data.split("_")[2]
    await state.update_data(sell_type=account_type)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_keyboard("sell_country", account_type)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sell_country_"))
async def sell_country_callback(callback: CallbackQuery, state: FSMContext):
    """Выбор страны при продаже."""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    await state.update_data(sell_type=account_type, sell_country=country)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
        f'Отправьте цену в рублях:',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(SellStates.waiting_price)
    await callback.answer()


@dp.message(SellStates.waiting_price)
async def process_sell_price(message: Message, state: FSMContext):
    """Обработка цены."""
    try:
        price = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer("Неверная цена. Отправьте число:")
        return

    if price <= 0:
        await message.answer("Цена должна быть больше 0")
        return

    await state.update_data(sell_price=price)
    await message.answer("Отправьте описание товара:")
    await state.set_state(SellStates.waiting_description)


@dp.message(SellStates.waiting_description)
async def process_sell_description(message: Message, state: FSMContext):
    """Обработка описания."""
    description = message.text.strip()
    await state.update_data(sell_description=description)

    await message.answer(
        f'<tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> '
        f'Отправьте номер телефона в формате +79001234567:'
    )
    await state.set_state(SellStates.waiting_phone)


@dp.message(SellStates.waiting_phone)
async def process_sell_phone(message: Message, state: FSMContext):
    """Обработка номера телефона."""
    phone = message.text.strip()

    if not phone.startswith("+"):
        await message.answer("Номер должен начинаться с +")
        return

    await state.update_data(sell_phone=phone)

    # Авторизуем через Telethon
    try:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        sent = await client.send_code_request(phone)

        await state.update_data(
            sell_client=client,
            sell_phone_hash=sent.phone_code_hash
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
            f'Отправьте код подтверждения с номера {phone}:'
        )
        await state.set_state(SellStates.waiting_code)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()


@dp.message(SellStates.waiting_code)
async def process_sell_code(message: Message, state: FSMContext):
    """Обработка кода подтверждения."""
    code = message.text.strip()
    data = await state.get_data()
    client = data.get("sell_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        await client.sign_in(
            phone=data["sell_phone"],
            code=code,
            phone_code_hash=data["sell_phone_hash"]
        )

        session_string = client.session.save()
        await client.disconnect()

        # Сохраняем аккаунт в базу
        account_id = await db.add_account(
            message.from_user.id,
            data["sell_type"],
            data["sell_country"],
            data["sell_phone"],
            data["sell_description"],
            session_string=session_string,
            price_rub=data["sell_price"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Аккаунт успешно добавлен на продажу!\n\n'
            f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
            f'<b>Номер:</b> {data["sell_phone"]}\n'
            f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
            f'<b>Цена:</b> {data["sell_price"]} ₽\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'<b>Описание:</b> {data["sell_description"]}\n\n'
            f'ID аккаунта: {account_id}',
            reply_markup=main_menu_keyboard()
        )
        await state.clear()

    except SessionPasswordNeededError:
        await state.update_data(sell_client=client)
        await message.answer("Требуется 2FA пароль. Отправьте пароль:")
        await state.set_state(SellStates.waiting_password)

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        if client:
            await client.disconnect()
        await state.clear()


@dp.message(SellStates.waiting_password)
async def process_sell_password(message: Message, state: FSMContext):
    """Обработка 2FA пароля."""
    password = message.text.strip()
    data = await state.get_data()
    client = data.get("sell_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        await client.sign_in(password=password)

        session_string = client.session.save()
        await client.disconnect()

        account_id = await db.add_account(
            message.from_user.id,
            data["sell_type"],
            data["sell_country"],
            data["sell_phone"],
            data["sell_description"],
            session_string=session_string,
            price_rub=data["sell_price"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Аккаунт успешно добавлен на продажу!\n\n'
            f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
            f'<b>Номер:</b> {data["sell_phone"]}\n'
            f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
            f'<b>Цена:</b> {data["sell_price"]} ₽\n\n'
            f'ID аккаунта: {account_id}',
            reply_markup=main_menu_keyboard()
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        if client:
            await client.disconnect()
        await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ: КУПИТЬ АККАУНТ
# =====================================================================

@dp.callback_query(F.data == "buy_account")
async def buy_account_callback(callback: CallbackQuery):
    """Начало покупки аккаунта."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Купить аккаунт</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'Выберите тип аккаунта:',
        reply_markup=account_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_type_"))
async def buy_type_callback(callback: CallbackQuery):
    """Выбор типа аккаунта при покупке."""
    account_type = callback.data.split("_")[2]

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_keyboard("buy_country", account_type)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy_country_"))
async def buy_country_callback(callback: CallbackQuery):
    """Выбор страны при покупке."""
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    account = await db.get_available_account(account_type, country)

    if not account:
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
            f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'<b>Нет в наличии</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'Попробуйте другую страну или тип.',
            reply_markup=back_to_main_keyboard()
        )
        await callback.answer("Нет в наличии", show_alert=True)
        return

    description = account.get("description", "") or "Без описания"

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'<b>Цена:</b> {account["price_rub"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'<b>Описание:</b> {description}\n\n'
        f'Выберите способ оплаты:',
        reply_markup=await payment_methods_keyboard(account["id"])
    )
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ОПЛАТА БАЛАНСОМ
# =====================================================================

@dp.callback_query(F.data.startswith("pay_balance_"))
async def pay_balance_callback(callback: CallbackQuery):
    """Оплата внутренним балансом."""
    account_id = int(callback.data.split("_")[2])
    account = await db.get_account_by_id(account_id)

    if not account or account["is_sold"]:
        await callback.answer("Аккаунт недоступен", show_alert=True)
        return

    user = await db.get_user(callback.from_user.id)

    if user["balance"] < account["price_rub"]:
        await callback.answer(
            f"Недостаточно средств. Баланс: {user['balance']} ₽",
            show_alert=True
        )
        return

    # Списываем средства
    await db.deduct_balance(callback.from_user.id, account["price_rub"])

    # Рассчитываем комиссию
    commission = (account["price_rub"] * COMMISSION_RATE).quantize(Decimal("0.01"))
    seller_amount = account["price_rub"] - commission

    # Начисляем продавцу
    await db.add_balance(account["seller_id"], seller_amount)
    await db.increment_sales(account["seller_id"])

    # Помечаем проданным
    await db.mark_account_sold(account_id, callback.from_user.id)

    # Записываем покупку
    purchase_id = await db.add_purchase(
        callback.from_user.id,
        account_id,
        account["seller_id"],
        account["price_rub"],
        "RUB",
        commission
    )

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
        f'Покупка успешна!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'<b>Номер:</b> <code>{account["phone"]}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'<b>Списано:</b> {account["price_rub"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'<b>Остаток:</b> {user["balance"] - account["price_rub"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> '
        f'<b>Дата:</b> {format_date(msk_time())}',
        reply_markup=get_code_keyboard(purchase_id)
    )

    # Уведомляем продавца
    try:
        await bot.send_message(
            account["seller_id"],
            f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
            f'Ваш аккаунт {account["phone"]} продан!\n'
            f'На баланс: {seller_amount} ₽\n'
            f'Комиссия платформы: {commission} ₽ (7%)'
        )
    except Exception:
        pass

    await callback.answer("Покупка успешна!", show_alert=True)


# =====================================================================
# ОБРАБОТЧИКИ: ОПЛАТА USDT
# =====================================================================

@dp.callback_query(F.data.startswith("pay_usdt_"))
async def pay_usdt_callback(callback: CallbackQuery):
    """Оплата через USDT."""
    account_id = int(callback.data.split("_")[2])
    account = await db.get_account_by_id(account_id)

    if not account or account["is_sold"]:
        await callback.answer("Аккаунт недоступен", show_alert=True)
        return

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        account["price_usdt"],
        "USDT",
        f"Покупка аккаунта {account['phone']}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            callback.from_user.id,
            account["price_usdt"],
            "USDT",
            account_id
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Оплата USDT</b>\n\n'
            f'Сумма: {account["price_usdt"]} USDT\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=back_to_main_keyboard()
        )

    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ОПЛАТА TON
# =====================================================================

@dp.callback_query(F.data.startswith("pay_ton_"))
async def pay_ton_callback(callback: CallbackQuery):
    """Оплата через TON."""
    account_id = int(callback.data.split("_")[2])
    account = await db.get_account_by_id(account_id)

    if not account or account["is_sold"]:
        await callback.answer("Аккаунт недоступен", show_alert=True)
        return

    if not crypto_pay:
        await callback.answer("Crypto Pay не настроен", show_alert=True)
        return

    invoice = await crypto_pay.create_invoice(
        account["price_ton"],
        "TON",
        f"Покупка аккаунта {account['phone']}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            callback.from_user.id,
            account["price_ton"],
            "TON",
            account_id
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Оплата TON</b>\n\n'
            f'Сумма: {account["price_ton"]} TON\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=back_to_main_keyboard()
        )

    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ: ОПЛАТА YOOMONEY
# =====================================================================

@dp.callback_query(F.data.startswith("pay_ym_"))
async def pay_ym_callback(callback: CallbackQuery):
    """Оплата через YooMoney."""
    account_id = int(callback.data.split("_")[2])
    account = await db.get_account_by_id(account_id)

    if not account or account["is_sold"]:
        await callback.answer("Аккаунт недоступен", show_alert=True)
        return

    label = f"buy_{callback.from_user.id}_{uuid.uuid4().hex[:8]}"
    payment_link = create_yoomoney_link(
        account["price_rub"],
        label,
        f"Покупка {account['phone']}"
    )

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Оплата YooMoney</b>\n\n'
        f'Сумма: {account["price_rub"]} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'После оплаты отправьте чек в @VestTrafferSupp\n'
        f'Аккаунт будет выдан после проверки.',
        reply_markup=back_to_main_keyboard()
    )

    await callback.answer()


# =====================================================================
# ПАГИНАЦИЯ СТРАН
# =====================================================================

@dp.callback_query(F.data.startswith("spage_"))
async def spage_callback(callback: CallbackQuery):
    """Обработчик пагинации стран."""
    parts = callback.data.split("_")
    prefix = parts[1]
    account_type = parts[2]
    page = int(parts[3])

    await callback.message.edit_text(
        f'<b>Выберите страну:</b>',
        reply_markup=countries_keyboard(prefix, account_type, page)
    )
    await callback.answer()


# =====================================================================
# ИГНОР ДЛЯ НЕАКТИВНЫХ КНОПОК
# =====================================================================

@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    """Игнорирует нажатия на неактивные кнопки."""
    await callback.answer()


# =====================================================================
# ФОНОВАЯ ПРОВЕРКА ПЛАТЕЖЕЙ
# =====================================================================

async def check_crypto_payments_loop():
    """Бесконечный цикл проверки крипто-платежей."""
    logger.info("Запущена фоновая проверка крипто-платежей")

    while True:
        await asyncio.sleep(5)

        if not crypto_pay:
            continue

        try:
            # Отменяем просроченные
            expired = await db.get_expired_payments()
            for payment in expired:
                await db.update_crypto_payment(payment["invoice_id"], "expired")

            # Проверяем pending
            pending = await db.get_pending_payments()
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
                                f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
                                f'Баланс пополнен!</b>\n\n'
                                f'+{payment["amount"]} {payment["currency"]}'
                            )
                        except Exception:
                            pass

                    elif payment["account_id"]:
                        # Покупка аккаунта
                        account = await db.get_account_by_id(payment["account_id"])
                        if account and not account["is_sold"]:
                            await db.mark_account_sold(account["id"], payment["user_id"])

                            commission = (payment["amount"] * COMMISSION_RATE).quantize(Decimal("0.01"))
                            seller_amount = payment["amount"] - commission

                            await db.add_balance(account["seller_id"], seller_amount)
                            await db.increment_sales(account["seller_id"])

                            purchase_id = await db.add_purchase(
                                payment["user_id"],
                                account["id"],
                                account["seller_id"],
                                payment["amount"],
                                payment["currency"],
                                commission
                            )

                            try:
                                await bot.send_message(
                                    payment["user_id"],
                                    f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
                                    f'Покупка успешна!</b>\n\n'
                                    f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
                                    f'<b>Номер:</b> <code>{account["phone"]}</code>\n'
                                    f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
                                    f'<b>Оплачено:</b> {payment["amount"]} {payment["currency"]}',
                                    reply_markup=get_code_keyboard(purchase_id)
                                )
                            except Exception:
                                pass

                            # Уведомляем продавца
                            try:
                                await bot.send_message(
                                    account["seller_id"],
                                    f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
                                    f'Ваш аккаунт {account["phone"]} продан!\n'
                                    f'На баланс: {seller_amount} {payment["currency"]}\n'
                                    f'Комиссия: {commission} {payment["currency"]} (7%)'
                                )
                            except Exception:
                                pass

        except Exception as e:
            logger.error(f"Ошибка проверки платежей: {e}")


# =====================================================================
# АДМИН-ПАНЕЛЬ
# =====================================================================

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """Админ-панель."""
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> '
        f'Админ панель</b>\n\nВыберите действие:',
        reply_markup=admin_keyboard()
    )


@dp.callback_query(F.data == "adm_stats", F.from_user.id.in_(ADMIN_IDS))
async def admin_stats_callback(callback: CallbackQuery):
    """Статистика."""
    stats = await db.get_stats()

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["stats"]}">📊</tg-emoji> '
        f'Статистика</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> '
        f'Пользователей: {stats["total_users"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Аккаунтов: {stats["total_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'Продано: {stats["sold_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'Доступно: {stats["available"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Покупок: {stats["total_purchases"]}',
        reply_markup=admin_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "adm_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_callback(callback: CallbackQuery, state: FSMContext):
    """Рассылка."""
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["megaphone"]}">📣</tg-emoji> '
        f'Рассылка</b>\n\nОтправьте сообщение для рассылки:',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@dp.message(AdminStates.waiting_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast(message: Message, state: FSMContext):
    """Выполнение рассылки."""
    users = await db.get_all_users()
    sent = 0
    failed = 0

    status_msg = await message.answer(
        f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> '
        f'Начинаю рассылку...'
    )

    for user_id in users:
        try:
            await message.copy_to(user_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'<b>Рассылка завершена!</b>\n\n'
        f'Успешно: {sent}\n'
        f'Ошибок: {failed}\n'
        f'Всего пользователей: {len(users)}',
        reply_markup=admin_keyboard()
    )
    await state.clear()


@dp.callback_query(F.data == "adm_withdraws", F.from_user.id.in_(ADMIN_IDS))
async def admin_withdraws_callback(callback: CallbackQuery):
    """Заявки на вывод."""
    withdraws = await db.get_pending_withdraws()

    if not withdraws:
        await callback.answer("Нет заявок на вывод", show_alert=True)
        return

    text = (
        f'<b><tg-emoji emoji-id="{EMOJI["money_accept"]}">🏧</tg-emoji> '
        f'Заявки на вывод:</b>\n\n'
    )

    for w in withdraws:
        text += (
            f'ID: {w["id"]}\n'
            f'User: {w["user_id"]}\n'
            f'Сумма: {w["amount"]} ₽\n'
            f'СБП: <code>{w["sbp_details"]}</code>\n'
            f'Дата: {w["created_at"]}\n'
            f'---\n'
        )

    await callback.message.edit_text(text, reply_markup=admin_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "adm_mirrors", F.from_user.id.in_(ADMIN_IDS))
async def admin_mirrors_callback(callback: CallbackQuery):
    """Список зеркал."""
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM mirror_bots ORDER BY created_at DESC LIMIT 20"
        )

        if not rows:
            await callback.answer("Нет созданных зеркал", show_alert=True)
            return

        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["mirror"]}">📦</tg-emoji> '
            f'Зеркала ботов:</b>\n\n'
        )

        for r in rows:
            text += (
                f'Owner: {r["owner_id"]}\n'
                f'Имя: {r["bot_name"] or "—"}\n'
                f'Создан: {r["created_at"]}\n'
                f'---\n'
            )

        await callback.message.edit_text(text, reply_markup=admin_keyboard())
        await callback.answer()


# =====================================================================
# ЗАПУСК БОТА
# =====================================================================

async def main():
    """Главная функция запуска бота."""
    logger.info("=" * 60)
    logger.info("Запуск бота Vest Traff Accs...")

    # Подключаем базу данных
    await db.connect()
    await db.init_tables()
    logger.info("База данных готова")

    # Подключаем Telethon
    await telethon_client.connect()
    logger.info("Telethon подключён")

    # Запускаем фоновую проверку платежей
    asyncio.create_task(check_crypto_payments_loop())
    logger.info("Фоновая проверка платежей запущена")

    # Очищаем вебхук и запускаем поллинг
    await bot(DeleteWebhook(drop_pending_updates=True))

    logger.info("=" * 60)
    logger.info("Бот Vest Traff Accs успешно запущен!")
    logger.info(f"Курс USDT: 1 = {USDT_RATE} ₽")
    logger.info(f"Курс TON: 1 = {TON_RATE} ₽")
    logger.info(f"Комиссия платформы: {COMMISSION_RATE * 100}%")
    logger.info(f"Кошелёк YooMoney: {YOOMONEY_WALLET}")
    logger.info(f"Поддержка: @VestTrafferSupp")
    logger.info("=" * 60)

    # Запускаем поллинг
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
