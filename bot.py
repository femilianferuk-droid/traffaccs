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
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.methods import DeleteWebhook
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton
)

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError
)
from telethon.sessions import StringSession

import asyncpg
import aiohttp
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# =====================================================================
# КОНФИГУРАЦИЯ БОТА
# =====================================================================

# Данные для Telethon (авторизация аккаунтов)
API_ID = 32480523
API_HASH = "147839735c9fa4e83451209e9b55cfc5"

# Токены из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN", "")

# Список администраторов (Telegram ID)
ADMIN_IDS: List[int] = [7973988177]

# Номер кошелька YooMoney для приёма платежей
YOOMONEY_WALLET = "4100119286550472"

# Внутренние курсы валют (не показываются пользователям)
USDT_RATE = Decimal("90")    # 1 USDT = 90 рублей
TON_RATE = Decimal("95")     # 1 TON = 95 рублей

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =====================================================================
# ПРЕМИУМ ЭМОДЗИ TELEGRAM
# =====================================================================
# Все эмодзи используются через premium ID
# Для текста: <tg-emoji emoji-id="ID">символ</tg-emoji>
# Для кнопок: icon_custom_emoji_id="ID"

EMOJI = {
    # Основные иконки интерфейса
    "settings": "5870982283724328568",      # ⚙ Настройки
    "profile": "5870994129244131212",        # 👤 Профиль
    "people": "5870772616305839506",         # 👥 Люди
    "file": "5870528606328852614",           # 📁 Файл
    "smile": "5870764288364252592",          # 🙂 Смайл улыбка

    # Графики и статистика
    "stats_grow": "5870930636742595124",     # 📊 Рост график
    "stats": "5870921681735781843",          # 📊 Статистика график

    # Дом и замки
    "house": "5873147866364514353",          # 🏘 Дом
    "lock_closed": "6037249452824072506",    # 🔒 Замок закрытый
    "lock_open": "6037496202990194718",      # 🔓 Замок открытый

    # Действия
    "megaphone": "6039422865189638057",      # 📣 Рупор (рассылка)
    "check": "5870633910337015697",          # ✅ Галочка
    "cross": "5870657884844462243",          # ❌ Крестик
    "pencil": "5870676941614354370",         # 🖋 Карандаш
    "trash": "5870875489362513438",          # 🗑 Мусорный бак

    # Навигация
    "down": "5893057118545646106",           # 📰 Вниз (назад)
    "clip": "6039451237743595514",           # 📎 Скрепка
    "link": "5769289093221454192",           # 🔗 Ссылка
    "send": "5963103826075456248",           # ⬆ Отправить
    "download": "6039802767931871481",       # ⬇ Скачать

    # Уведомления и информация
    "info": "6028435952299413210",           # ℹ Инфо
    "bot": "6030400221232501136",            # 🤖 Бот
    "eye": "6037397706505195857",            # 👁 Глаз
    "eye_hidden": "6037243349675544634",     # 👁 Скрыто
    "bell": "6039486778597970865",           # 🔔 Уведомление
    "gift": "6032644646587338669",           # 🎁 Подарок

    # Время
    "clock": "5983150113483134607",          # ⏰ Часы
    "clock_past": "5775896410780079073",     # 🕓 Время прошло
    "calendar": "5890937706803894250",       # 📅 Календарь

    # Праздники и эмоции
    "celebrate": "6041731551845159060",      # 🎉 Ура

    # Финансы
    "wallet": "5769126056262898415",         # 👛 Кошелек
    "money": "5904462880941545555",          # 🪙 Деньги
    "money_send": "5890848474563352982",     # 🪙 Отправить деньги
    "money_accept": "5879814368572478751",   # 🏧 Принять деньги

    # Товары
    "box": "5884479287171485878",            # 📦 Коробка
    "tag": "5886285355279193209",            # 🏷 Бирка

    # Криптовалюта
    "cryptobot": "5260752406890711732",      # 👾 Криптобот

    # Инструменты
    "code": "5940433880585605708",           # 🔨 Код </>
    "loading": "5345906554510012647",        # 🔄 Загрузка
    "apps": "5778672437122045013",           # 📦 Приложения
    "brush": "6050679691004612757",          # 🖌 Кисточка
    "add_text": "5771851822897566479",       # 🔡 Добавить текст

    # Флаги стран
    "usa": "5202021044105257611",            # 🇺🇸 США
    "russia": "5449408995691341691",         # 🇷🇺 Россия
    "ukraine": "5447309366568953338",        # 🇺🇦 Украина
    "belarus": "5382219601054544127",        # 🇧🇾 Беларусь
    "kazakhstan": "5228718354658769982",     # 🇰🇿 Казахстан
    "uzbekistan": "5449829434334912605",     # 🇺🇿 Узбекистан
    "china": "5431782733376399004",          # 🇨🇳 Китай
    "myanmar": "5188162778073935826",        # 🇲🇲 Мьянма
    "india": "5447419223242449630",          # 🇮🇳 Индия
    "bangladesh": "5222131025877936317",     # 🇧🇩 Бангладеш
    "pakistan": "5269660289321679111",       # 🇵🇰 Пакистан
    "nigeria": "5411568100430587798",        # 🇳🇬 Нигерия
    "spain": "5201957744877248121",          # 🇪🇸 Испания
    "france": "5202132623060640759",         # 🇫🇷 Франция
    "uk": "5202196682497859879",             # 🇬🇧 Великобритания
    "romania": "5411159898148840778",        # 🇷🇴 Румыния
    "japan": "5456261908069885892",          # 🇯🇵 Япония
    "egypt": "5226476858471626962",          # 🇪🇬 Египет
    "sweden": "5384542551296455687",         # 🇸🇪 Швеция
    "tajikistan": "5427304285077516492",     # 🇹🇯 Таджикистан
    "brazil": "5202074005346983800",         # 🇧🇷 Бразилия
    "argentina": "5262873863036872166",      # 🇦🇷 Аргентина
    "canada": "5382084502858249131",         # 🇨🇦 Канада
}

# Названия стран на русском языке
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
    """
    Возвращает текущее московское время (UTC+3).
    Используется для отображения дат покупок.
    """
    return datetime.now(timezone(timedelta(hours=3)))


