from sqlalchemy import Engine
from sqlmodel import create_engine


def get_engine() -> Engine:
    """
    Create and return the SQLAlchemy engine.

    Parameters
    ----------
    None

    Returns
    -------
    engine : Engine
        An SQLAlchemy engine instance.
    """
    return create_engine("sqlite:///db.sqlite", echo=True)
