from fastapi import Depends

from app.db import get_connection
from app.services.repository import PostgresRepository


def get_repository():
    with get_connection() as conn:
        yield PostgresRepository(conn)