def format_date(dt: datetime) -> str:
    """
    Форматирует дату в московском времени.
    Пример: 05.05.2026 14:30
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    msk = dt.astimezone(timezone(timedelta(hours=3)))
    return msk.strftime("%d.%m.%Y %H:%M")


def calc_usdt(rub: Decimal) -> Decimal:
    """
    Пересчитывает рубли в USDT по внутреннему курсу.
    Используется для автоматического расчёта цен в USDT.
    """
    return (rub / USDT_RATE).quantize(Decimal("0.01"))


def calc_ton(rub: Decimal) -> Decimal:
    """
    Пересчитывает рубли в TON по внутреннему курсу.
    Используется для автоматического расчёта цен в TON.
    """
    return (rub / TON_RATE).quantize(Decimal("0.01"))


# =====================================================================
# РАБОТА С БАЗОЙ ДАННЫХ POSTGRESQL
# =====================================================================

class Database:
    """
    Класс для работы с PostgreSQL.
    Содержит все методы для CRUD операций.
    """

    def __init__(self):
        """Инициализация пула соединений."""
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """
        Подключается к базе данных PostgreSQL.
        Создаёт пул соединений для эффективной работы.
        """
        self.pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10
        )
        logger.info("Подключение к PostgreSQL установлено")

    async def init_tables(self):
        """
        Создаёт все необходимые таблицы, если они не существуют.
        Выполняется при запуске бота.
        """
        async with self.pool.acquire() as conn:
            await conn.execute("""
                -- Таблица пользователей
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    balance DECIMAL DEFAULT 0,
                    purchases_count INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                -- Таблица аккаунтов для продажи
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

                -- Таблица покупок
                CREATE TABLE IF NOT EXISTS purchases (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(user_id),
                    account_id INT REFERENCES accounts(id),
                    price DECIMAL,
                    currency TEXT,
                    purchase_date TIMESTAMP DEFAULT NOW()
                );

                -- Таблица цен (задаются админом, USDT и TON считаются автоматически)
                CREATE TABLE IF NOT EXISTS prices (
                    id SERIAL PRIMARY KEY,
                    account_type TEXT NOT NULL,
                    country TEXT NOT NULL,
                    price_rub DECIMAL DEFAULT 0,
                    UNIQUE(account_type, country)
                );

                -- Таблица крипто-платежей (для отслеживания счетов Crypto Pay)
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
            logger.info("Таблицы базы данных инициализированы")

    # ==================== МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ====================

    async def get_or_create_user(
        self, user_id: int, username: str = None
    ) -> Dict[str, Any]:
        """
        Получает пользователя из БД или создаёт нового.
        Возвращает словарь с данными пользователя.
        """
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            if not user:
                await conn.execute(
                    "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                    user_id, username
                )
                return {
                    "user_id": user_id,
                    "username": username,
                    "balance": Decimal("0"),
                    "purchases_count": 0
                }
            return dict(user)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает пользователя по ID.
        Возвращает None если пользователь не найден.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            return dict(row) if row else None

    async def add_balance(self, user_id: int, amount: Decimal) -> None:
        """
        Пополняет баланс пользователя на указанную сумму.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance + $1 WHERE user_id = $2",
                amount, user_id
            )

    async def deduct_balance(self, user_id: int, amount: Decimal) -> None:
        """
        Списывает средства с баланса пользователя.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET balance = balance - $1 WHERE user_id = $2",
                amount, user_id
            )

    # ==================== МЕТОДЫ ДЛЯ АККАУНТОВ ====================

    async def get_available_account(
        self, account_type: str, country: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получает первый доступный (не проданный) аккаунт
        по типу и стране.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                """SELECT * FROM accounts 
                   WHERE account_type = $1 
                   AND country = $2 
                   AND is_sold = FALSE 
                   LIMIT 1""",
                account_type, country
            )

    async def mark_account_sold(
        self, account_id: int, user_id: int
    ) -> None:
        """
        Помечает аккаунт как проданный.
        Записывает ID покупателя и время продажи.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """UPDATE accounts 
                   SET is_sold = TRUE, sold_to = $1, sold_at = NOW() 
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
        """
        Добавляет новый аккаунт в базу данных.
        Цены в USDT и TON рассчитываются автоматически.
        Возвращает ID созданного аккаунта.
        """
        pu = calc_usdt(price_rub)
        pt = calc_ton(price_rub)
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                """INSERT INTO accounts 
                   (account_type, country, phone, session_string, 
                    password, price_rub, price_usdt, price_ton)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
                   RETURNING id""",
                account_type, country, phone, session_string,
                password, price_rub, pu, pt
            )

    async def get_account_by_id(
        self, account_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Получает аккаунт по его ID.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM accounts WHERE id = $1", account_id
            )
            return dict(row) if row else None

    async def update_account_code(
        self, account_id: int, code: str
    ) -> None:
        """
        Обновляет код подтверждения для аккаунта.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE accounts SET code = $1 WHERE id = $2",
                code, account_id
            )

    # ==================== МЕТОДЫ ДЛЯ ПОКУПОК ====================

    async def add_purchase(
        self,
        user_id: int,
        account_id: int,
        price: Decimal,
        currency: str
    ) -> int:
        """
        Добавляет запись о покупке.
        Увеличивает счётчик покупок пользователя.
        Возвращает ID покупки.
        """
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

    async def get_user_purchases(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Получает все покупки пользователя с информацией об аккаунтах.
        Сортировка: сначала новые.
        """
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
        """
        Получает конкретную покупку по ID с проверкой владельца.
        Включает session_string для получения кода через Telethon.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT p.*, a.phone, a.code, a.session_string, 
                          a.account_type, a.country
                   FROM purchases p 
                   JOIN accounts a ON p.account_id = a.id 
                   WHERE p.id = $1 AND p.user_id = $2""",
                purchase_id, user_id
            )
            return dict(row) if row else None

    # ==================== МЕТОДЫ ДЛЯ ЦЕН ====================

    async def set_price(
        self,
        account_type: str,
        country: str,
        price_rub: Decimal
    ) -> None:
        """
        Устанавливает цену для конкретного типа и страны.
        USDT и TON рассчитываются автоматически по курсу.
        Обновляет цены у всех непроданных аккаунтов этого типа и страны.
        """
        pu = calc_usdt(price_rub)
        pt = calc_ton(price_rub)
        async with self.pool.acquire() as conn:
            # Обновляем или создаём цену в таблице prices
            await conn.execute(
                """INSERT INTO prices (account_type, country, price_rub) 
                   VALUES ($1, $2, $3)
                   ON CONFLICT (account_type, country) 
                   DO UPDATE SET price_rub = $3""",
                account_type, country, price_rub
            )
            # Обновляем цены у всех непроданных аккаунтов
            await conn.execute(
                """UPDATE accounts 
                   SET price_rub = $1, price_usdt = $2, price_ton = $3 
                   WHERE account_type = $4 AND country = $5 AND is_sold = FALSE""",
                price_rub, pu, pt, account_type, country
            )

    async def get_price(
        self, account_type: str, country: str
    ) -> Dict[str, Any]:
        """
        Получает цену для типа и страны.
        Если цена не установлена, возвращает значения по умолчанию (100 ₽).
        """
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
            # Значения по умолчанию
            default_rub = Decimal("100")
            return {
                "price_rub": default_rub,
                "price_usdt": calc_usdt(default_rub),
                "price_ton": calc_ton(default_rub)
            }

    # ==================== МЕТОДЫ ДЛЯ СТАТИСТИКИ ====================

    async def get_all_users(self) -> List[int]:
        """
        Получает список ID всех пользователей.
        Используется для рассылки.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users")
            return [row["user_id"] for row in rows]

    async def get_stats(self) -> Dict[str, Any]:
        """
        Получает общую статистику:
        - количество пользователей
        - количество аккаунтов (всего/продано/доступно)
        - количество покупок
        """
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

    # ==================== МЕТОДЫ ДЛЯ CRYPTO PAY ====================

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
        """
        Добавляет запись о крипто-платеже.
        Используется для отслеживания статуса оплаты.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO crypto_payments 
                   (invoice_id, user_id, amount, currency, 
                    account_type, country, is_topup)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                invoice_id, user_id, amount, currency,
                account_type, country, is_topup
            )

    async def update_crypto_payment(
        self, invoice_id: str, status: str
    ) -> Optional[Dict[str, Any]]:
        """
        Обновляет статус крипто-платежа.
        Статусы: pending, paid, expired
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "UPDATE crypto_payments SET status = $1 WHERE invoice_id = $2 RETURNING *",
                status, invoice_id
            )

    async def get_pending_crypto_payments(self) -> List[Dict[str, Any]]:
        """
        Получает все ожидающие оплаты крипто-платежи.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM crypto_payments WHERE status = 'pending'"
            )
            return [dict(row) for row in rows]

    async def get_expired_crypto_payments(self) -> List[Dict[str, Any]]:
        """
        Получает просроченные крипто-платежи (старше 10 минут).
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM crypto_payments 
                   WHERE status = 'pending' 
                   AND created_at < NOW() - INTERVAL '10 minutes'"""
            )
            return [dict(row) for row in rows]

    async def get_crypto_payment_by_invoice(
        self, invoice_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о платеже по ID счёта.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM crypto_payments WHERE invoice_id = $1",
                invoice_id
            )
            return dict(row) if row else None


