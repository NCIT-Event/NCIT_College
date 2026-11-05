import os

from alembic import context
from app.models import Base
from sqlalchemy import create_engine

target_metadata = Base.metadata


def run_migrations():
    url = os.environ["DATABASE_URL"]
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
