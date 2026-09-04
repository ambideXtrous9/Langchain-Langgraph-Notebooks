"""DuckDB Fact Store for NSE Stock Analysis."""

import logging
import re
from typing import Any, Dict, List, Optional, Union
import duckdb
import pandas as pd
from langchain_core.tools import tool
from app.tools.nifty_data import load_enriched_nifty500

logger = logging.getLogger(__name__)


class StockFactStore:
    """High-performance DuckDB fact store containing NIFTY 500 records and aggregates."""

    _instance: Optional["StockFactStore"] = None

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.con = duckdb.connect(database=db_path)
        self._initialized = False

    @classmethod
    def get_instance(cls, db_path: str = ":memory:") -> "StockFactStore":
        """Singleton accessor for StockFactStore."""
        if cls._instance is None:
            cls._instance = StockFactStore(db_path=db_path)
            cls._instance.initialize()
        return cls._instance

    def initialize(self, force_reload: bool = False) -> None:
        """Loads NIFTY 500 data and builds analytical tables in DuckDB."""
        if self._initialized and not force_reload:
            return

        df = load_enriched_nifty500()
        self.con.register("nifty500_df", df)

        # 1. Main NIFTY 500 facts table
        self.con.execute("CREATE OR REPLACE TABLE nifty500 AS SELECT * FROM nifty500_df")

        # 2. Sector aggregates table
        self.con.execute("""
            CREATE OR REPLACE TABLE sector_aggregates AS
            SELECT 
                industry,
                COUNT(*) AS stock_count,
                ROUND(SUM(market_cap_cr), 2) AS total_market_cap_cr,
                ROUND(AVG(pe_ratio), 2) AS avg_pe_ratio,
                ROUND(MEDIAN(pe_ratio), 2) AS median_pe_ratio,
                ROUND(AVG(roe_pct), 2) AS avg_roe_pct,
                ROUND(AVG(roce_pct), 2) AS avg_roce_pct,
                ROUND(AVG(return_1m_pct), 2) AS avg_return_1m_pct,
                ROUND(AVG(return_1y_pct), 2) AS avg_return_1y_pct,
                ROUND(AVG(debt_to_equity), 2) AS avg_debt_to_equity,
                ROUND(AVG(beta), 2) AS avg_beta
            FROM nifty500
            GROUP BY industry
            ORDER BY total_market_cap_cr DESC
        """)

        # 3. Changepoint / Breakout candidates table
        self.con.execute("""
            CREATE OR REPLACE TABLE changepoint_candidates AS
            SELECT 
                symbol,
                company_name,
                industry,
                current_price,
                high_52w,
                low_52w,
                return_1m_pct,
                return_1y_pct,
                volume_avg_30d,
                ROUND((current_price / high_52w) * 100, 2) AS pct_of_52w_high
            FROM nifty500
            WHERE breakout_52w = 1 OR return_1m_pct > 15.0
            ORDER BY return_1m_pct DESC
        """)

        # 4. Value and Quality discovery table
        self.con.execute("""
            CREATE OR REPLACE TABLE quality_value_stocks AS
            SELECT 
                symbol,
                company_name,
                industry,
                current_price,
                pe_ratio,
                roe_pct,
                roce_pct,
                debt_to_equity,
                return_1y_pct
            FROM nifty500
            WHERE pe_ratio < 25.0 AND roe_pct > 18.0 AND debt_to_equity < 0.6
            ORDER BY roe_pct DESC
        """)

        self._initialized = True
        logger.info("StockFactStore successfully initialized with DuckDB tables.")

    def execute_sql(self, query: str) -> pd.DataFrame:
        """Executes a SQL query against the DuckDB fact store and returns a DataFrame."""
        if not self._initialized:
            self.initialize()
        # Security sanitization: prevent destructive commands
        disallowed = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE"]
        first_token = query.strip().split()[0].upper() if query.strip() else ""
        if first_token in disallowed:
            raise PermissionError(f"Modifying query '{first_token}' is not allowed on Fact Store.")

        return self.con.execute(query).df()

    def execute_scalar(self, query: str) -> Union[float, int, str]:
        """Executes a SQL query and guarantees that it returns EXACTLY ONE scalar value.
        Used by the Numeric Tracer to audit finding claims against raw data.
        """
        df = self.execute_sql(query)
        if df.empty:
            raise ValueError(f"Query returned 0 rows: {query}")
        if len(df) > 1:
            raise ValueError(f"Query returned {len(df)} rows, expected exactly 1 row: {query}")
        if len(df.columns) != 1:
            raise ValueError(f"Query returned {len(df.columns)} columns, expected exactly 1 column: {query}")

        val = df.iloc[0, 0]
        if pd.isna(val):
            raise ValueError("Query returned NULL/NaN scalar.")
        return val

    def get_dataset_profile(self, filter_term: str = "") -> Dict[str, Any]:
        """Generates a deterministic summary dataset profile for the Planner."""
        if not self._initialized:
            self.initialize()

        base_filter = ""
        if filter_term:
            sanitized = re.sub(r"[^a-zA-Z0-9_\s]", "", filter_term).strip()
            if sanitized:
                base_filter = f"WHERE symbol ILIKE '%{sanitized}%' OR company_name ILIKE '%{sanitized}%' OR industry ILIKE '%{sanitized}%'"

        stats = self.con.execute(f"""
            SELECT 
                COUNT(*) AS total_stocks,
                COUNT(DISTINCT industry) AS total_industries,
                ROUND(AVG(pe_ratio), 2) AS market_avg_pe,
                ROUND(AVG(roe_pct), 2) AS market_avg_roe,
                ROUND(AVG(return_1y_pct), 2) AS market_avg_1y_return,
                ROUND(SUM(market_cap_cr), 2) AS total_market_cap_cr
            FROM nifty500
            {base_filter}
        """).df().to_dict(orient="records")[0]

        top_industries = self.con.execute(f"""
            SELECT industry, COUNT(*) AS count, ROUND(SUM(market_cap_cr), 2) AS mcap_cr
            FROM nifty500
            {base_filter}
            GROUP BY industry
            ORDER BY mcap_cr DESC
            LIMIT 6
        """).df().to_dict(orient="records")

        top_gainers_1m = self.con.execute(f"""
            SELECT symbol, company_name, return_1m_pct, current_price
            FROM nifty500
            {base_filter}
            ORDER BY return_1m_pct DESC
            LIMIT 5
        """).df().to_dict(orient="records")

        return {
            "summary_stats": stats,
            "top_industries": top_industries,
            "top_gainers_1m": top_gainers_1m,
            "filter_applied": filter_term,
        }

    def resolve_target_entities(self, query: str) -> List[Dict[str, Any]]:
        """Resolves target stock entities from a natural user query using company aliases, symbols, and fuzzy search."""
        if not self._initialized:
            self.initialize()

        aliases = {
            "HDFC BANK": "HDFCBANK",
            "HDFC": "HDFCBANK",
            "RELIANCE": "RELIANCE",
            "RELIANCE INDUSTRIES": "RELIANCE",
            "RIL": "RELIANCE",
            "TCS": "TCS",
            "TATA CONSULTANCY": "TCS",
            "INFOSYS": "INFY",
            "INFY": "INFY",
            "ICICI BANK": "ICICIBANK",
            "ICICI": "ICICIBANK",
            "STATE BANK OF INDIA": "SBIN",
            "SBI": "SBIN",
            "SBIN": "SBIN",
            "TATA MOTORS": "TATAMOTORS",
            "MARUTI": "MARUTI",
            "MARUTI SUZUKI": "MARUTI",
            "ITC": "ITC",
            "L&T": "LT",
            "LARSEN": "LT",
            "BHARTI AIRTEL": "BHARTIARTL",
            "AIRTEL": "BHARTIARTL",
            "KOTAK": "KOTAKBANK",
            "KOTAK MAHINDRA": "KOTAKBANK",
            "AXIS BANK": "AXISBANK",
            "AXIS": "AXISBANK",
            "BAJAJ FINANCE": "BAJFINANCE",
            "BAJAJ FINSERV": "BAJAJFINSV",
            "SUN PHARMA": "SUNPHARMA",
            "TITAN": "TITAN",
            "WIPRO": "WIPRO",
            "ASIAN PAINTS": "ASIANPAINT",
            "HCL TECH": "HCLTECH",
            "NTPC": "NTPC",
            "ONGC": "ONGC",
            "POWER GRID": "POWERGRID",
            "MAHINDRA": "M&M",
            "M&M": "M&M",
            "TATA STEEL": "TATASTEEL",
            "JSW STEEL": "JSWSTEEL",
            "COAL INDIA": "COALINDIA",
            "ADANI ENTERPRISES": "ADANIENT",
            "ADANI PORTS": "ADANIPORTS",
            "ZOMATO": "ZOMATO",
            "TRENT": "TRENT",
            "HINDALCO": "HINDALCO",
        }

        q_upper = query.upper()
        found_symbols = []

        # 1. Check exact aliases in query
        for alias, sym in sorted(aliases.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, q_upper):
                if sym not in found_symbols:
                    found_symbols.append(sym)

        # 2. Check if raw symbols from nifty500 match tokens in the query
        words = [w.strip(".,;:!?()[]\"'") for w in q_upper.split()]
        all_syms = set(self.con.execute("SELECT symbol FROM nifty500").df()["symbol"].str.upper())
        for w in words:
            if len(w) >= 3 and w in all_syms and w not in found_symbols:
                found_symbols.append(w)

        # 3. If no symbols found, try fuzzy ILIKE search for words in company_name
        if not found_symbols:
            for w in words:
                if len(w) >= 4 and w not in {"RESEARCH", "DEPTH", "COMPARE", "PERFORMANCE", "NEXT", "MONTHS", "YEAR", "STOCK", "STOCKS", "ANALYSIS", "SECTOR", "EVALUATE"}:
                    matches = self.con.execute(f"SELECT symbol FROM nifty500 WHERE company_name ILIKE '%{w}%' LIMIT 3").df()
                    for s in matches["symbol"]:
                        if s not in found_symbols:
                            found_symbols.append(s)

        results = []
        if found_symbols:
            in_clause = "', '".join(found_symbols)
            df_res = self.con.execute(f"""
                SELECT symbol, company_name, industry, current_price, market_cap_cr, pe_ratio, roe_pct, return_6m_pct
                FROM nifty500
                WHERE symbol IN ('{in_clause}')
            """).df()
            for _, r in df_res.iterrows():
                results.append({
                    "symbol": r["symbol"],
                    "company_name": r["company_name"],
                    "industry": r["industry"],
                    "current_price": float(r["current_price"]),
                    "market_cap_cr": float(r["market_cap_cr"]),
                    "pe_ratio": float(r["pe_ratio"]),
                    "roe_pct": float(r["roe_pct"]),
                    "return_6m_pct": float(r["return_6m_pct"]),
                    "yahoo_symbol": f"{r['symbol']}.NS",
                })
        return results

    def resolve_time_horizon(self, query: str) -> Dict[str, Any]:
        """Resolves target time horizon from user query."""
        q_lower = query.lower()
        if any(h in q_lower for h in ["1 year", "12 month", "1 yr", "1y", "annual"]):
            return {"days": 252, "period": "1y", "label": "1 Year", "trading_days": 252}
        elif any(h in q_lower for h in ["3 month", "quarter", "3m", "3 mos"]):
            return {"days": 63, "period": "3mo", "label": "3 Months", "trading_days": 63}
        elif any(h in q_lower for h in ["1 month", "30 day", "1m", "short term"]):
            return {"days": 21, "period": "1mo", "label": "1 Month", "trading_days": 21}
        elif any(h in q_lower for h in ["6 month", "half year", "6m", "6 mos"]):
            return {"days": 126, "period": "6mo", "label": "6 Months", "trading_days": 126}
        elif any(h in q_lower for h in ["2 year", "24 month", "2y"]):
            return {"days": 504, "period": "2y", "label": "2 Years", "trading_days": 504}
        else:
            return {"days": 126, "period": "6mo", "label": "6 Months", "trading_days": 126}

    def get_comparative_metrics(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Fetches detailed side-by-side comparative financial metrics for target symbols."""
        if not self._initialized:
            self.initialize()
        if not symbols:
            return []
        in_clause = "', '".join([s.strip().upper() for s in symbols])
        df = self.con.execute(f"""
            SELECT symbol, company_name, industry, current_price, market_cap_cr,
                   pe_ratio, pb_ratio, roe_pct, roce_pct, debt_to_equity, beta,
                   return_1m_pct, return_6m_pct, return_1y_pct, high_52w, low_52w
            FROM nifty500
            WHERE symbol IN ('{in_clause}')
        """).df()
        return df.to_dict(orient="records")

    def screen_stocks(self, where_clause: str = "1=1", order_by: str = "market_cap_cr DESC", limit: int = 5) -> List[Dict[str, Any]]:
        """Screens NIFTY 500 stocks based on fundamental filters."""
        if not self._initialized:
            self.initialize()
        try:
            df = self.con.execute(f"""
                SELECT symbol, company_name, industry, current_price, market_cap_cr,
                       pe_ratio, pb_ratio, roe_pct, roce_pct, debt_to_equity, beta,
                       return_1m_pct, return_6m_pct, return_1y_pct
                FROM nifty500
                WHERE {where_clause}
                ORDER BY {order_by}
                LIMIT {limit}
            """).df()
            return df.to_dict(orient="records")
        except Exception as exc:
            logger.warning(f"Stock screening failed: {exc}")
            return []



@tool
def execute_stock_sql(query: str) -> str:
    """Executes a read-only SQL query against the NIFTY 500 DuckDB fact store.
    Tables available:
    - nifty500: symbol, company_name, industry, series, isin_code, current_price, market_cap_cr, pe_ratio, pb_ratio, roe_pct, roce_pct, debt_to_equity, beta, return_1m_pct, return_6m_pct, return_1y_pct, high_52w, low_52w, volume_avg_30d, breakout_52w, promoter_holding_pct, pledged_promoter_pct, fii_holding_pct, dii_holding_pct.
    - sector_aggregates: industry, stock_count, total_market_cap_cr, avg_pe_ratio, median_pe_ratio, avg_roe_pct, avg_roce_pct, avg_return_1m_pct, avg_return_1y_pct, avg_debt_to_equity, avg_beta.
    - changepoint_candidates: breakout stocks near 52W high.
    - quality_value_stocks: high ROE, low PE, low debt stocks.
    """
    store = StockFactStore.get_instance()
    try:
        df = store.execute_sql(query)
        if df.empty:
            return "Query executed successfully: No rows returned."
        # Cap output to 20 rows to conserve token context
        truncated = df.head(20)
        output = truncated.to_markdown(index=False)
        if len(df) > 20:
            output += f"\n\n... [Truncated: showing 20 of {len(df)} rows]"
        return output
    except Exception as e:
        return f"SQL Execution Error: {str(e)}"
