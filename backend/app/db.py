"""Banco local da plataforma: usuarios e papeis (SI = total, gestor = somente leitura)."""
import os
import sqlite3

from passlib.hash import bcrypt

from .config import settings

ROLES = ("si", "gestor")


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(settings.DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)
    con = _conn()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'gestor'
        )
        """
    )
    con.commit()
    # Cria o admin (perfil SI) uma unica vez, a partir das variaveis de ambiente.
    exists = con.execute(
        "SELECT 1 FROM users WHERE username = ?", (settings.ADMIN_USER,)
    ).fetchone()
    if not exists:
        con.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (settings.ADMIN_USER, bcrypt.hash(settings.ADMIN_PASSWORD), "si"),
        )
        con.commit()
    con.close()


def verify_user(username: str, password: str):
    con = _conn()
    row = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    con.close()
    if row and bcrypt.verify(password, row["password_hash"]):
        return row
    return None


def create_user(username: str, password: str, role: str) -> None:
    if role not in ROLES:
        raise ValueError("papel invalido")
    con = _conn()
    con.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, bcrypt.hash(password), role),
    )
    con.commit()
    con.close()


def list_users():
    con = _conn()
    rows = con.execute("SELECT id, username, role FROM users ORDER BY username").fetchall()
    con.close()
    return rows
