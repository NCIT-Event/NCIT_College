import os

from alembic import context
from app.models import Base
from sqlalchemy import create_engine

target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Alembic can't compare expression indexes; the full-text index is created by hand in 0001.
    return not (type_ == "index" and name == "ix_documents_search")


def run_migrations():
    url = os.environ["DATABASE_URL"]
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
