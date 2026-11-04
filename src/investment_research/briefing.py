"""Bounded briefings from calculated data and explicitly sourced research."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import html
import re
from urllib.parse import urlparse

from .storage import digest

CLAIM_TYPES = {"fact", "estimate", "assumption", "opinion"}


def parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Timestamp must be an ISO string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def validate_research(research: dict, as_of: datetime, *, sample: bool = False) -> dict:
    """No LLM output is accepted as an unsourced fact; URLs never execute here."""
    if as_of.tzinfo is None:
        raise ValueError("as_of must include timezone")
    if not isinstance(research, dict):
        raise ValueError("Research must be an object")
    sources = research.get("sources", [])
    claims = research.get("claims", [])
    if not isinstance(sources, list) or not isinstance(claims, list) or len(sources) > 200 or len(claims) > 200:
        raise ValueError("Research sources and claims must be bounded lists")
    source_map = {}
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get("id"), str) or not source["id"] or len(source["id"]) > 100:
            raise ValueError("Source requires a bounded identifier")
        if source["id"] in source_map:
            raise ValueError("Duplicate source identifier")
        if not isinstance(source.get("url"), str) or re.search(r"[\s<>\x00-\x1f]", source["url"]):
            raise ValueError("Source URL contains unsafe characters")
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Source must be a credential-free HTTPS URL")
        if parsed.hostname.endswith(".invalid") and not sample:
            raise ValueError("Synthetic source cannot support a live report")
        published, retrieved = parse_time(source["published_at"]), parse_time(source["retrieved_at"])
        if published > as_of or retrieved > as_of or published > retrieved:
            raise ValueError("Source chronology is invalid")
        source_map[source["id"]] = source
    claim_ids = set()
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str) or not claim["id"] or len(claim["id"]) > 100:
            raise ValueError("Claim requires a bounded identifier")
        if claim["id"] in claim_ids:
            raise ValueError("Duplicate claim identifier")
        claim_ids.add(claim["id"])
        if claim.get("kind") not in CLAIM_TYPES:
            raise ValueError("Claim must distinguish fact, estimate, assumption or opinion")
        if not isinstance(claim.get("text"), str) or not claim["text"].strip() or len(claim["text"]) > 1600:
            raise ValueError("Claim text is missing or too long")
        if not isinstance(claim.get("source_ids", []), list) or any(not isinstance(sid, str) for sid in claim.get("source_ids", [])):
            raise ValueError("Claim source references must be a list of identifiers")
        if "material" in claim and not isinstance(claim["material"], bool):
            raise ValueError("Materiality must be an explicit boolean")
        for field in ("title", "symbol", "thesis_impact"):
            if field in claim and (not isinstance(claim[field], str) or len(claim[field]) > 1600):
                raise ValueError("Claim display fields must be bounded plain strings")
        if claim["kind"] in {"fact", "estimate"} and not claim.get("source_ids"):
            raise ValueError("Facts and estimates require provenance")
        if any(sid not in source_map for sid in claim.get("source_ids", [])):
            raise ValueError("Unknown source reference")
        if claim.get("material") and not claim.get("thesis_impact"):
            raise ValueError("Material developments need an explicit thesis impact")
    return research


def _comparable_previous(analysis: dict, previous: dict | None, *, sample: bool, as_of: datetime) -> dict | None:
    if not previous or previous.get("mode") != ("sample" if sample else "imported"):
        return None
    old = previous.get("analysis", {})
    try:
        if (parse_time(previous["as_of"]) >= as_of or old.get("methodology") != analysis.get("methodology")
                or old.get("history_start") != analysis.get("history_start") or old.get("currency") != analysis.get("currency")
                or not old.get("quality", {}).get("history_attested_complete")
                or {a["id"] for a in old["accounts"]} != {a["id"] for a in analysis["accounts"]}):
            return None
        # A corrected history must not masquerade as a new investment gain.
        current_history = {row["date"]: row for row in analysis["timeline"]}
        if any(current_history.get(row["date"]) != row for row in old["timeline"]):
            return None
    except (ValueError, KeyError, TypeError):
        return None
    return old


def _markdown_text(value: str) -> str:
    """Render imported prose as text, not HTML, links, images, or headings."""
    escaped = html.escape(str(value), quote=False)
    escaped = re.sub(r"([\\`*_{}\[\]()#+!|])", r"\\\1", escaped)
    return " ".join(escaped.split())


def build_briefing(analysis: dict, research: dict, *, as_of: datetime,
                   previous: dict | None = None, sample: bool = False,
                   concentration_review_pct: str = "20") -> dict:
    research = validate_research(research, as_of, sample=sample)
    summary = analysis["summary"]
    equity = Decimal(summary["equity"])
    holdings = analysis["holdings"]
    try:
        threshold = Decimal(concentration_review_pct)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Concentration review threshold must be a decimal") from exc
    if not threshold.is_finite() or not 0 < threshold <= 100:
        raise ValueError("Concentration review threshold must be between zero and 100")
    old = _comparable_previous(analysis, previous, sample=sample, as_of=as_of)
    old_holdings = {row["symbol"]: row for row in old["holdings"]} if old else {}
    concentration = []
    for holding in sorted(holdings, key=lambda h: Decimal(h["market_value"]), reverse=True):
        weight = Decimal(holding["market_value"]) / equity * 100 if equity > 0 else Decimal(0)
        old_weight = Decimal(old_holdings.get(holding["symbol"], {}).get("weight_pct", "0"))
        same_policy = previous and previous.get("policy_assumptions", {}).get("concentration_review_pct") == str(threshold)
        if weight >= threshold and not (old and same_policy and old_weight >= threshold and abs(weight - old_weight) < Decimal("2")):
            concentration.append({
                "id": "concentration-" + holding["symbol"], "kind": "opinion",
                "symbol": holding["symbol"], "title": "Concentration review",
                "text": f"{holding['symbol']} represents {weight:.1f}% of the combined portfolio. Review whether this fits your risk budget.",
                "basis": "Calculated from the imported holdings and valuation marks. The review threshold is a configurable assumption, not a sell instruction.",
                "question": f"Explain the {holding['symbol']} concentration calculation and the assumptions behind this review.",
                "action": "review", "source_ids": [],
            })
    old_claims = {claim["id"]: claim for claim in previous.get("research", {}).get("claims", [])} if old else {}
    material = [claim for claim in research.get("claims", []) if claim.get("material") and old_claims.get(claim["id"]) != claim]
    insights = []
    for claim in material:
        if len(insights) >= (2 if concentration else 3):
            break
        insights.append({
            "id": claim["id"], "kind": claim["kind"], "symbol": claim.get("symbol", ""),
            "title": claim.get("title", "Thesis update"), "text": claim["text"],
            "basis": claim["thesis_impact"], "source_ids": claim.get("source_ids", []),
            "question": f"Challenge the evidence and assumptions for research claim {claim['id']}.", "action": "research",
        })
    insights.extend(concentration[:3-len(insights)])
    # Only compare snapshots that share the same complete account scope and method.
    delta = None
    if old:
        value_change = equity - Decimal(old["summary"]["equity"])
        flow_change = Decimal(summary["net_contributions"]) - Decimal(old["summary"]["net_contributions"])
        delta = {"since": previous["as_of"], "value_change": str(value_change),
                 "net_external_flows": str(flow_change), "investment_gain": str(value_change-flow_change)}
    report = {
        "schema_version": 1, "mode": "sample" if sample else "imported",
        "as_of": as_of.isoformat(), "analysis": analysis, "changes_since_previous": delta,
        "comparison": {"status": "comparable" if old else "no_comparable_history",
                       "previous_report_id": previous.get("report_id") if old else None},
        "policy_assumptions": {"concentration_review_pct": str(threshold), "concentration_change_pp": "2"},
        "insights": insights, "research": research,
        "status": {"account_connection": "none", "trading_capabilities": "absent",
                   "delivery": "not_verified", "mobile_rendering": "not_verified",
                   "quote_feed": "synthetic" if sample else "manual_import"},
        "constraints": ["Recommendation only", "No financial permissions", "Budget is user supplied; no scheduled purchases"],
        "opportunities": research.get("opportunities", []),
        "follow_up_contract": "Use this report_id and its source/thesis versions. Retrieve newer data explicitly; do not silently mix dates.",
    }
    report["report_id"] = "brief-" + digest(report)[:20]
    text = render_markdown(report)
    # The main view is capped at 360 words, approximately 2 minutes at 180 wpm.
    count = len(re.findall(r"\S+", text))
    if count > 360:
        raise ValueError("Briefing exceeds the two-minute reading budget")
    report["reading_words"] = count
    report["estimated_read_seconds"] = round(count / 180 * 60)
    return report


def render_markdown(report: dict) -> str:
    s = report["analysis"]["summary"]
    marker = "SYNTHETIC DEMO — NOT YOUR PORTFOLIO" if report["mode"] == "sample" else "MANUAL IMPORT — NOT LIVE ACCOUNT DATA"
    money = lambda value: f"${Decimal(value):,.2f}"
    lines = [f"# Investment briefing · {marker}", f"As of {report['as_of']} · {report.get('report_id', 'pending')}",
             f"Portfolio: **{money(s['equity'])}** · Net contributions: {money(s['net_contributions'])} · Investment gain: {money(s['gain'])}.",
             f"Flow-adjusted return: **{s['twr_pct']}%** · Benchmark: {s['benchmark_twr_pct']}% · Maximum drawdown: {s['max_drawdown_pct']}%."]
    change = report.get("changes_since_previous")
    lines.append((f"Since {change['since']}: value changed {money(change['value_change'])}; "
                  f"net contributions {money(change['net_external_flows'])}; investment result {money(change['investment_gain'])}.") if change else
                 "Changes since previous briefing: unavailable until a comparable prior report exists.")
    if not report["insights"]:
        lines.append("No material research or allocation change requires attention in this dataset.")
    sources = {source["id"]: source for source in report["research"].get("sources", [])}
    for insight in report["insights"]:
        citations = " ".join(f"[{_markdown_text(source_id)}](<{sources[source_id]['url']}>)" for source_id in insight["source_ids"][:2])
        lines.append(f"- **{_markdown_text(insight['symbol'])} — {_markdown_text(insight['title'])} [{insight['kind']}]:** {_markdown_text(insight['text'])} {citations}".rstrip())
    if report["mode"] == "sample":
        lines.append("All companies, prices, developments and benchmark values in this demo are fictional. No current S&P 500 performance is claimed.")
    else:
        lines.append("Portfolio freshness depends on your latest import. Missing transactions can invalidate results; reconcile to your statement.")
    lines.append("Sources and methodology are in the linked report context. Recommendations only; you decide and execute independently.")
    return "\n\n".join(lines) + "\n"
