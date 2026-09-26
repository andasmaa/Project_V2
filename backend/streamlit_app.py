"""
Compliance / Governance dashboard for the AWB banking AI assistant.

Run from backend/:
    streamlit run streamlit_app.py

This dashboard reads the governance PostgreSQL store directly. It does not
reimplement the banking workflow and it never displays raw message content.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import streamlit as st

from governance.audit_schema import GovernanceDBError, connection_scope
from governance.integrity import verify_all
from governance.metrics import GovernanceMetrics
from governance.models import Tier


st.set_page_config(
    page_title="AWB AI Governance",
    page_icon="🛡️",
    layout="wide",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


@st.cache_data(ttl=10)
def load_summary() -> dict[str, Any]:
    return GovernanceMetrics().summary()


@st.cache_data(ttl=10)
def load_risk_counts() -> dict[str, int]:
    return GovernanceMetrics().risk_counts()


@st.cache_data(ttl=10)
def load_escalated_risk_counts() -> dict[str, int]:
    return GovernanceMetrics().escalated_risk_counts()


@st.cache_data(ttl=10)
def load_event_counts() -> dict[str, int]:
    return GovernanceMetrics().event_counts()


def verify_database() -> dict[str, Any]:
    report = verify_all()
    return _json_safe(report)


def get_trace(session_id: str) -> dict[str, list]:
    return GovernanceMetrics().session_trace(session_id)


def main() -> None:
    st.title("AI Governance & Compliance Dashboard")
    st.caption(
        "Auditability, risk, HITL decisions and hash-chain integrity. "
        "No raw customer message content is displayed."
    )

    if st.sidebar.button("Refresh data"):
        load_summary.clear()
        load_risk_counts.clear()
        load_escalated_risk_counts.clear()
        load_event_counts.clear()
        st.rerun()

    try:
        summary = load_summary()
        risk_counts = load_risk_counts()
        escalated = load_escalated_risk_counts()
        event_counts = load_event_counts()
    except Exception as exc:
        st.error("Unable to read the governance PostgreSQL database.")
        st.code(str(exc))
        st.info(
            "Check GOVERNANCE_DB_* in .env and run "
            "`python -m governance.audit_schema --init` first."
        )
        return

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------
    st.header("Overview")

    total_events = (
        summary["l1_events"]
        + summary["l2_events"]
        + summary["l3_events"]
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("L1 interactions", summary["l1_events"])
    c2.metric("L2 executions", summary["l2_events"])
    c3.metric("L3 governance", summary["l3_events"])
    c4.metric("HITL required", summary["hitl_required"])
    c5.metric("Total audit events", total_events)

    if summary["hitl_required"]:
        approved = summary["hitl_approved"]
        rejected = summary["hitl_rejected"]
        decided = approved + rejected
        pending = max(summary["hitl_required"] - decided, 0)
    else:
        approved = rejected = pending = 0

    st.subheader("Human-in-the-loop status")
    h1, h2, h3 = st.columns(3)
    h1.metric("Approved", approved)
    h2.metric("Rejected", rejected)
    h3.metric("Undecided / pending", pending)

    # ------------------------------------------------------------------
    # Risk distribution
    # ------------------------------------------------------------------
    st.header("Risk distribution")

    if risk_counts:
        import pandas as pd
        import plotly.express as px

        risk_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        rows = [
            {"Risk level": level, "Events": risk_counts.get(level, 0)}
            for level in risk_order
        ]
        df = pd.DataFrame(rows)

        col1, col2 = st.columns(2)

        with col1:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )

        with col2:
            fig = px.bar(
                df,
                x="Risk level",
                y="Events",
                category_orders={"Risk level": risk_order},
                title="Risk level across L1 interactions",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No risk records have been written yet.")

    if escalated:
        st.subheader("Escalated governance events")
        import pandas as pd
        st.dataframe(
            pd.DataFrame(
                [
                    {"Risk level": k, "Escalated events": v}
                    for k, v in sorted(escalated.items())
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ------------------------------------------------------------------
    # Event lifecycle
    # ------------------------------------------------------------------
    st.header("Audit lifecycle")

    lifecycle = [
        "CHAT_REQUEST",
        "MODERATION_RESULT",
        "ROUTING_DECISION",
        "RAG_RETRIEVAL",
        "AGENT_EXECUTION",
        "JUDGE_EVALUATION",
        "HITL_REQUIRED",
        "HITL_DECISION",
        "CHAT_RESPONSE",
    ]

    lifecycle_counts = {
        event: event_counts.get(event, 0)
        for event in lifecycle
    }

    import pandas as pd
    st.dataframe(
        pd.DataFrame(
            [
                {"Event": event, "Occurrences": count}
                for event, count in lifecycle_counts.items()
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------
    st.header("Audit-chain integrity")

    if st.button("Verify hash chains"):
        try:
            integrity = verify_database()
            st.session_state["integrity_result"] = integrity
        except Exception as exc:
            st.session_state["integrity_result"] = {
                "error": str(exc)
            }

    integrity_result = st.session_state.get("integrity_result")

    if integrity_result:
        if "error" in integrity_result:
            st.error(integrity_result["error"])
        else:
            all_valid = bool(integrity_result.get("all_valid", False))
            if all_valid:
                st.success("All governance audit chains are valid.")
            else:
                st.error("At least one governance audit chain is invalid.")

            st.json(integrity_result)
    else:
        st.info("Click “Verify hash chains” to run the integrity verifier.")

    # ------------------------------------------------------------------
    # Session trace
    # ------------------------------------------------------------------
    st.header("Session trace")

    session_id = st.text_input(
        "Session ID",
        placeholder="Paste a session_id from your application logs",
    )

    if session_id:
        try:
            trace = get_trace(session_id)
            if not any(trace.values()):
                st.warning("No governance events found for this session.")
            else:
                for tier in ("L1", "L2", "L3"):
                    events = trace.get(tier, [])
                    st.subheader(f"{tier} — {len(events)} events")
                    if events:
                        # Never render the entire DB row blindly: exclude
                        # any future raw-content fields if they are added.
                        safe_events = []
                        for event in events:
                            safe = dict(event)
                            for sensitive_key in (
                                "message",
                                "raw_message",
                                "original_message",
                                "content",
                                "raw_content",
                            ):
                                safe.pop(sensitive_key, None)
                            safe_events.append(_json_safe(safe))
                        st.json(safe_events)
        except Exception as exc:
            st.error(f"Could not load session trace: {exc}")

    # ------------------------------------------------------------------
    # Technical information
    # ------------------------------------------------------------------
    st.sidebar.divider()
    st.sidebar.caption(
        f"Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    st.sidebar.caption(
        "Governance layer: L1 Interaction / L2 Execution / L3 Governance"
    )


if __name__ == "__main__":
    main()
