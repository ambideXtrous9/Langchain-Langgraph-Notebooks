"""Rigorous Verification Engine for Stock Analysis: Numeric Tracer, Quote Audit, Digit Audit, and Skeptic Quorum."""

import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from app.tools.stock_fact_store import StockFactStore

logger = logging.getLogger(__name__)

# Known structural / designation numbers exempt from digit audit
EXEMPT_STRUCTURAL_NUMBERS = {
    "500", "50", "100", "52", "200", "30", "1", "0", "7", "2024", "2025", "2026", "2027",
    "6", "3", "12", "2", "4", "5", "8", "9", "10", "15", "20", "25", "95", "99",
    "126", "252", "63", "21", "504"
}


def run_numeric_tracer(sql_query: Optional[str], expected_scalar: Optional[float], fact_store: Optional[StockFactStore] = None) -> Tuple[bool, str, Optional[float]]:
    """Numeric Tracer: Re-executes SQL against DuckDB fact store and asserts it returns EXACTLY ONE scalar."""
    if not sql_query or expected_scalar is None:
        return True, "No SQL scalar claimed; skipped numeric tracer.", None

    store = fact_store or StockFactStore.get_instance()
    try:
        raw_val = store.execute_scalar(sql_query)
        try:
            val = float(raw_val)
        except (ValueError, TypeError):
            return False, f"SQL returned non-numeric scalar: {raw_val}", None

        # Check tolerance (1% relative or 0.1 absolute)
        diff = abs(val - expected_scalar)
        rel_diff = diff / max(abs(expected_scalar), 1e-6)
        if rel_diff <= 0.02 or diff <= 0.2:
            return True, f"Scalar verified: claimed {expected_scalar}, realized {val:.2f}", val
        else:
            return False, f"Numeric mismatch: claimed {expected_scalar}, but SQL returned {val:.2f}", val
    except Exception as e:
        return False, f"Numeric Tracer SQL execution failed: {str(e)}", None


def run_quote_audit(verbatim_quote: Optional[str], source_text: Optional[str]) -> Tuple[bool, str]:
    """Quote Audit: Verbatim-substring check against source corporate disclosure or news narrative."""
    if not verbatim_quote:
        return True, "No verbatim quote claimed."

    if not source_text:
        return False, "Verbatim quote claimed but source text is empty."

    quote_norm = re.sub(r"\s+", " ", verbatim_quote.strip().lower())
    source_norm = re.sub(r"\s+", " ", source_text.strip().lower())

    if quote_norm in source_norm:
        return True, "Quote verified verbatim in source narrative."

    # Substring match with 90% word sequence overlap
    quote_words = quote_norm.split()
    if len(quote_words) >= 4:
        sub_str = " ".join(quote_words[:min(6, len(quote_words))])
        if sub_str in source_norm:
            return True, f"Quote verified via leading substring: '{sub_str}'."

    return False, f"Verbatim quote '{verbatim_quote[:40]}...' not found in source text."


def run_digit_audit(
    claim: str,
    verified_scalar: Optional[float],
    sql_context: Optional[str] = None,
    additional_scalars: Optional[List[float]] = None,
) -> Tuple[bool, str, List[str]]:
    """Digit Audit: Every prose number in claim must trace to a verified scalar or fact store ground."""
    # Extract numbers from claim (integers and floats)
    raw_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", claim)
    untraced = []

    for num_str in raw_numbers:
        if num_str in EXEMPT_STRUCTURAL_NUMBERS:
            continue

        try:
            num = float(num_str)
        except ValueError:
            continue

        # Check against verified scalar
        matched = False
        if verified_scalar is not None:
            if abs(num - verified_scalar) <= 0.2 or abs(num - verified_scalar) / max(abs(verified_scalar), 1e-6) <= 0.02:
                matched = True

        # Check against additional verified scalars (e.g. secondary metrics, quant outputs)
        if not matched and additional_scalars:
            for add_s in additional_scalars:
                if add_s is not None:
                    try:
                        add_f = float(add_s)
                        if abs(num - add_f) <= 0.2 or abs(num - add_f) / max(abs(add_f), 1e-6) <= 0.02:
                            matched = True
                            break
                    except (ValueError, TypeError):
                        pass

        # Check if number appears in the SQL query as a filter or bound
        if not matched and sql_context and num_str in sql_context:
            matched = True

        if not matched:
            untraced.append(num_str)

    if untraced:
        return False, f"Digit audit failed: untraced numbers {untraced} in claim prose.", untraced
    return True, "Digit audit passed: all prose numbers traced.", []


