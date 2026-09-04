"""Master Deep Agent: Universal Query Reasoner & Orchestration Planner.

Analyzes any natural language user query, classifies intent, discovers candidate symbols
from DuckDB, infers time horizons, and formulates multi-source data retrieval directives
across CSV, DuckDB, SQLite, GNews, Yahoo Finance, and Quant Sandbox.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings
from app.core.llm import get_llm
from app.tools.stock_fact_store import StockFactStore

logger = logging.getLogger(__name__)


# Supported intent classifications
INTENT_SINGLE_STOCK = "single_stock_deep_dive"
INTENT_COMPARISON = "head_to_head_comparison"
INTENT_SCREENING = "factor_fundamental_screening"
INTENT_SECTOR = "sector_thematic_screening"
INTENT_MACRO_RISK = "macro_scenario_risk"
INTENT_PORTFOLIO = "portfolio_optimization"
INTENT_GENERAL = "general_market_overview"


class IntelligentQueryReasoner:
    """Master Deep Agent that intelligently parses, decomposes, and plans for any equity research query."""

    def __init__(self, fact_store: Optional[StockFactStore] = None):
        self.fact_store = fact_store or StockFactStore.get_instance()
        if not self.fact_store._initialized:
            self.fact_store.initialize()

    def _get_candidate_matches_from_db(self, query: str) -> List[Dict[str, Any]]:
        """Fast DB candidate search to prime LLM context with verified NSE symbols."""
        tokens = [t.strip(".,;:!?()[]\"'") for t in query.upper().split() if len(t) >= 3]
        stop_words = {
            "RESEARCH", "DEPTH", "COMPARE", "PERFORMANCE", "NEXT", "MONTHS", "YEAR",
            "STOCK", "STOCKS", "ANALYSIS", "SECTOR", "EVALUATE", "WHICH", "WHAT",
            "ABOUT", "SHOULD", "FIND", "SCREEN", "INVEST", "INDIA", "INDIAN", "MARKET"
        }
        filtered_tokens = [t for t in tokens if t not in stop_words]

        candidates = []
        seen = set()

        # Check aliases first
        deterministic_matches = self.fact_store.resolve_target_entities(query)
        for d in deterministic_matches:
            if d["symbol"] not in seen:
                candidates.append(d)
                seen.add(d["symbol"])

        # Check fuzzy names in DuckDB
        for tok in filtered_tokens[:4]:
            try:
                df = self.fact_store.con.execute(f"""
                    SELECT symbol, company_name, industry, current_price, pe_ratio, roe_pct
                    FROM nifty500
                    WHERE symbol = '{tok}' OR company_name ILIKE '%{tok}%' OR industry ILIKE '%{tok}%'
                    LIMIT 3
                """).df()
                for _, r in df.iterrows():
                    s = r["symbol"]
                    if s not in seen:
                        candidates.append({
                            "symbol": s,
                            "company_name": r["company_name"],
                            "industry": r["industry"],
                            "current_price": float(r["current_price"]),
                            "pe_ratio": float(r["pe_ratio"]),
                            "roe_pct": float(r["roe_pct"]),
                        })
                        seen.add(s)
            except Exception as e:
                logger.debug(f"Candidate lookup notice: {e}")

        return candidates[:8]

    def _get_active_industries(self) -> List[str]:
        """Fetches distinct active industries in the NIFTY 500 universe."""
        try:
            df = self.fact_store.con.execute("SELECT DISTINCT industry FROM nifty500 ORDER BY industry").df()
            return df["industry"].tolist()
        except Exception:
            return ["Financial Services", "Information Technology", "Automobile and Auto Components", "Oil Gas & Consumable Fuels"]

    async def analyze_query(self, query: str) -> Dict[str, Any]:
        """Evaluates query using LLM reasoning, returning structured intent, targets, horizon, and sourcing strategy."""
        candidates = self._get_candidate_matches_from_db(query)
        industries = self._get_active_industries()
        fallback_horizon = self.fact_store.resolve_time_horizon(query)

        system_prompt = (
            "You are the Master Equity Research Strategist and Chief Architect of an institutional Indian NSE stock research swarm.\n"
            "Analyze the user's research query with extreme financial intelligence. You must determine:\n"
            "1. Intent classification: 'single_stock_deep_dive', 'head_to_head_comparison', 'factor_fundamental_screening', "
            "'sector_thematic_screening', 'macro_scenario_risk', 'portfolio_optimization', or 'general_market_overview'.\n"
            "2. Target symbols: Grounded NSE ticker symbols matching the user's intent. Prefer provided candidates if relevant.\n"
            "3. Sector filter: If the query focuses on an industry (e.g. Banking, IT, Auto, Energy).\n"
            "4. Time horizon: Explicit or inferred duration (e.g. '6 Months' -> 126 trading days, '1 Year' -> 252 trading days, '3 Months' -> 63 trading days).\n"
            "5. Primary research question & key hypotheses.\n"
            "6. Data sourcing directives across CSV/DuckDB, SQLite Blackboard, GNews, Yahoo Finance, and Quant Sandbox.\n\n"
            "Return ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "intent": "...",\n'
            '  "reasoning": "...",\n'
            '  "target_symbols": ["SYM1", "SYM2"],\n'
            '  "sector_filter": null or "Exact Sector Name",\n'
            '  "screening_sql_where": null or "DuckDB WHERE clause e.g. pe_ratio < 25 AND roe_pct > 15",\n'
            '  "time_horizon": {"label": "6 Months", "trading_days": 126, "period": "6mo"},\n'
            '  "primary_research_question": "...",\n'
            '  "key_hypotheses": ["H1", "H2"],\n'
            '  "data_sourcing_plan": {\n'
            '    "duckdb_strategy": "...",\n'
            '    "yahoo_finance_symbols": ["SYM1.NS", "SYM2.NS"],\n'
            '    "gnews_search_topics": ["Query 1", "Query 2"],\n'
            '    "quant_sandbox_tasks": ["monte_carlo", "portfolio_optimization"]\n'
            '  },\n'
            '  "initial_strategic_roadmap": "1-2 sentence overview of how the swarm should tackle this query"\n'
            "}"
        )

        candidates_context = json.dumps([{"symbol": c["symbol"], "company_name": c["company_name"], "industry": c.get("industry", "")} for c in candidates])
        user_message = (
            f"User Query: \"{query}\"\n"
            f"Grounded Candidate Matches from NIFTY 500: {candidates_context}\n"
            f"Available Sectors (sample): {industries[:10]}\n"
            f"Rule-based Horizon Hint: {fallback_horizon['label']} ({fallback_horizon['trading_days']} trading days)\n\n"
            "Evaluate and return the structured JSON query intelligence."
        )

        parsed_data = None
        try:
            llm = get_llm(temperature=0.1, max_tokens=1000)
            res = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
            raw_text = res.content.strip()
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            parsed_data = json.loads(raw_text)
        except Exception as exc:
            logger.warning(f"[Query Reasoner] LLM reasoning fallback triggered: {exc}")

        # Construct final validated structure
        return self._finalize_query_intelligence(query, parsed_data, candidates, fallback_horizon)

    def _finalize_query_intelligence(
        self,
        query: str,
        llm_data: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
        fallback_horizon: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Validates and guarantees high-integrity query intelligence with fallbacks."""
        if not llm_data:
            llm_data = {}

        # 1. Determine Intent
        intent = llm_data.get("intent")
        if not intent:
            if len(candidates) > 1:
                intent = INTENT_COMPARISON
            elif len(candidates) == 1:
                intent = INTENT_SINGLE_STOCK
            elif any(w in query.lower() for w in ["screen", "undervalue", "pe <", "roe >", "dividend", "filter"]):
                intent = INTENT_SCREENING
            elif any(w in query.lower() for w in ["sector", "industry", "pharma", "it", "bank", "auto", "energy", "fmcg"]):
                intent = INTENT_SECTOR
            elif any(w in query.lower() for w in ["portfolio", "allocate", "weights", "sharpe", "markowitz"]):
                intent = INTENT_PORTFOLIO
            elif any(w in query.lower() for w in ["risk", "drawdown", "var", "leverage", "crash", "fall"]):
                intent = INTENT_MACRO_RISK
            else:
                intent = INTENT_GENERAL

        # 2. Resolve Target Symbols
        target_symbols = []
        raw_symbols = llm_data.get("target_symbols", [])
        if isinstance(raw_symbols, list):
            for s in raw_symbols:
                s_clean = s.strip().upper().replace(".NS", "").replace(".BO", "")
                if s_clean:
                    target_symbols.append(s_clean)

        # Fallback to candidates if empty
        if not target_symbols and candidates:
            target_symbols = [c["symbol"] for c in candidates[:4]]

        # Validate symbols exist in DuckDB
        validated_symbols = []
        if target_symbols:
            in_clause = "', '".join(target_symbols)
            try:
                df = self.fact_store.con.execute(f"SELECT symbol FROM nifty500 WHERE symbol IN ('{in_clause}')").df()
                validated_symbols = df["symbol"].tolist()
            except Exception:
                validated_symbols = target_symbols

        # Handle dynamic screening if no symbols were explicitly named
        screening_sql = llm_data.get("screening_sql_where")
        if not validated_symbols and (intent in [INTENT_SCREENING, INTENT_SECTOR] or screening_sql):
            screened_targets = self._execute_dynamic_screening(screening_sql, llm_data.get("sector_filter"), query)
            validated_symbols = [t["symbol"] for t in screened_targets]

        # 3. Resolve Time Horizon
        th_data = llm_data.get("time_horizon", {})
        if not isinstance(th_data, dict) or not th_data.get("trading_days"):
            th_data = fallback_horizon
        else:
            days = int(th_data.get("trading_days", 126))
            label = th_data.get("label") or f"{days} Days"
            period = th_data.get("period") or ("1y" if days >= 200 else "6mo" if days >= 100 else "3mo")
            th_data = {"label": label, "trading_days": days, "period": period, "days": days}

        # 4. Resolve Target Names & Profiles
        target_names = []
        resolved_entities = []
        if validated_symbols:
            in_clause = "', '".join(validated_symbols)
            try:
                df = self.fact_store.con.execute(f"""
                    SELECT symbol, company_name, industry, current_price, market_cap_cr, pe_ratio, roe_pct, return_6m_pct
                    FROM nifty500
                    WHERE symbol IN ('{in_clause}')
                """).df()
                for _, r in df.iterrows():
                    target_names.append(r["company_name"])
                    resolved_entities.append({
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
            except Exception as e:
                logger.warning(f"[Query Reasoner] Entity profile retrieval notice: {e}")

        # 5. Analysis Mode
        if len(validated_symbols) > 1:
            analysis_mode = "comparison"
        elif len(validated_symbols) == 1:
            analysis_mode = "single_stock"
        else:
            analysis_mode = "sector"

        # 6. Sourcing Directives
        sourcing_plan = llm_data.get("data_sourcing_plan", {})
        if not isinstance(sourcing_plan, dict):
            sourcing_plan = {}

        yahoo_symbols = [f"{s}.NS" for s in validated_symbols] if validated_symbols else ["^NSEI"]
        gnews_topics = sourcing_plan.get("gnews_search_topics", [])
        if not gnews_topics:
            if target_names:
                gnews_topics = [f"{n} stock news" for n in target_names[:3]]
            else:
                gnews_topics = [f"{query} NSE"]

        raw_tasks = sourcing_plan.get("quant_sandbox_tasks", [])
        normalized_tasks = []
        for t in raw_tasks:
            t_clean = t.lower().strip()
            if "monte" in t_clean:
                normalized_tasks.append("monte_carlo")
            elif "portfolio" in t_clean or "sharpe" in t_clean or "markowitz" in t_clean:
                normalized_tasks.append("portfolio_optimization")
            else:
                normalized_tasks.append(t_clean)
        if "monte_carlo" not in normalized_tasks:
            normalized_tasks.append("monte_carlo")
        if (len(validated_symbols) >= 2 or intent in [INTENT_PORTFOLIO, INTENT_COMPARISON]) and "portfolio_optimization" not in normalized_tasks:
            normalized_tasks.append("portfolio_optimization")
        sandbox_tasks = list(dict.fromkeys(normalized_tasks))



        primary_question = llm_data.get("primary_research_question") or query
        roadmap = llm_data.get("initial_strategic_roadmap") or (
            f"Execute {analysis_mode} analysis on {', '.join(validated_symbols) if validated_symbols else 'NIFTY 500'} "
            f"over {th_data['label']} using DuckDB fact store, GNews narratives, Yahoo Finance consensus, and Quant Sandbox."
        )

        return {
            "query": query,
            "intent": intent,
            "analysis_mode": analysis_mode,
            "target_symbols": validated_symbols,
            "target_names": target_names,
            "resolved_entities": resolved_entities,
            "sector_filter": llm_data.get("sector_filter"),
            "time_horizon": th_data["label"],
            "time_horizon_days": th_data["trading_days"],
            "time_horizon_period": th_data["period"],
            "primary_research_question": primary_question,
            "key_hypotheses": llm_data.get("key_hypotheses", []),
            "reasoning": llm_data.get("reasoning", "Heuristic entity and horizon mapping"),
            "initial_strategic_roadmap": roadmap,
            "data_sourcing_plan": {
                "duckdb_strategy": sourcing_plan.get("duckdb_strategy", "Extract comparative valuation & return multiples"),
                "yahoo_finance_symbols": yahoo_symbols,
                "gnews_search_topics": gnews_topics,
                "quant_sandbox_tasks": sandbox_tasks,
            },
        }

    def _execute_dynamic_screening(
        self,
        sql_where: Optional[str],
        sector: Optional[str],
        query: str,
    ) -> List[Dict[str, Any]]:
        """Executes safe DuckDB screening to find top matching stocks for screening/thematic queries."""
        where_parts = []
        if sector:
            clean_sector = sector.replace("'", "")
            where_parts.append(f"industry ILIKE '%{clean_sector}%'")

        if sql_where and any(col in sql_where.lower() for col in ["pe_ratio", "roe_pct", "debt_to_equity", "current_price", "return_6m_pct", "market_cap_cr"]):
            safe_where = re.sub(r"(drop|delete|insert|update|alter|truncate)", "", sql_where, flags=re.IGNORECASE)
            where_parts.append(safe_where)

        # Fallback to query keyword sector search
        if not where_parts:
            for s in ["IT", "BANK", "AUTO", "PHARMA", "ENERGY", "FMCG", "POWER", "METALS"]:
                if s in query.upper():
                    where_parts.append(f"industry ILIKE '%{s}%'")
                    break

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        try:
            df = self.fact_store.con.execute(f"""
                SELECT symbol, company_name, industry, current_price, market_cap_cr, pe_ratio, roe_pct, return_6m_pct
                FROM nifty500
                WHERE {where_clause}
                ORDER BY market_cap_cr DESC
                LIMIT 3
            """).df()
            return df.to_dict(orient="records")
        except Exception as e:
            logger.warning(f"[Query Reasoner] Dynamic screening error: {e}")
            return []
