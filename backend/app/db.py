from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker
from .config import database_url


def make_engine(url: str) -> Engine:
    if url.startswith('sqlite'):
        engine = create_engine(
            url, pool_pre_ping=True, connect_args={'check_same_thread': False}
        )

        @event.listens_for(engine, 'connect')
        def foreign_keys(connection: SQLiteConnection, _: object) -> None:
            connection.execute('PRAGMA foreign_keys=ON')
    else:
        engine = create_engine(url, pool_pre_ping=True)
    return engine


engine = make_engine(database_url())
Session = sessionmaker(engine, expire_on_commit=False)
