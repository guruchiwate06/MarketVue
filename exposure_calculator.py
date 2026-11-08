
import sqlite3
from pathlib import Path


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "portfolio.db"


# --------------------------------------------------
# Sector exposure calculator
# --------------------------------------------------

def calculate_sector_exposure(portfolio_name):
    """
    Calculate sector exposure for a portfolio.

    Only stock holdings are included.
    Original holding weights are used without normalization.

    Returns:
        portfolio_name
        portfolio_id
        sector_exposure
        raw_holdings
        total_equity_weight
        sql_query
    """

    if not isinstance(portfolio_name, str) or not portfolio_name.strip():
        raise ValueError("A valid portfolio name is required.")

    portfolio_name = portfolio_name.strip()

    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Database file not found: {DB_PATH}"
        )

    connection = None

    try:
        # Open the database in read-only mode.
        database_uri = DB_PATH.as_uri() + "?mode=ro"

        connection = sqlite3.connect(
            database_uri,
            uri=True
        )

        # Find the requested portfolio.
        portfolio_query = """
            SELECT portfolio_id, portfolio_name
            FROM portfolios
            WHERE portfolio_name = ?
        """

        portfolio = connection.execute(
            portfolio_query,
            (portfolio_name,)
        ).fetchone()

        if portfolio is None:
            raise ValueError(
                f"Portfolio not found: {portfolio_name}"
            )

        portfolio_id, actual_name = portfolio

        # Retrieve original stock holdings and their sectors.
        holdings_query = """
            SELECT
                h.holding_id,
                s.symbol,
                s.company_name,
                COALESCE(sec.sector_name, 'Unclassified') AS sector,
                h.quantity,
                h.current_weight
            FROM holdings h
            JOIN securities s
                ON h.security_id = s.security_id
            LEFT JOIN sectors sec
                ON s.sector_id = sec.sector_id
            WHERE h.portfolio_id = ?
              AND s.asset_type = 'Stock'
            ORDER BY h.holding_id
        """

        rows = connection.execute(
            holdings_query,
            (portfolio_id,)
        ).fetchall()

        # Handle portfolios without stock holdings.
        if not rows:

            return {
                "portfolio_name": actual_name,
                "portfolio_id": portfolio_id,
                "sector_exposure": {},
                "raw_holdings": [],
                "total_equity_weight": 0.0,
                "sql_query": holdings_query,
                "sql_parameters": {
                    "portfolio_id": portfolio_id
                }
            }

        # Group holding weights by sector.
        exposure = {}

        for row in rows:

            sector = row[3]
            weight = float(row[5]) if row[5] is not None else 0.0

            exposure[sector] = (
                exposure.get(sector, 0.0) + weight
            )

        # Preserve the individual holdings for evidence.
        raw_holdings = []

        for row in rows:

            raw_holdings.append({
                "holding_id": row[0],
                "symbol": row[1],
                "company_name": row[2],
                "sector": row[3],
                "quantity": row[4],
                "current_weight": row[5]
            })

        # Sum the original stock holding weights.
        total_equity_weight = sum(exposure.values())

        return {
            "portfolio_name": actual_name,
            "portfolio_id": portfolio_id,
            "sector_exposure": exposure,
            "raw_holdings": raw_holdings,
            "total_equity_weight": total_equity_weight,
            "sql_query": holdings_query,
            "sql_parameters": {
                "portfolio_id": portfolio_id
            }
        }

    finally:

        if connection is not None:
            connection.close()


# --------------------------------------------------
# Testing
# --------------------------------------------------

if __name__ == "__main__":

    portfolio_name = "Tech Innovation Fund"

    try:

        result = calculate_sector_exposure(portfolio_name)

        print("\nSECTOR EXPOSURE REPORT")
        print("----------------------")

        print("Portfolio:", result["portfolio_name"])
        print("Portfolio ID:", result["portfolio_id"])

        print("\nSector Breakdown:")

        for sector, weight in result["sector_exposure"].items():

            print(f"{sector}: {weight * 100:.2f}%")

        print(
            "\nTotal Equity Weight:",
            f"{result['total_equity_weight'] * 100:.2f}%"
        )

        print("\nRaw Holdings:")

        for holding in result["raw_holdings"]:
            print(holding)

        print("\nSQL Used:")
        print(result["sql_query"])

        print("\nSQL Parameters:")
        print(result["sql_parameters"])

    except (ValueError, FileNotFoundError, sqlite3.Error) as error:

        print("Error:", error)
