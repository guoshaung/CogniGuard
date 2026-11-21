"""MySQL 连接配置与连接工厂（供 MySQL 版工具后端使用）。

从项目 .env 读取 MYSQL_* 配置，兼容常见拼写（USER/NAME、PASSWORD/PASSWARD）。
仅连本地合成库，绝不在命令行传递口令。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _env() -> dict:
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def db_config() -> dict:
    e = _env()
    return {
        "host": e.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(e.get("MYSQL_PORT", "3306") or 3306),
        "user": e.get("MYSQL_USER") or e.get("MYSQL_NAME") or "root",
        "password": e.get("MYSQL_PASSWORD") or e.get("MYSQL_PASSWARD") or "",
        "db": e.get("MYSQL_DB", "coginguard_demo"),
    }


def connect(with_db: bool = True):
    import pymysql
    cfg = db_config()
    kwargs = dict(host=cfg["host"], port=cfg["port"], user=cfg["user"],
                  password=cfg["password"], charset="utf8mb4", autocommit=True,
                  cursorclass=pymysql.cursors.DictCursor, connect_timeout=8)
    if with_db:
        kwargs["database"] = cfg["db"]
    return pymysql.connect(**kwargs)