# Создаём экземпляр базы данных
db = Database()


# =====================================================================
# СОСТОЯНИЯ FSM (Finite State Machine)
# =====================================================================

class AdminStates(StatesGroup):
    """
    Состояния для админ-панели.
    Используются для пошагового ввода данных.
    """
    waiting_broadcast = State()              # Ожидание текста рассылки
    waiting_balance_user = State()           # Ожидание ID пользователя
    waiting_balance_amount = State()         # Ожидание суммы для выдачи
    waiting_add_account_phone = State()      # Ожидание номера телефона
    waiting_add_account_code = State()       # Ожидание кода подтверждения
    waiting_add_account_password = State()   # Ожидание 2FA пароля
    waiting_change_price_rub = State()       # Ожидание новой цены в рублях
    waiting_check_invoice = State()          # Ожидание ID счёта для проверки


class TopupStates(StatesGroup):
    """
    Состояния для пополнения баланса.
    """
    waiting_amount_usdt = State()            # Ожидание суммы в USDT
    waiting_amount_ton = State()             # Ожидание суммы в TON
    waiting_amount_ym = State()              # Ожидание суммы в рублях (YooMoney)


# =====================================================================
# CRYPTO PAY API
# =====================================================================

class CryptoPayAPI:
    """
    Класс для работы с API Crypto Bot (https://t.me/CryptoBot).
    Позволяет создавать счета и проверять их статус.
    """

    BASE_URL = "https://pay.crypt.bot/api"

    def __init__(self, token: str):
        """
        Инициализация с токеном от @CryptoBot.
        """
        self.token = token

    async def create_invoice(
        self,
        amount: Decimal,
        currency: str = "USDT",
        description: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        Создаёт счёт на оплату в Crypto Bot.
        Возвращает словарь с информацией о счёте или None при ошибке.
        """
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
                logger.error(f"Crypto Pay API error: {resp.status}")
                return None

    async def get_invoice(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о счёте по его ID.
        Возвращает словарь или None.
        """
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


# Создаём экземпляр API (если токен указан)
crypto_pay = CryptoPayAPI(CRYPTO_BOT_TOKEN) if CRYPTO_BOT_TOKEN else None


# =====================================================================
# YOOMONEY QUICKPAY (без API токена)
# =====================================================================

def create_yoomoney_link(
    amount: Decimal,
    label: str,
    comment: str = ""
) -> str:
    """
    Создаёт ссылку на форму оплаты YooMoney QuickPay.
    Не требует API токена, только номер кошелька.
    
    Параметры:
    - amount: сумма к оплате
    - label: уникальная метка платежа
    - comment: комментарий к платежу
    """
    params = {
        "receiver": YOOMONEY_WALLET,
        "quickpay-form": "shop",
        "targets": comment or "Оплата",
        "paymentType": "AC",  # Банковская карта
        "sum": str(amount),
        "label": label,
    }
    return f"https://yoomoney.ru/quickpay/confirm.xml?{urlencode(params)}"


# =====================================================================
# TELETHON КЛИЕНТ
# =====================================================================

# Создаём глобальный клиент Telethon
telethon_client = TelegramClient(StringSession(), API_ID, API_HASH)


async def fetch_code_from_telegram(session_string: str) -> Optional[str]:
    """
    Получает код подтверждения из аккаунта Telegram.
    
    Алгоритм:
    1. Подключается к аккаунту через session_string
    2. Получает последние 10 диалогов
    3. Ищет в сообщениях 5-6 значные коды
    4. Исключает коды начинающиеся с "20" (годы)
    
    Возвращает код или None если не найден.
    """
    try:
        client = TelegramClient(
            StringSession(session_string),
            API_ID,
            API_HASH
        )
        await client.connect()

        if not await client.is_user_authorized():
            await client.disconnect()
            return None

        # Получаем последние диалоги
        dialogs = await client.get_dialogs(limit=10)

        for dialog in dialogs:
            # Получаем последние 20 сообщений из каждого диалога
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
        logger.error(f"Ошибка получения кода через Telethon: {e}")

    return None


# =====================================================================
# ИНИЦИАЛИЗАЦИЯ БОТА AIOGRAM
# =====================================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())


# =====================================================================
# КЛАВИАТУРЫ БОТА
# =====================================================================

def main_menu_keyboard() -> types.InlineKeyboardMarkup:
    """
    Главное меню бота.
    Содержит кнопки: Купить аккаунт, Профиль, Поддержка, Проекты.
    Все кнопки с premium эмодзи и стилями.
    """
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
            style="success",
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
    """Кнопка возврата в главное меню."""
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
    """Кнопка возврата в профиль."""
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
    """
    Клавиатура профиля пользователя.
    Кнопки: Мои покупки, Пополнить баланс, Проверить оплату, Назад.
    """
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
            text="Проверить оплату",
            callback_data="check_payment",
            style="primary",
            icon_custom_emoji_id=EMOJI["bell"]
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
    """
    Клавиатура выбора типа аккаунта.
    Типы: Новореги, С отлёгой, Прогретые.
    """
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
    account_type: str,
    page: int = 0,
    per_page: int = 8
) -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора страны с пагинацией.
    По 8 стран на странице.
    """
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    builder = InlineKeyboardBuilder()

    # Добавляем кнопки стран
    for country in page_countries:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"country_{account_type}_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )

    # Навигационные кнопки (пагинация)
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

    # Кнопка назад
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="buy_account",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )

    return builder.as_markup()


async def payment_methods_keyboard(
    account_type: str,
    country: str
) -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора способа оплаты.
    Показывает актуальные цены из базы данных.
    """
    price = await db.get_price(account_type, country)

    builder = InlineKeyboardBuilder()

    # Оплата балансом (primary стиль)
    builder.row(
        types.InlineKeyboardButton(
            text=f"Оплатить балансом ({price['price_rub']} ₽)",
            callback_data=f"pay_balance_{account_type}_{country}",
            style="primary",
            icon_custom_emoji_id=EMOJI["wallet"]
        )
    )

    # USDT через Crypto Bot
    builder.row(
        types.InlineKeyboardButton(
            text=f"USDT ({price['price_usdt']} USDT)",
            callback_data=f"pay_usdt_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )

    # TON через Crypto Bot
    builder.row(
        types.InlineKeyboardButton(
            text=f"TON ({price['price_ton']} TON)",
            callback_data=f"pay_ton_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["cryptobot"]
        )
    )

    # YooMoney
    builder.row(
        types.InlineKeyboardButton(
            text=f"YooMoney ({price['price_rub']} ₽)",
            callback_data=f"pay_ym_{account_type}_{country}",
            style="default",
            icon_custom_emoji_id=EMOJI["money"]
        )
    )

    # Кнопка назад
    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data=f"acc_type_{account_type}",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )

    return builder.as_markup()


def get_code_keyboard(purchase_id: int) -> types.InlineKeyboardMarkup:
    """
    Клавиатура для получения кода подтверждения.
    Появляется после успешной покупки.
    """
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
    """
    Клавиатура для выбора способа пополнения баланса.
    """
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
    """
    Клавиатура админ-панели.
    Все кнопки со стилями.
    """
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


def change_price_type_keyboard() -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора типа аккаунта для изменения цен.
    """
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


def countries_price_keyboard(
    account_type: str,
    page: int = 0,
    per_page: int = 8
) -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора страны для изменения цен (с пагинацией).
    """
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    builder = InlineKeyboardBuilder()

    for country in page_countries:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"chprice_country_{account_type}_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )

    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="◁",
                callback_data=f"chprice_page_{account_type}_{page - 1}",
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
                callback_data=f"chprice_page_{account_type}_{page + 1}",
                icon_custom_emoji_id=EMOJI["send"]
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="admin_change_price",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


def add_account_type_keyboard() -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора типа аккаунта при добавлении.
    """
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


def countries_add_keyboard(
    page: int = 0,
    per_page: int = 8
) -> types.InlineKeyboardMarkup:
    """
    Клавиатура выбора страны при добавлении аккаунта (с пагинацией).
    """
    countries = list(COUNTRY_NAMES.keys())
    total_pages = (len(countries) + per_page - 1) // per_page

    start = page * per_page
    end = start + per_page
    page_countries = countries[start:end]

    builder = InlineKeyboardBuilder()

    for country in page_countries:
        builder.row(
            types.InlineKeyboardButton(
                text=COUNTRY_NAMES[country],
                callback_data=f"addacc_country_{country}",
                icon_custom_emoji_id=EMOJI[country]
            )
        )

    # Пагинация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                text="◁",
                callback_data=f"addacc_page_{page - 1}",
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
                callback_data=f"addacc_page_{page + 1}",
                icon_custom_emoji_id=EMOJI["send"]
            )
        )
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        types.InlineKeyboardButton(
            text="◁ Назад",
            callback_data="admin_add_account",
            icon_custom_emoji_id=EMOJI["down"]
        )
    )
    return builder.as_markup()


# =====================================================================
# ОБРАБОТЧИКИ КОМАНД
# =====================================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start.
    Приветствует пользователя и показывает главное меню.
    """
    await db.get_or_create_user(message.from_user.id, message.from_user.username)

    welcome_text = (
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'Добро пожаловать в Vest Traff Accs!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Покупка аккаунтов Telegram с разных стран\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите действие в меню:'
    )
    await message.answer(welcome_text, reply_markup=main_menu_keyboard())


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    """
    Обработчик команды /admin.
    Доступен только администраторам.
    """
    if message.from_user.id not in ADMIN_IDS:
        logger.warning(f"Попытка доступа к /admin от {message.from_user.id}")
        return

    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["settings"]}">⚙</tg-emoji> '
        f'Админ панель</b>\n\nВыберите действие:',
        reply_markup=admin_panel_keyboard()
    )