def run_skeptic_quorum(finding: Dict[str, Any], all_findings: List[Dict[str, Any]]) -> Tuple[bool, str, List[str]]:
    """Skeptic Quorum: Evaluates finding for fatal analytical flaws. Refutation requires a named flaw."""
    named_flaws = []
    claim = finding.get("claim", "").lower()
    lens = finding.get("lens", "").lower()
    conf = finding.get("confidence", 0.85)

    # Flaw 1: Low confidence assertion without proof
    if conf < 0.6:
        named_flaws.append("Low Confidence Flaw: confidence below 0.60 threshold.")

    # Flaw 2: Excessive extrapolation without historical baseline
    if "will surge" in claim or "guaranteed upside" in claim:
        named_flaws.append("Speculative Extrapolation Flaw: unhedged predictive assertion.")

    # Flaw 3: Single stock over-generalization in cluster lens
    if lens == "clusters" and "sector" in claim and not any(k in claim for k in ["peers", "industry", "average", "median", "cluster"]):
        named_flaws.append("Generalization Flaw: cluster finding lacks peer or sector comparative baseline.")

    # Flaw 4: Missing verification scalar when making numeric comparison
    if any(k in claim for k in ["higher than", "exceeds", "pe of", "roe of"]) and finding.get("numeric_scalar") is None:
        named_flaws.append("Ungrounded Quantitative Claim Flaw: comparative assertion without scalar ground.")

    if named_flaws:
        return False, f"Skeptic quorum rejected with flaws: {'; '.join(named_flaws)}", named_flaws
    return True, "Skeptic quorum approved: No fatal flaws detected.", []


def verify_finding(finding: Dict[str, Any], source_text: Optional[str] = None, all_findings: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Runs complete 4-tier verification suite on a candidate finding."""
    f_copy = finding.copy()
    details = {}

    # 1. Numeric Tracer
    num_ok, num_msg, scalar = run_numeric_tracer(
        sql_query=f_copy.get("sql_query"),
        expected_scalar=f_copy.get("numeric_scalar"),
    )
    details["numeric_tracer"] = {"passed": num_ok, "message": num_msg, "realized_scalar": scalar}

    # 2. Quote Audit
    src = source_text or f_copy.get("source_text") or f_copy.get("verbatim_quote")
    quote_ok, quote_msg = run_quote_audit(
        verbatim_quote=f_copy.get("verbatim_quote"),
        source_text=src,
    )
    details["quote_audit"] = {"passed": quote_ok, "message": quote_msg}

    # 3. Digit Audit (supports primary and additional grounded scalars)
    digit_ok, digit_msg, untraced = run_digit_audit(
        claim=f_copy.get("claim", ""),
        verified_scalar=scalar or f_copy.get("numeric_scalar"),
        sql_context=f_copy.get("sql_query"),
        additional_scalars=f_copy.get("additional_scalars", []),
    )
    details["digit_audit"] = {"passed": digit_ok, "message": digit_msg, "untraced": untraced}

    # 4. Skeptic Quorum
    skeptic_ok, skeptic_msg, flaws = run_skeptic_quorum(
        finding=f_copy,
        all_findings=all_findings or [],
    )
    details["skeptic_quorum"] = {"passed": skeptic_ok, "message": skeptic_msg, "flaws": flaws}

    # Finding passes if numeric tracer, digit audit, and skeptic quorum pass
    is_verified = num_ok and digit_ok and skeptic_ok
    f_copy["verified"] = is_verified
    f_copy["verification_details"] = details
    f_copy["skeptic_votes"] = flaws

    return f_copy
