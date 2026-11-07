
import sqlite3
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"
DATA_DIR = BASE_DIR / "data"

TABLES = {
    "benchmarks": """
        CREATE TABLE IF NOT EXISTS benchmarks (
            benchmark_id INTEGER PRIMARY KEY,
            benchmark_name TEXT,
            benchmark_symbol TEXT,
            benchmark_type TEXT,
            description TEXT,
            inception_date TEXT
        )
    """,

    "historical_prices": """
        CREATE TABLE IF NOT EXISTS historical_prices (
            price_id INTEGER PRIMARY KEY,
            security_id INTEGER,
            price_date TEXT,
            open_price REAL,
            high_price REAL,
            low_price REAL,
            close_price REAL,
            volume INTEGER,
            adjusted_close REAL
        )
    """,

    "holdings": """
        CREATE TABLE IF NOT EXISTS holdings (
            holding_id INTEGER PRIMARY KEY,
            portfolio_id INTEGER,
            security_id INTEGER,
            quantity REAL,
            purchase_price REAL,
            purchase_date TEXT,
            current_weight REAL,
            cost_basis REAL
        )
    """,

    "portfolios": """
        CREATE TABLE IF NOT EXISTS portfolios (
            portfolio_id INTEGER PRIMARY KEY,
            portfolio_name TEXT,
            creation_date TEXT,
            target_risk_level TEXT,
            total_aum REAL,
            strategy_type TEXT,
            benchmark_index TEXT,
            status TEXT
        )
    """,

    "portfolio_performance": """
        CREATE TABLE IF NOT EXISTS portfolio_performance (
            performance_id INTEGER PRIMARY KEY,
            portfolio_id INTEGER,
            performance_date TEXT,
            nav REAL,
            total_return_1m REAL,
            total_return_3m REAL,
            total_return_6m REAL,
            total_return_1y REAL,
            volatility REAL,
            sharpe_ratio REAL,
            max_drawdown REAL
        )
    """,

    "risk_metrics": """
        CREATE TABLE IF NOT EXISTS risk_metrics (
            risk_id INTEGER PRIMARY KEY,
            portfolio_id INTEGER,
            calculation_date TEXT,
            var_95 REAL,
            var_99 REAL,
            cvar_95 REAL,
            beta REAL,
            correlation_sp500 REAL,
            tracking_error REAL,
            information_ratio REAL,
            sortino_ratio REAL
        )
    """,

    "sectors": """
        CREATE TABLE IF NOT EXISTS sectors (
            sector_id INTEGER PRIMARY KEY,
            sector_name TEXT,
            sector_description TEXT,
            industry_group TEXT
        )
    """,

    "securities": """
        CREATE TABLE IF NOT EXISTS securities (
            security_id INTEGER PRIMARY KEY,
            symbol TEXT,
            company_name TEXT,
            asset_type TEXT,
            sector_id INTEGER,
            market_cap REAL,
            current_price REAL,
            currency TEXT,
            exchange TEXT,
            country TEXT,
            listing_date TEXT,
            maturity_date TEXT,
            coupon_rate REAL
        )
    """,

    "transactions": """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY,
            portfolio_id INTEGER,
            security_id INTEGER,
            transaction_type TEXT,
            quantity REAL,
            price REAL,
            transaction_date TEXT,
            fees REAL,
            settlement_date TEXT,
            notes TEXT
        )
    """
}


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


def create_database():
    connection = sqlite3.connect(DB_PATH)

    try:
        # Create database tables.
        for table_name, create_query in TABLES.items():
            connection.execute(create_query)

        # Apply the supplied indexes.
        schema_path = BASE_DIR / "database_schema.sql"

        if not schema_path.is_file():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}"
            )

        schema_sql = schema_path.read_text(encoding="utf-8")
        connection.executescript(schema_sql)

        # Start a transaction for the data refresh.
        connection.execute("BEGIN")

        print("DATABASE LOADING")
        print("----------------")

        # Clear previous records.
        for table_name in TABLES:
            connection.execute(f"DELETE FROM {table_name}")

        # Load all CSV files.
        for table_name in TABLES:
            count = load_csv(connection, table_name)
            print(f"{table_name}: {count} records loaded")

        connection.commit()

        print("\nDatabase created and loaded successfully!")
        print(f"Database location: {DB_PATH}")

    except Exception as error:
        connection.rollback()
        print("\nDatabase loading failed.")
        print("Reason:", error)
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    create_database()