# =====================================================================
# ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ
# =====================================================================

@dp.callback_query(F.data == "main_menu")
async def main_menu_callback(callback: CallbackQuery):
    """
    Обработчик возврата в главное меню.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["bot"]}">🤖</tg-emoji> '
        f'Главное меню</b>\n\nВыберите действие:',
        reply_markup=main_menu_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "projects")
async def projects_callback(callback: CallbackQuery):
    """
    Обработчик раздела Проекты.
    Показывает список проектов и канал.
    """
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
    """
    Обработчик раздела Поддержка.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Поддержка</b>\n\n'
        f'По всем вопросам обращайтесь:\n'
        f'@VestSupport',
        reply_markup=back_to_main_keyboard()
    )
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ ПРОФИЛЯ
# =====================================================================

@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):
    """
    Обработчик просмотра профиля.
    Показывает юзернейм, ID, баланс и количество покупок.
    """
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
        f'<b>Количество покупок:</b> {user["purchases_count"]}'
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard())
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ МОИХ ПОКУПОК
# =====================================================================

@dp.callback_query(F.data == "my_purchases")
async def my_purchases_callback(callback: CallbackQuery):
    """
    Обработчик списка покупок пользователя.
    Показывает дату, номер телефона, цену и кнопку получения кода.
    """
    purchases = await db.get_user_purchases(callback.from_user.id)

    if not purchases:
        text = (
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
            f'Мои покупки</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'У вас пока нет покупок.'
        )
        await callback.message.edit_text(
            text,
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


# =====================================================================
# ОБРАБОТЧИКИ ПОЛУЧЕНИЯ КОДА
# =====================================================================

@dp.callback_query(F.data.startswith("get_code_"))
async def get_code_callback(callback: CallbackQuery):
    """
    Обработчик получения кода подтверждения.
    Пытается получить свежий код через Telethon,
    затем проверяет сохранённый код в базе данных.
    """
    purchase_id = int(callback.data.split("_")[2])
    purchase = await db.get_purchase_by_id(purchase_id, callback.from_user.id)

    if not purchase:
        await callback.answer("Покупка не найдена", show_alert=True)
        return

    # Сообщаем пользователю что ищем код
    await callback.answer()
    status_msg = await callback.message.answer(
        f'<tg-emoji emoji-id="{EMOJI["loading"]}">🔄</tg-emoji> '
        f'Ищу код подтверждения...'
    )

    # Пытаемся получить свежий код через Telethon
    session_string = purchase.get("session_string")
    if session_string:
        code = await fetch_code_from_telegram(session_string)
        if code:
            # Сохраняем код в базу
            await db.update_account_code(purchase["account_id"], code)
            await status_msg.edit_text(
                f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
                f'Код подтверждения:</b>\n\n'
                f'<code>{code}</code>\n\n'
                f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
                f'<b>Номер:</b> <code>{purchase["phone"]}</code>'
            )
            return

    # Если есть сохранённый код в базе
    if purchase.get("code"):
        await status_msg.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
            f'Код подтверждения:</b>\n\n'
            f'<code>{purchase["code"]}</code>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
            f'<b>Номер:</b> <code>{purchase["phone"]}</code>'
        )
        return

    # Код не найден нигде
    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Код пока не получен. Попробуйте позже или обратитесь '
        f'в поддержку @VestSupport'
    )


# =====================================================================
# ОБРАБОТЧИКИ ПОПОЛНЕНИЯ БАЛАНСА
# =====================================================================

