
import sqlite3
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
DATA_DIR = BASE_DIR / "data"

# --------------------------------------------------
# Database Schema & Loading Order
# --------------------------------------------------

# Table creation order based on foreign-key dependencies
TABLE_ORDER = [
    "sectors",
    "securities",
    "benchmarks",
    "portfolios",
    "holdings",
    "transactions",
    "historical_prices",
    "portfolio_performance",
    "risk_metrics",
]


def load_csv(connection, table_name):
    csv_path = DATA_DIR / f"{table_name}.csv"

    if not csv_path.is_file():
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}"
        )

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        csv_columns = reader.fieldnames

        if not csv_columns:
            raise ValueError(
                f"CSV file is empty or has no header: {csv_path}"
            )

        database_columns = [
            row[1]
            for row in connection.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        ]

        if csv_columns != database_columns:
            raise ValueError(
                f"Column mismatch in {table_name}.csv\n"
                f"Expected: {database_columns}\n"
                f"Received: {csv_columns}"
            )

        placeholders = ", ".join(["?"] * len(csv_columns))
        columns = ", ".join(csv_columns)

        query = f"""
            INSERT INTO {table_name} ({columns})
            VALUES ({placeholders})
        """

        rows = []

        for row in reader:
            values = [
                value if value != "" else None
                for value in row.values()
            ]
            rows.append(values)

        if rows:
            connection.executemany(query, rows)

        return len(rows)


def create_database(target_db_path=None):
    """
    Initialize the SQLite database using database_schema.sql as the single source of truth,
    enable foreign-key enforcement, and populate all nine tables in foreign-key dependency order.
    """
    db_file = target_db_path or DB_PATH
    connection = sqlite3.connect(db_file)

    try:
        # Enable foreign key constraint checking
        connection.execute("PRAGMA foreign_keys = ON;")

        # Apply schema with full constraints, check constraints, foreign keys and indexes
        schema_path = BASE_DIR / "database_schema.sql"
        if not schema_path.is_file():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        schema_sql = schema_path.read_text(encoding="utf-8")
        connection.executescript(schema_sql)

        # Start a transaction for the data refresh.
        connection.execute("BEGIN")

        print("DATABASE LOADING")
        print("----------------")

        # Clear records in reverse dependency order to respect foreign keys
        for table_name in reversed(TABLE_ORDER):
            connection.execute(f"DELETE FROM {table_name}")

        # Load all CSV files in dependency order
        for table_name in TABLE_ORDER:
            count = load_csv(connection, table_name)
            print(f"{table_name}: {count} records loaded")

        connection.commit()

        print("\nDatabase created and loaded successfully!")
        print(f"Database location: {db_file}")

    except Exception as error:
        connection.rollback()
        print("\nDatabase loading failed.")
        print("Reason:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_database()
