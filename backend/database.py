import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

from config import get_settings

DATABASE_PATH = Path("./data/kanban.db")


def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    settings = get_settings()
    return Fernet(settings.encryption_key)


def encrypt_data(data: dict) -> str:
    """Encrypt sensitive data like tokens."""
    fernet = get_fernet()
    return fernet.encrypt(json.dumps(data).encode()).decode()


def decrypt_data(encrypted: str) -> dict:
    """Decrypt sensitive data."""
    fernet = get_fernet()
    return json.loads(fernet.decrypt(encrypted.encode()).decode())


async def init_db():
    """Initialize database with tables."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Accounts table - stores OAuth tokens and settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                email TEXT,
                color TEXT DEFAULT '#0078d4',
                config TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Items table - cached emails and tasks
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                type TEXT NOT NULL,
                title TEXT,
                sender TEXT,
                content TEXT,
                date TEXT,
                data JSON,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for faster queries
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_account_id ON items(account_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_date ON items(date)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_items_type ON items(type)
        """)

        # Settings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.commit()


async def get_db():
    """Get database connection."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db


# Account operations
async def create_account(
    id: str,
    name: str,
    provider: str,
    email: str = "",
    color: str = "#0078d4",
    config: dict = None
) -> dict:
    """Create a new account."""
    encrypted_config = encrypt_data(config or {})

    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO accounts (id, name, provider, email, color, config)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, name, provider, email, color, encrypted_config)
        )
        await db.commit()

    return {
        "id": id,
        "name": name,
        "provider": provider,
        "email": email,
        "color": color
    }


async def get_account(account_id: str) -> Optional[dict]:
    """Get account by ID."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account_id,)
        )
        row = await cursor.fetchone()

        if row:
            account = dict(row)
            if account.get("config"):
                account["config"] = decrypt_data(account["config"])
            return account
        return None


async def get_all_accounts() -> list:
    """Get all accounts (without sensitive config)."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, name, provider, email, color, created_at FROM accounts ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_account(account_id: str, **kwargs) -> bool:
    """Update account fields."""
    # Handle config separately for encryption
    config = kwargs.pop("config", None)

    async with aiosqlite.connect(DATABASE_PATH) as db:
        if kwargs:
            fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
            values = list(kwargs.values()) + [account_id]
            await db.execute(
                f"UPDATE accounts SET {fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )

        if config is not None:
            encrypted_config = encrypt_data(config)
            await db.execute(
                "UPDATE accounts SET config = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (encrypted_config, account_id)
            )

        await db.commit()
        return True


async def delete_account(account_id: str) -> bool:
    """Delete account and its cached items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM items WHERE account_id = ?", (account_id,))
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()
        return True


# Item (email/task) operations
async def upsert_items(account_id: str, item_type: str, items: list):
    """Insert or update cached items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for item in items:
            await db.execute(
                """
                INSERT OR REPLACE INTO items (id, account_id, type, title, sender, content, date, data, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    item.get("id"),
                    account_id,
                    item_type,
                    item.get("title") or item.get("subject"),
                    item.get("sender"),
                    item.get("content"),
                    item.get("date") or item.get("receivedDateTime") or item.get("dueDate"),
                    json.dumps(item)
                )
            )
        await db.commit()


async def get_items(
    account_id: str,
    item_type: str = None,
    start_date: str = None,
    end_date: str = None
) -> list:
    """Get cached items for an account."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row

        query = "SELECT * FROM items WHERE account_id = ?"
        params = [account_id]

        if item_type:
            query += " AND type = ?"
            params.append(item_type)

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

        return [json.loads(row["data"]) for row in rows]


async def delete_item(item_id: str) -> bool:
    """Delete a cached item."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        await db.commit()
        return True


async def clear_account_items(account_id: str, item_type: str = None):
    """Clear cached items for an account."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if item_type:
            await db.execute(
                "DELETE FROM items WHERE account_id = ? AND type = ?",
                (account_id, item_type)
            )
        else:
            await db.execute(
                "DELETE FROM items WHERE account_id = ?",
                (account_id,)
            )
        await db.commit()


async def get_last_sync(account_id: str, item_type: str) -> Optional[datetime]:
    """Get last sync time for account items."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            SELECT MAX(synced_at) as last_sync FROM items
            WHERE account_id = ? AND type = ?
            """,
            (account_id, item_type)
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None
