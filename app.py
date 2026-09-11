
            "parameter": "On-throttle differential",
            "direction": "increase",
            "amount_hint": "+5% to +10%",
            "reason": "Exit understeer — lock differential on power to help the car pull through corners.",
            "validation_metric": "us_exit frequency",
            "weight": 0.8,
        },
        {
            "parameter": "Front wing",
            "direction": "increase",
            "amount_hint": "+1",
            "reason": "Front end grip on power.",
            "validation_metric": "us_exit count",
            "weight": 0.7,
        },
    ],
    "lock_front": [
        {
            "parameter": "Brake bias (% front)",
            "direction": "increase",
            "amount_hint": "more forward +1% to +2% (toward more forward 70%)",
            "reason": "Front lockup — move toward more forward 70% (higher % front) to offload braking work from front tires.",
            "validation_metric": "lock_front frequency; front tire temp drop",
            "weight": 1.2,
        },
        {
            "parameter": "Brake pressure",
            "direction": "decrease",
            "amount_hint": "−2% to −5% (e.g. 100% → 95%)",
            "reason": "Reduces peak hydraulic pressure so threshold braking doesn't instantly lock wheels.",
            "validation_metric": "lock_front count per lap",
            "weight": 1.0,
        },
        {
            "parameter": "Front tire pressure",
            "direction": "decrease",
            "amount_hint": "−0.5 to −1.0 psi",
            "reason": "Lower pressure increases front contact patch / grip under braking.",
            "validation_metric": "Front tire temp and lock frequency",
            "weight": 0.7,
        },
    ],
    "lock_rear": [
        {
            "parameter": "Brake bias (% front)",
            "direction": "decrease",
            "amount_hint": "more rearward −1% to −2% (toward more rearward 50%)",
            "reason": "Rear lockup — move toward more rearward 50% (lower % front) to apply more braking force to the rear.",
            "validation_metric": "lock_rear frequency",
            "weight": 1.2,
        },
        {
            "parameter": "Off-throttle differential",
            "direction": "increase",
            "amount_hint": "+5% to +10%",
            "reason": "More coast locking stabilizes rear under deceleration.",
            "validation_metric": "lock_rear count",
            "weight": 0.9,
        },
    ],
    "traction_spin": [
        {
            "parameter": "On-throttle differential",
            "direction": "decrease",
            "amount_hint": "−10% to −20%",
            "reason": "Wheelspin on exit — lower locked diff action lets outside/inside wheels differentiate better.",
            "validation_metric": "κ_r peak on exit; traction_spin count",
            "weight": 1.3,
        },
        {
            "parameter": "Rear tire pressure",
            "direction": "decrease",
            "amount_hint": "−0.5 to −1.0 psi",
            "reason": "Larger contact patch for rear power delivery.",
            "validation_metric": "Rear tire temps and longitudinal slip",
            "weight": 0.8,
        },
        {
            "parameter": "Rear spring",
            "direction": "decrease",
            "amount_hint": "−1 to −2",
            "reason": "Softer rear spring helps rear mechanical grip over bumps on throttle.",
            "validation_metric": "traction_spin frequency",
            "weight": 0.7,
        },
    ],
    "tires_cold": [
        {
            "parameter": "Front tire pressure",
            "direction": "increase",
            "amount_hint": "+0.5 to +1.0 psi",
            "reason": "Higher pressure builds tire carcass heat faster.",
            "validation_metric": "tyre_temp_f reaching 70°C sooner",
            "weight": 0.9,
        },
        {
            "parameter": "Rear tire pressure",
            "direction": "increase",
            "amount_hint": "+0.5 to +1.0 psi",
            "reason": "Higher rear pressure builds rear tire temperature.",
            "validation_metric": "tyre_temp_r reaching 70°C",
            "weight": 0.9,
        },
    ],
    "tires_hot": [
        {
            "parameter": "Front tire pressure",
            "direction": "decrease",
            "amount_hint": "−0.5 to −1.0 psi",
            "reason": "Lower pressure reduces flexing/overheating.",
            "validation_metric": "tyre_temp staying below 95°C",
            "weight": 0.9,
        },
        {
            "parameter": "Rear tire pressure",
            "direction": "decrease",
            "amount_hint": "−0.5 to −1.0 psi",
            "reason": "Lower rear pressure drops running temperature.",
            "validation_metric": "tyre_temp_r",
            "weight": 0.9,
        },
    ],
}