@dp.callback_query(F.data == "top_up")
async def top_up_callback(callback: CallbackQuery):
    """
    Обработчик меню пополнения баланса.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'Пополнение баланса</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите способ пополнения:',
        reply_markup=topup_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data == "topup_crypto_usdt")
async def topup_crypto_usdt_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик пополнения USDT через Crypto Bot.
    Запрашивает сумму у пользователя.
    """
    if not crypto_pay:
        await callback.answer(
            "Crypto Pay не настроен",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
        f'Пополнение USDT</b>\n\n'
        f'Отправьте сумму в USDT:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_usdt)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_usdt)
async def process_topup_usdt(message: Message, state: FSMContext):
    """
    Обработчик получения суммы USDT.
    Создаёт счёт в Crypto Bot и отправляет ссылку на оплату.
    """
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        await state.clear()
        return

    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer(
            "Неверная сумма. Отправьте число (например: 10.5):"
        )
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    # Создаём счёт в Crypto Bot
    invoice = await crypto_pay.create_invoice(
        amount,
        "USDT",
        f"Пополнение баланса {message.from_user.id}"
    )

    if invoice:
        # Сохраняем платёж в базу
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


@dp.callback_query(F.data == "topup_crypto_ton")
async def topup_crypto_ton_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик пополнения TON через Crypto Bot.
    Запрашивает сумму у пользователя.
    """
    if not crypto_pay:
        await callback.answer(
            "Crypto Pay не настроен",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
        f'Пополнение TON</b>\n\n'
        f'Отправьте сумму в TON:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ton)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_ton)
async def process_topup_ton(message: Message, state: FSMContext):
    """
    Обработчик получения суммы TON.
    Создаёт счёт в Crypto Bot и отправляет ссылку на оплату.
    """
    if not crypto_pay:
        await message.answer("Crypto Pay не настроен")
        await state.clear()
        return

    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer(
            "Неверная сумма. Отправьте число (например: 5.5):"
        )
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    invoice = await crypto_pay.create_invoice(
        amount,
        "TON",
        f"Пополнение баланса {message.from_user.id}"
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


@dp.callback_query(F.data == "topup_yoomoney")
async def topup_yoomoney_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик пополнения через YooMoney.
    Запрашивает сумму у пользователя.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Пополнение YooMoney</b>\n\n'
        f'Отправьте сумму в рублях:',
        reply_markup=back_to_profile_keyboard()
    )
    await state.set_state(TopupStates.waiting_amount_ym)
    await callback.answer()


@dp.message(TopupStates.waiting_amount_ym)
async def process_topup_ym(message: Message, state: FSMContext):
    """
    Обработчик получения суммы для YooMoney.
    Создаёт ссылку на форму оплаты.
    """
    try:
        amount = Decimal(message.text.strip())
    except (ValueError, InvalidOperation):
        await message.answer(
            "Неверная сумма. Отправьте число (например: 500):"
        )
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return

    # Создаём уникальную метку и ссылку на оплату
    label = f"topup_{message.from_user.id}_{uuid.uuid4().hex[:8]}"
    payment_link = create_yoomoney_link(
        amount,
        label,
        f"Пополнение баланса {message.from_user.id}"
    )

    await message.answer(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Пополнение YooMoney</b>\n\n'
        f'Сумма: {amount} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'После оплаты отправьте чек в @VestSupport\n'
        f'Баланс будет пополнен после проверки.',
        reply_markup=profile_keyboard()
    )

    await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ ПРОВЕРКИ ОПЛАТЫ
# =====================================================================

@dp.callback_query(F.data == "check_payment")
async def check_payment_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик кнопки "Проверить оплату" в профиле.
    Запрашивает ID счёта (invoice_id).
    """
    if not crypto_pay:
        await callback.answer(
            "Crypto Pay не настроен",
            show_alert=True
        )
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
    """
    Обработчик проверки статуса счёта.
    Проверяет в базе данных и через API Crypto Bot.
    """
    invoice_id = message.text.strip()

    # Ищем платёж в базе
    payment = await db.get_crypto_payment_by_invoice(invoice_id)

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
        # Оплата прошла
        await db.update_crypto_payment(invoice_id, "paid")

        if payment["is_topup"]:
            # Пополнение баланса
            await db.add_balance(payment["user_id"], payment["amount"])
            await message.answer(
                f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
                f'Оплата подтверждена!\n'
                f'Баланс пополнен на {payment["amount"]} {payment["currency"]}',
                reply_markup=profile_keyboard()
            )

        elif payment["account_type"] and payment["country"]:
            # Покупка аккаунта
            account = await db.get_available_account(
                payment["account_type"],
                payment["country"]
            )
            if account:
                await db.mark_account_sold(account["id"], payment["user_id"])
                purchase_id = await db.add_purchase(
                    payment["user_id"],
                    account["id"],
                    payment["amount"],
                    payment["currency"]
                )
                await message.answer(
                    f'<tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
                    f'Оплата подтверждена!\n'
                    f'<code>{account["phone"]}</code>',
                    reply_markup=get_code_keyboard(purchase_id)
                )
            else:
                await message.answer(
                    f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
                    f'Аккаунты закончились. Обратитесь в поддержку',
                    reply_markup=profile_keyboard()
                )
    else:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'Оплата ещё не прошла. Попробуйте позже.',
            reply_markup=profile_keyboard()
        )

    await state.clear()


# =====================================================================
# ОБРАБОТЧИКИ ПОКУПКИ АККАУНТА
# =====================================================================

