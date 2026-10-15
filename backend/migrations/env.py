from alembic import context
from app.db import engine
from app.models import Base
from app.config import database_url

if context.is_offline_mode():
    context.configure(url=database_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=engine.dialect.name == 'sqlite')
        with context.begin_transaction():
            context.run_migrations()