def build_setup_recommendations(
    summaries: list[IssueSummary], setup: dict[str, Any]
) -> list[SetupChange]:
    """
    Map diagnosed issues to ranked, feasible setup changes.
    De-duplicates recommendations across issues (accumulates weights / links).
    """
    agg: dict[str, dict[str, Any]] = {}

    for s in summaries:
        templates = ISSUE_TO_CHANGES.get(s.issue_id, [])
        for t in templates:
            param = t["parameter"]
            # Weight scales with issue criticality + template weight
            weight = t["weight"] * max(s.criticality, 0.2) * (1.0 + s.mean_severity * 0.5)
            if param not in agg:
                agg[param] = {
                    "parameter": param,
                    "direction": t["direction"],
                    "amount_hint": t["amount_hint"],
                    "reasons": [f"[{s.name} ({s.tier})]: {t['reason']}"],
                    "linked_issues": [s.name],
                    "priority_score": weight,
                    "validation_metric": t["validation_metric"],
                    "issue_id": s.issue_id,
                }
            else:
                agg[param]["priority_score"] += weight
                if s.name not in agg[param]["linked_issues"]:
                    agg[param]["linked_issues"].append(s.name)
                agg[param]["reasons"].append(f"[{s.name}]: {t['reason']}")

    results: list[SetupChange] = []
    for param, data in agg.items():
        feas, blocked_msg, cur, lo, hi = feasibility(param, data["direction"], setup)
        results.append(
            SetupChange(
                parameter=param,
                direction=data["direction"],
                amount_hint=data["amount_hint"],
                reason=" | ".join(data["reasons"][:3]),
                linked_issues=data["linked_issues"],
                priority=float(data["priority_score"]),
                validation_metric=data["validation_metric"],
                current=cur,
                min_v=lo,
                max_v=hi,
                feasible=feas,
                blocked_reason=blocked_msg,
                issue_id=data["issue_id"],
            )
        )

    # Sort: feasible first, then by priority score descending
    results.sort(key=lambda x: (not x.feasible, -x.priority))
    return results


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Virtual Race Engineer — Telemetry Analyzer",
        page_icon="🏎️",
        layout="wide",
    )

    st.title("🏎️ Virtual Race Engineer")
    st.markdown(
        "**F1 25 / F1 26 Telemetry Analyzer** — Upload a game logger export "
        "(CSV or TSV, up to 266 columns). "
        "Diagnoses balance, braking, and traction issues, grades your session, "
        "compares your driving vs your best lap, and ranks setup adjustments with reasons."
    )

    with st.sidebar:
        st.header("1. Upload Telemetry")
        uploaded = st.file_uploader(
            "Telemetry CSV / TSV export",
            type=["csv", "tsv", "txt"],
            help="Expects F1 game logger schema (266 columns).",
        )
        st.markdown("---")
        st.header("2. Diagnostic Tuning")
        us_thresh = st.slider("Understeer slip threshold (rad)", 0.01, 0.08, US_ALPHA_THRESH, 0.005)
        os_thresh = st.slider("Oversteer slip threshold (rad)", 0.01, 0.08, OS_ALPHA_THRESH, 0.005)
        lock_slip = st.slider("Brake lock slip threshold", 0.03, 0.20, LOCK_SLIP, 0.01)
        spin_slip = st.slider("Throttle wheelspin threshold", 0.05, 0.25, SPIN_SLIP, 0.01)

        st.markdown("---")
        st.markdown(
            "**Setup limits note:** ARB (1–21), Wings (0–50), "
            "Springs (1–41), Ride height (F:15–35, R:40–60), "
            "Camber (F:−3.5 to −2.5, R:−2 to −1), "
            "Toe (F:0–0.2, R:0.1–0.25), "
            "Pressures (F:22.5–29.5, R:20.5–26.5 psi), "
            "Brake bias (50%–70% front), Diffs (10%–100%)."
        )

    if uploaded is None:
        st.info("👈 Please upload a telemetry file in the sidebar to begin analysis.")
        # Show dummy template info
        with st.expander("Expected columns & schema info"):
            st.markdown(
                "The analyzer expects standard F1 game telemetry exports with channels such as:\n"
                "- `velocity_X`, `velocity_Y`, `velocity_Z`, `gforce_X`, `gforce_Y`\n"
                "- `wheel_slip_angle_0..3`, `wheel_slip_ratio_0..3`, `wheel_speed_0..3`\n"
                "- `throttle`, `brake`, `steering`, `gear`, `speed_kph`, `lap_number`, `lap_distance`, `lap_time`\n"
                "- Setup channels: `wing_setup_0`, `wing_setup_1`, `arb_setup_0`, `arb_setup_1`, "
                "`diff_onThrottle_setup`, `front_brake_bias`, `tyre_press_setup_0`, etc."
            )
        return

    with st.spinner("Parsing and cleaning telemetry (260+ columns)..."):
        try:
            df = load_telemetry(uploaded)
        except Exception as e:
            st.error(f"Error loading telemetry file: {e}")
            return

    if df.empty:
        st.error("The loaded dataframe is empty.")
        return

    # Extract setup snapshot
    setup_info = extract_setup(df)

    # Run diagnostics
    events, summaries = run_diagnostics(
        df,
        us_alpha=us_thresh,
        os_alpha=os_thresh,
        lock_slip=lock_slip,
        spin_slip=spin_slip,
    )

    # Driver analysis vs best lap
    driver_data = analyze_driver(df)

    # Session grade
    grade = session_grade(df, summaries, driver_data)

    # Setup recommendations (filtered / ranked with feasibility)
    setup_recs = build_setup_recommendations(summaries, setup_info)

    # -------------------------------------------------
    # Top metrics bar
    # -------------------------------------------------
    col1, col2, col3, col4, col5 = st.columns(5)
    total_samples = len(df)
    valid_samples = int(df["valid_sample"].sum()) if "valid_sample" in df.columns else total_samples
    lap_times = driver_data.get("lap_times", [])
    best_t = driver_data.get("best_lap_time")

    with col1:
        st.metric("Session Grade", f"{grade['letter']} ({grade['score']}/100)")
    with col2:
        st.metric("Best Lap", format_lap_time(best_t) if best_t else "—")
    with col3:
        st.metric("Timed Laps", len(lap_times))
    with col4:
        st.metric("Issues Flagged", len(summaries))
    with col5:
        st.metric("Valid Samples", f"{valid_samples:,} / {total_samples:,}")

    st.markdown("---")

    # Tabs for main views
    tab_overview, tab_issues, tab_setup, tab_driver, tab_raw = st.tabs(
        ["📊 Overview & Grade", "🔍 Issue Diagnostics", "⚙️ Setup Advisor", "📈 Driver vs Best Lap", "📋 Raw Data & Setup"]
    )

    with tab_overview:
        st.subheader("Session Evaluation & Component Breakdown")
        gcol1, gcol2 = st.columns([1, 1])

        with gcol1:
            st.markdown(f"### Overall Grade: **{grade['letter']}** ({grade['score']} / 100)")
            st.caption(grade["disclaimer"])
            for name, comp in grade["components"].items():
                st.progress(
                    int(comp["score"]),
                    text=f"**{name}**: {comp['score']:.0f}/100 (weight {comp['weight']*100:.0f}%) — {comp['detail']}",
                )

        with gcol2:
            st.subheader("Top Critical Issues")
            if not summaries:
                st.success("No significant balance or mechanical issues flagged in this session!")
            else:
                for s in summaries[:5]:
                    tier_emoji = {"S": "🔴", "A": "🟠", "B": "🟡", "C": "🟢"}.get(s.tier, "⚪")
                    st.markdown(
                        f"{tier_emoji} **Tier {s.tier} — {s.name}** "
                        f"(Freq: {s.events_per_lap:.1f}/lap, Present on {s.lap_presence_pct:.0f}% of laps, "
                        f"Sev: {s.mean_severity:.2f})"
                    )

        st.markdown("### Lap Times Summary")
        if lap_times:
            lt_df = pd.DataFrame(lap_times, columns=["Lap", "Time (s)"])
            lt_df["Formatted"] = lt_df["Time (s)"].apply(format_lap_time)
            st.dataframe(lt_df, hide_index=True, use_container_width=True)
        else:
            st.info("No completed flying laps detected.")

    with tab_issues:
        st.subheader("Issue Diagnostics & Track Hotspots")
        if not summaries:
            st.success("Clean session! No issues met the diagnostic thresholds.")
        else:
            filter_tier = st.multiselect(
                "Filter by Severity Tier", ["S", "A", "B", "C"], default=["S", "A", "B", "C"]
            )
            filtered_sums = [s for s in summaries if s.tier in filter_tier]

            for s in filtered_sums:
                tier_color = {"S": "red", "A": "orange", "B": "gold", "C": "green"}.get(s.tier, "grey")
                with st.expander(
                    f"Tier {s.tier} | {s.name} — {s.count} occurrences across {s.laps_present}/{s.total_laps} laps ({s.lap_presence_pct:.0f}%)"
                ):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"**Confidence**: {s.confidence * 100:.0f}%")
                        st.markdown(f"**Mean Severity**: {s.mean_severity:.2f} (Max: {s.max_severity:.2f})")
                        st.markdown(f"**Events / Lap**: {s.events_per_lap:.2f}")
                        hot_str = ", ".join(f"{int(m)} m" for m in s.hot_corners_m[:4])
                        st.markdown(f"**Hotspot Distance Bins**: {hot_str or 'None'}")
                    with col_b:
                        st.markdown("**Sample Details:**")
                        for det in s.sample_details:
                            st.text(f"• {det}")

            # Track scatter of events if lap_distance available
            if "lap_distance" in df.columns and events:
                st.subheader("Issue Events Map (Distance vs Lap)")
                ev_df = pd.DataFrame([asdict(e) for e in events])
                if not ev_df.empty and "distance_m" in ev_df.columns:
                    fig = px.scatter(
                        ev_df,
                        x="distance_m",
                        y="lap",
                        color="tier" if "tier" in ev_df.columns else "name",
                        hover_data=["name", "speed_kph", "phase", "severity", "detail"],
                        title="Telemetry Issues across Track Distance and Laps",
                        labels={"distance_m": "Lap Distance (m)", "lap": "Lap Number"},
                    )
                    st.plotly_chart(fig, use_container_width=True)

    with tab_setup:
        st.subheader("Ranked Setup Recommendations")
        st.markdown(
            "Generated from diagnosed issues, ranked by impact. "
            "In-game limits are verified against user confirmation."
        )

        if not setup_recs:
            st.success("No setup changes recommended — balance is currently optimal relative to thresholds.")
        else:
            for i, rec in enumerate(setup_recs, 1):
                feas_badge = "✅ Feasible" if rec.feasible else "❌ Blocked / Limit Reached"
                with st.expander(
                    f"Option {i} ({rec.parameter}: {rec.direction.upper()} {rec.amount_hint}) — Priority: {rec.priority:.1f} [{feas_badge}]"
                ):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.markdown(f"**Action**: `{rec.direction.upper()}` by **{rec.amount_hint}**")
                        st.markdown(f"**Reason**: {rec.reason}")
                        st.markdown(f"**Linked Issues**: {', '.join(rec.linked_issues)}")
                        st.markdown(f"**Validation Metric**: _{rec.validation_metric}_")
                    with c2:
                        cur_str = format_setup_value(rec.parameter, rec.current)
                        st.markdown(f"**Current Setup Value**: `{cur_str}`")
                        if not rec.feasible:
                            st.warning(rec.blocked_reason)
                        else:
                            st.success("Within valid setup range.")

    with tab_driver:
        st.subheader("Driver Analysis vs Best Lap")
        notes = driver_data.get("notes", [])
        for n in notes:
            st.markdown(f"- {n}")

        col_b, col_t, col_s = st.columns(3)
        with col_b:
            st.markdown("### 🛑 Brake Notes")
            for b_n in driver_data.get("brake_notes", []):
                st.markdown(f"- {b_n}")
        with col_t:
            st.markdown("### ⚡ Throttle & Exit")
            for t_n in driver_data.get("throttle_notes", []):
                st.markdown(f"- {t_n}")
        with col_s:
            st.markdown("### 🔄 Mid-Corner Scrub")
            for s_n in driver_data.get("scrub_notes", []):
                st.markdown(f"- {s_n}")

        zones = driver_data.get("time_loss_zones", [])
        if zones:
            st.subheader("Top Proxy Time-Loss Zones (vs Best Lap)")
            z_df = pd.DataFrame(zones)
            st.dataframe(z_df, hide_index=True, use_container_width=True)

            # Speed comparison plot if series exists
            delta_df = driver_data.get("delta_series")
            if delta_df is not None and not delta_df.empty:
                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=delta_df["bin"],
                        y=delta_df["speed_kph_ref"],
                        name=f"Best Lap (L{driver_data.get('best_lap', 1):.0f})",
                        line=dict(color="cyan", width=2),
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=delta_df["bin"],
                        y=delta_df["speed_kph_cmp"],
                        name="Comparison Laps Mean",
                        line=dict(color="orange", width=2, dash="dash"),
                    )
                )
                fig.update_layout(
                    title="Speed Profile by Distance Bin (km/h)",
                    xaxis_title="Lap Distance (m)",
                    yaxis_title="Speed (km/h)",
                    template="plotly_dark",
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab_raw:
        st.subheader("Current Car Setup Snapshot")
        setup_table = setup_info.get("table", [])
        if setup_table:
            st.dataframe(pd.DataFrame(setup_table), hide_index=True, use_container_width=True)
        else:
            st.info("No setup channels found in telemetry.")

        st.subheader("Raw Telemetry Preview")
        st.dataframe(df.head(100), use_container_width=True)


if __name__ == "__main__":
    main()