@dp.callback_query(F.data == "buy_account")
async def buy_account_callback(callback: CallbackQuery):
    """
    Обработчик начала процесса покупки.
    Показывает выбор типа аккаунта.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'Купить аккаунт</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'Выберите тип аккаунта:',
        reply_markup=account_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("acc_type_"))
async def account_type_callback(callback: CallbackQuery):
    """
    Обработчик выбора типа аккаунта.
    Показывает выбор страны.
    """
    account_type = callback.data.split("_")[2]

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите страну:',
        reply_markup=countries_keyboard(account_type, 0)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("page_"))
async def countries_page_callback(callback: CallbackQuery):
    """
    Обработчик пагинации стран при выборе.
    """
    parts = callback.data.split("_")
    account_type = parts[1]
    page = int(parts[2])

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите страну:',
        reply_markup=countries_keyboard(account_type, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("country_"))
async def country_callback(callback: CallbackQuery):
    """
    Обработчик выбора страны.
    Проверяет наличие аккаунтов и показывает способы оплаты.
    """
    parts = callback.data.split("_")
    account_type = parts[1]
    country = parts[2]

    # Получаем цену и проверяем наличие
    price = await db.get_price(account_type, country)
    account = await db.get_available_account(account_type, country)

    if not account:
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
            f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'<b>Нет в наличии</b>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
            f'Попробуйте другую страну или тип аккаунта.',
            reply_markup=countries_keyboard(account_type, 0)
        )
        await callback.answer("Нет в наличии", show_alert=True)
        return

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'{ACCOUNT_TYPES[account_type]} - {COUNTRY_NAMES[country]}</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'<b>Цены:</b>\n'
        f'• {price["price_rub"]} ₽\n'
        f'• {price["price_usdt"]} USDT\n'
        f'• {price["price_ton"]} TON\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'Выберите способ оплаты:',
        reply_markup=await payment_methods_keyboard(account_type, country)
    )
    await callback.answer()


# =====================================================================
# ОБРАБОТЧИКИ ОПЛАТЫ БАЛАНСОМ
# =====================================================================

@dp.callback_query(F.data.startswith("pay_balance_"))
async def pay_balance_callback(callback: CallbackQuery):
    """
    Обработчик оплаты внутренним балансом.
    Списывает рубли и сразу выдаёт аккаунт.
    """
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    price = await db.get_price(account_type, country)
    user = await db.get_user(callback.from_user.id)

    # Проверяем достаточно ли средств
    if user["balance"] < price["price_rub"]:
        await callback.answer(
            f"Недостаточно средств. Баланс: {user['balance']} ₽, "
            f"необходимо: {price['price_rub']} ₽",
            show_alert=True
        )
        return

    # Проверяем наличие
    account = await db.get_available_account(account_type, country)
    if not account:
        await callback.answer("Аккаунты закончились", show_alert=True)
        return

    # Списываем средства
    await db.deduct_balance(callback.from_user.id, price["price_rub"])

    # Помечаем аккаунт как проданный
    await db.mark_account_sold(account["id"], callback.from_user.id)

    # Записываем покупку
    purchase_id = await db.add_purchase(
        callback.from_user.id,
        account["id"],
        price["price_rub"],
        "RUB"
    )

    new_balance = user["balance"] - price["price_rub"]

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
        f'Покупка успешна!</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'<b>Номер:</b> <code>{account["phone"]}</code>\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'<b>Списано с баланса:</b> {price["price_rub"]} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
        f'<b>Остаток:</b> {new_balance} ₽\n'
        f'<tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> '
        f'<b>Дата:</b> {format_date(msk_time())}',
        reply_markup=get_code_keyboard(purchase_id)
    )
    await callback.answer("Покупка успешна!", show_alert=True)


# =====================================================================
# ОБРАБОТЧИКИ ОПЛАТЫ КРИПТОВАЛЮТОЙ
# =====================================================================

@dp.callback_query(F.data.startswith("pay_usdt_"))
async def pay_usdt_callback(callback: CallbackQuery):
    """
    Обработчик оплаты USDT.
    Создаёт счёт в Crypto Bot.
    """
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
        price["price_usdt"],
        "USDT",
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            callback.from_user.id,
            price["price_usdt"],
            "USDT",
            account_type,
            country
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Оплата USDT</b>\n\n'
            f'Сумма: {price["price_usdt"]} USDT\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=back_to_main_keyboard()
        )
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


@dp.callback_query(F.data.startswith("pay_ton_"))
async def pay_ton_callback(callback: CallbackQuery):
    """
    Обработчик оплаты TON.
    Создаёт счёт в Crypto Bot.
    """
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
        price["price_ton"],
        "TON",
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    if invoice:
        await db.add_crypto_payment(
            str(invoice["invoice_id"]),
            callback.from_user.id,
            price["price_ton"],
            "TON",
            account_type,
            country
        )

        pay_url = invoice.get("pay_url") or invoice.get("bot_invoice_url", "")
        await callback.message.edit_text(
            f'<b><tg-emoji emoji-id="{EMOJI["cryptobot"]}">👾</tg-emoji> '
            f'Оплата TON</b>\n\n'
            f'Сумма: {price["price_ton"]} TON\n\n'
            f'<a href="{pay_url}">Нажмите для оплаты</a>\n\n'
            f'<tg-emoji emoji-id="{EMOJI["clock"]}">⏰</tg-emoji> '
            f'Счёт действителен 10 минут\n'
            f'<tg-emoji emoji-id="{EMOJI["bell"]}">🔔</tg-emoji> '
            f'Проверить оплату можно в профиле',
            reply_markup=back_to_main_keyboard()
        )
    else:
        await callback.answer("Ошибка создания счёта", show_alert=True)


# =====================================================================
# ОБРАБОТЧИКИ ОПЛАТЫ YOOMONEY
# =====================================================================

@dp.callback_query(F.data.startswith("pay_ym_"))
async def pay_yoomoney_callback(callback: CallbackQuery):
    """
    Обработчик оплаты через YooMoney.
    Создаёт ссылку на форму оплаты.
    """
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
        price["price_rub"],
        label,
        f"Покупка {ACCOUNT_TYPES[account_type]} {COUNTRY_NAMES[country]}"
    )

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'Оплата YooMoney</b>\n\n'
        f'Сумма к оплате: {price["price_rub"]} ₽\n\n'
        f'<a href="{payment_link}">Нажмите для оплаты</a>\n\n'
        f'Тип: {ACCOUNT_TYPES[account_type]}\n'
        f'Страна: {COUNTRY_NAMES[country]}\n\n'
        f'<tg-emoji emoji-id="{EMOJI["info"]}">ℹ</tg-emoji> '
        f'После оплаты отправьте чек в @VestSupport\n'
        f'Аккаунт будет выдан после проверки платежа.',
        reply_markup=back_to_main_keyboard()
    )
    await callback.answer()


# =====================================================================
# ФОНОВАЯ ПРОВЕРКА CRYPTO ПЛАТЕЖЕЙ
# =====================================================================

async def check_crypto_payments_loop():
    """
    Бесконечный цикл проверки крипто-платежей.
    Запускается каждые 5 секунд.
    - Отменяет просроченные счета (старше 10 минут)
    - Проверяет статус pending платежей
    - При успешной оплате: пополняет баланс или выдаёт аккаунт
    """
    logger.info("Запущена фоновая проверка крипто-платежей")

    while True:
        await asyncio.sleep(5)

        if not crypto_pay:
            continue

        try:
            # Отменяем просроченные счета
            expired_payments = await db.get_expired_crypto_payments()
            for payment in expired_payments:
                await db.update_crypto_payment(payment["invoice_id"], "expired")
                try:
                    await bot.send_message(
                        payment["user_id"],
                        f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
                        f'Время оплаты истекло. Счёт аннулирован.'
                    )
                except Exception:
                    pass

            # Проверяем pending платежи
            pending_payments = await db.get_pending_crypto_payments()
            for payment in pending_payments:
                invoice = await crypto_pay.get_invoice(
                    int(payment["invoice_id"])
                )

                if invoice and invoice.get("status") == "paid":
                    # Обновляем статус в базе
                    await db.update_crypto_payment(
                        payment["invoice_id"],
                        "paid"
                    )

                    if payment["is_topup"]:
                        # Пополнение баланса
                        await db.add_balance(
                            payment["user_id"],
                            payment["amount"]
                        )
                        try:
                            await bot.send_message(
                                payment["user_id"],
                                f'<b><tg-emoji emoji-id="{EMOJI["wallet"]}">👛</tg-emoji> '
                                f'Баланс пополнен!</b>\n\n'
                                f'+{payment["amount"]} {payment["currency"]}\n'
                                f'<tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
                                f'Спасибо!'
                            )
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления: {e}")

                    elif payment["account_type"] and payment["country"]:
                        # Покупка аккаунта
                        account = await db.get_available_account(
                            payment["account_type"],
                            payment["country"]
                        )
                        if account:
                            await db.mark_account_sold(
                                account["id"],
                                payment["user_id"]
                            )
                            purchase_id = await db.add_purchase(
                                payment["user_id"],
                                account["id"],
                                payment["amount"],
                                payment["currency"]
                            )
                            try:
                                await bot.send_message(
                                    payment["user_id"],
                                    f'<b><tg-emoji emoji-id="{EMOJI["celebrate"]}">🎉</tg-emoji> '
                                    f'Покупка успешна!</b>\n\n'
                                    f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
                                    f'<b>Номер:</b> <code>{account["phone"]}</code>\n'
                                    f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
                                    f'<b>Оплачено:</b> {payment["amount"]} {payment["currency"]}\n'
                                    f'<tg-emoji emoji-id="{EMOJI["calendar"]}">📅</tg-emoji> '
                                    f'<b>Дата:</b> {format_date(msk_time())}',
                                    reply_markup=get_code_keyboard(purchase_id)
                                )
                            except Exception as e:
                                logger.error(f"Ошибка отправки аккаунта: {e}")

        except Exception as e:
            logger.error(f"Ошибка в цикле проверки платежей: {e}")


# =====================================================================
# АДМИН ПАНЕЛЬ - СТАТИСТИКА
# =====================================================================

@dp.callback_query(F.data == "admin_stats", F.from_user.id.in_(ADMIN_IDS))
async def admin_stats_callback(callback: CallbackQuery):
    """
    Обработчик просмотра статистики в админ-панели.
    """
    stats = await db.get_stats()

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["stats"]}">📊</tg-emoji> '
        f'Статистика</b>\n\n'
        f'<tg-emoji emoji-id="{EMOJI["profile"]}">👤</tg-emoji> '
        f'<b>Пользователей:</b> {stats["total_users"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["box"]}">📦</tg-emoji> '
        f'<b>Аккаунтов всего:</b> {stats["total_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'<b>Продано:</b> {stats["sold_accounts"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["tag"]}">🏷</tg-emoji> '
        f'<b>Доступно:</b> {stats["available"]}\n'
        f'<tg-emoji emoji-id="{EMOJI["money"]}">🪙</tg-emoji> '
        f'<b>Всего покупок:</b> {stats["total_purchases"]}',
        reply_markup=admin_panel_keyboard()
    )
    await callback.answer()


# =====================================================================
# АДМИН ПАНЕЛЬ - РАССЫЛКА
# =====================================================================

@dp.callback_query(F.data == "admin_broadcast", F.from_user.id.in_(ADMIN_IDS))
async def admin_broadcast_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик начала рассылки.
    Запрашивает сообщение для отправки всем пользователям.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["megaphone"]}">📣</tg-emoji> '
        f'Рассылка</b>\n\n'
        f'Отправьте сообщение, которое хотите разослать всем пользователям.',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminStates.waiting_broadcast)
    await callback.answer()


@dp.message(AdminStates.waiting_broadcast, F.from_user.id.in_(ADMIN_IDS))
async def process_broadcast(message: Message, state: FSMContext):
    """
    Обработчик выполнения рассылки.
    Отправляет сообщение всем пользователям с задержкой 0.05 сек.
    """
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
        await asyncio.sleep(0.05)  # Задержка для избежания флуда

    await status_msg.edit_text(
        f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
        f'<b>Рассылка завершена!</b>\n\n'
        f'Успешно: {sent}\n'
        f'Ошибок: {failed}\n'
        f'Всего пользователей: {len(users)}',
        reply_markup=admin_panel_keyboard()
    )
    await state.clear()


# =====================================================================
# АДМИН ПАНЕЛЬ - ВЫДАТЬ БАЛАНС
# =====================================================================

@dp.callback_query(F.data == "admin_give_balance", F.from_user.id.in_(ADMIN_IDS))
async def admin_give_balance_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выдачи баланса пользователю.
    Запрашивает ID пользователя.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["money_send"]}">🪙</tg-emoji> '
        f'Выдать баланс</b>\n\n'
        f'Отправьте ID пользователя:',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminStates.waiting_balance_user)
    await callback.answer()


@dp.message(AdminStates.waiting_balance_user, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_user(message: Message, state: FSMContext):
    """
    Обработчик получения ID пользователя.
    Проверяет существование пользователя и запрашивает сумму.
    """
    try:
        user_id = int(message.text.strip())
        user = await db.get_user(user_id)

        if not user:
            await message.answer(
                f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
                f'Пользователь не найден'
            )
            return

        await state.update_data(balance_user_id=user_id)
        await message.answer(
            f'Пользователь: @{user.get("username") or user_id} '
            f'(ID: {user_id})\n\n'
            f'Отправьте сумму для пополнения:'
        )
        await state.set_state(AdminStates.waiting_balance_amount)

    except ValueError:
        await message.answer("Неверный ID пользователя")


@dp.message(AdminStates.waiting_balance_amount, F.from_user.id.in_(ADMIN_IDS))
async def process_balance_amount(message: Message, state: FSMContext):
    """
    Обработчик получения суммы и пополнения баланса.
    """
    try:
        amount = Decimal(message.text.strip())

        if amount <= 0:
            await message.answer("Сумма должна быть больше 0")
            return

        data = await state.get_data()
        user_id = data["balance_user_id"]

        await db.add_balance(user_id, amount)

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Баланс пользователя {user_id} пополнен на {amount} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()

    except (ValueError, InvalidOperation):
        await message.answer("Неверная сумма")


# =====================================================================
# АДМИН ПАНЕЛЬ - ДОБАВИТЬ АККАУНТ
# =====================================================================

@dp.callback_query(F.data == "admin_add_account", F.from_user.id.in_(ADMIN_IDS))
async def admin_add_account_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик начала добавления аккаунта.
    Показывает выбор типа аккаунта.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> '
        f'Добавить аккаунт</b>\n\n'
        f'Выберите тип аккаунта:',
        reply_markup=add_account_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_type_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_type_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора типа аккаунта при добавлении.
    """
    account_type = callback.data.split("_")[2]
    await state.update_data(add_account_type=account_type)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> '
        f'Тип: {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_add_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_page_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_page_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик пагинации стран при добавлении аккаунта.
    """
    page = int(callback.data.split("_")[2])
    data = await state.get_data()

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> '
        f'Тип: {ACCOUNT_TYPES.get(data.get("add_account_type", ""), "")}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_add_keyboard(page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("addacc_country_"), F.from_user.id.in_(ADMIN_IDS))
async def addacc_country_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора страны при добавлении.
    Запрашивает номер телефона.
    """
    country = callback.data.split("_")[2]
    await state.update_data(add_account_country=country)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["add_text"]}">🔡</tg-emoji> '
        f'Страна: {COUNTRY_NAMES[country]}</b>\n\n'
        f'Отправьте номер телефона в формате +79001234567:',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminStates.waiting_add_account_phone)
    await callback.answer()


