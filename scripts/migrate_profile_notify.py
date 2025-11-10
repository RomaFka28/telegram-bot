"""One-off helper to add profile_update_notifications column to existing DB."""
import sqlalchemy as sa

from database import engine


def column_missing() -> bool:
    inspector = sa.inspect(engine)
    columns = [col["name"] for col in inspector.get_columns("users")]
    return "profile_update_notifications" not in columns


def add_column() -> None:
    ddl = sa.text(
        "ALTER TABLE users "
        "ADD COLUMN profile_update_notifications BOOLEAN DEFAULT TRUE"
    )
    with engine.begin() as conn:
        conn.execute(ddl)


def main() -> None:
    if not column_missing():
        print("Column profile_update_notifications already exists, nothing to do.")
        return
    add_column()
    print("Column profile_update_notifications added successfully.")


if __name__ == "__main__":
    main()