@dp.message(AdminStates.waiting_add_account_phone, F.from_user.id.in_(ADMIN_IDS))
async def addacc_phone_handler(message: Message, state: FSMContext):
    """
    Обработчик получения номера телефона.
    Отправляет код подтверждения через Telethon.
    """
    phone = message.text.strip()

    if not phone.startswith("+"):
        await message.answer("Номер должен начинаться с +")
        return

    await state.update_data(add_account_phone=phone)

    try:
        # Создаём новый клиент Telethon для этого аккаунта
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()

        # Отправляем запрос кода
        sent = await client.send_code_request(phone)

        # Сохраняем клиент и хеш в состоянии
        await state.update_data(
            add_account_client=client,
            add_account_phone_hash=sent.phone_code_hash
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["code"]}">🔨</tg-emoji> '
            f'Отправьте код подтверждения с номера {phone}:'
        )
        await state.set_state(AdminStates.waiting_add_account_code)

    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'Ошибка: {e}'
        )
        await state.clear()


@dp.message(AdminStates.waiting_add_account_code, F.from_user.id.in_(ADMIN_IDS))
async def addacc_code_handler(message: Message, state: FSMContext):
    """
    Обработчик получения кода подтверждения.
    Авторизует аккаунт и сохраняет сессию.
    """
    code = message.text.strip()
    data = await state.get_data()
    client = data.get("add_account_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        # Авторизуемся с кодом
        await client.sign_in(
            phone=data["add_account_phone"],
            code=code,
            phone_code_hash=data["add_account_phone_hash"]
        )

        # Получаем сессию
        session_string = client.session.save()
        await client.disconnect()

        # Добавляем аккаунт в базу
        account_type = data["add_account_type"]
        country = data["add_account_country"]
        price = await db.get_price(account_type, country)

        await db.add_account(
            account_type,
            country,
            data["add_account_phone"],
            session_string=session_string,
            price_rub=price["price_rub"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Аккаунт {data["add_account_phone"]} успешно добавлен!\n'
            f'Тип: {ACCOUNT_TYPES[account_type]}\n'
            f'Страна: {COUNTRY_NAMES[country]}\n'
            f'Цена: {price["price_rub"]} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()

    except SessionPasswordNeededError:
        # Требуется 2FA пароль
        await state.update_data(add_account_client=client)
        await message.answer("Требуется 2FA пароль. Отправьте пароль:")
        await state.set_state(AdminStates.waiting_add_account_password)

    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'Ошибка: {e}'
        )
        if client:
            await client.disconnect()
        await state.clear()


@dp.message(AdminStates.waiting_add_account_password, F.from_user.id.in_(ADMIN_IDS))
async def addacc_password_handler(message: Message, state: FSMContext):
    """
    Обработчик 2FA пароля при добавлении аккаунта.
    """
    password = message.text.strip()
    data = await state.get_data()
    client = data.get("add_account_client")

    if not client:
        await message.answer("Сессия истекла, начните заново")
        await state.clear()
        return

    try:
        # Авторизуемся с паролем
        await client.sign_in(password=password)

        # Получаем сессию
        session_string = client.session.save()
        await client.disconnect()

        # Добавляем аккаунт в базу
        account_type = data["add_account_type"]
        country = data["add_account_country"]
        price = await db.get_price(account_type, country)

        await db.add_account(
            account_type,
            country,
            data["add_account_phone"],
            session_string=session_string,
            price_rub=price["price_rub"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Аккаунт {data["add_account_phone"]} успешно добавлен!',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()

    except Exception as e:
        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["cross"]}">❌</tg-emoji> '
            f'Ошибка: {e}'
        )
        if client:
            await client.disconnect()
        await state.clear()


# =====================================================================
# АДМИН ПАНЕЛЬ - ИЗМЕНИТЬ ЦЕНЫ
# =====================================================================

@dp.callback_query(F.data == "admin_change_price", F.from_user.id.in_(ADMIN_IDS))
async def admin_change_price_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик изменения цен.
    Показывает выбор типа аккаунта.
    """
    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> '
        f'Изменение цен</b>\n\n'
        f'Выберите тип аккаунта:',
        reply_markup=change_price_type_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_type_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_type_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора типа аккаунта для изменения цены.
    """
    account_type = callback.data.split("_")[2]
    await state.update_data(change_price_type=account_type)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> '
        f'Тип: {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_price_keyboard(account_type)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_page_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_page_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик пагинации стран при изменении цен.
    """
    parts = callback.data.split("_")
    account_type = parts[2]
    page = int(parts[3])

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> '
        f'Тип: {ACCOUNT_TYPES[account_type]}</b>\n\n'
        f'Выберите страну:',
        reply_markup=countries_price_keyboard(account_type, page)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("chprice_country_"), F.from_user.id.in_(ADMIN_IDS))
async def chprice_country_callback(
    callback: CallbackQuery,
    state: FSMContext
):
    """
    Обработчик выбора страны для изменения цены.
    Показывает текущую цену и запрашивает новую.
    """
    parts = callback.data.split("_")
    account_type = parts[2]
    country = parts[3]

    await state.update_data(
        change_price_type=account_type,
        change_price_country=country
    )

    current_price = await db.get_price(account_type, country)

    await callback.message.edit_text(
        f'<b><tg-emoji emoji-id="{EMOJI["pencil"]}">🖋</tg-emoji> '
        f'Страна: {COUNTRY_NAMES[country]}</b>\n\n'
        f'Текущая цена: {current_price["price_rub"]} ₽\n\n'
        f'Отправьте новую цену в рублях:',
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminStates.waiting_change_price_rub)
    await callback.answer()


@dp.message(AdminStates.waiting_change_price_rub, F.from_user.id.in_(ADMIN_IDS))
async def chprice_rub_handler(message: Message, state: FSMContext):
    """
    Обработчик получения новой цены.
    Сохраняет цену и автоматически пересчитывает USDT и TON.
    """
    try:
        price_rub = Decimal(message.text.strip())

        if price_rub <= 0:
            await message.answer("Цена должна быть больше 0")
            return

        data = await state.get_data()

        # Сохраняем новую цену
        await db.set_price(
            data["change_price_type"],
            data["change_price_country"],
            price_rub
        )

        # Получаем обновлённые цены для отображения
        new_price = await db.get_price(
            data["change_price_type"],
            data["change_price_country"]
        )

        await message.answer(
            f'<tg-emoji emoji-id="{EMOJI["check"]}">✅</tg-emoji> '
            f'Цена для {ACCOUNT_TYPES[data["change_price_type"]]} - '
            f'{COUNTRY_NAMES[data["change_price_country"]]} обновлена!\n\n'
            f'Новая цена: {new_price["price_rub"]} ₽',
            reply_markup=admin_panel_keyboard()
        )
        await state.clear()

    except (ValueError, InvalidOperation):
        await message.answer("Неверное число. Отправьте цену ещё раз:")


# =====================================================================
# ИГНОР ДЛЯ НЕАКТИВНЫХ КНОПОК
# =====================================================================

@dp.callback_query(F.data == "ignore")
async def ignore_callback(callback: CallbackQuery):
    """
    Игнорирует нажатия на неактивные кнопки (например, индикатор страницы).
    """
    await callback.answer()


# =====================================================================
# ЗАПУСК БОТА
# =====================================================================

async def main():
    """
    Главная функция запуска бота.
    1. Подключается к базе данных
    2. Инициализирует таблицы
    3. Подключает Telethon
    4. Запускает фоновую проверку платежей
    5. Запускает поллинг бота
    """
    logger.info("=" * 50)
    logger.info("Запуск бота Vest Traff Accs...")

    # Подключаемся к базе данных
    await db.connect()
    await db.init_tables()
    logger.info("База данных готова")

    # Подключаем Telethon
    await telethon_client.connect()
    logger.info("Telethon подключён")

    # Запускаем фоновую проверку платежей
    asyncio.create_task(check_crypto_payments_loop())
    logger.info("Фоновая проверка платежей запущена")

    # Удаляем вебхук и запускаем поллинг
    await bot(DeleteWebhook(drop_pending_updates=True))

    logger.info("=" * 50)
    logger.info("Бот Vest Traff Accs успешно запущен!")
    logger.info(f"Внутренний курс: 1 USDT = {USDT_RATE} ₽")
    logger.info(f"Внутренний курс: 1 TON = {TON_RATE} ₽")
    logger.info(f"Кошелёк YooMoney: {YOOMONEY_WALLET}")
    logger.info("=" * 50)

    # Запускаем поллинг обновлений
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
