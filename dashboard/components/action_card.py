"""
Action Card Component - Stage 1 Frontend
Human-Centered Emergency Decision Cards translating algorithmic computations into
plain-English, binary-choice executive recommendations ("What Happened / Recommendation").
"""

from typing import Dict, Any
import streamlit as st


class ActionCardRenderer:
    """Renders human-centered decision cards with binary approval states."""

    def render_action_cards(
        self,
        risk_data: Dict[str, Any],
        ems_route: Dict[str, Any],
        fire_active: bool,
        seismic_magnitude: float,
        speed_anomaly: bool,
        rainfall_mm: float
    ):
        """
        Render actionable decision cards based on active hazard telemetry.
        """
        st.markdown(
            """
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">
                <h3 style="margin:0; font-size:16px; font-weight:800; color:#FFFFFF;">🚨 Human-Centered Action Directives</h3>
                <span style="font-size:11px; background:rgba(239,68,68,0.18); color:#EF4444; border:1px solid rgba(239,68,68,0.4); padding:3px 8px; border-radius:99px; font-weight:700;">Zero Alert Fatigue</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # -------------------------------------------------------------
        # Scenario 1: Flood Inundation at Bellandur Underpass
        # -------------------------------------------------------------
        if rainfall_mm >= 45.0:
            water_depth_cm = round((rainfall_mm - 30.0) * 0.75, 1)
            is_approved = st.session_state.get("action_approved_flood", False)

            status_badge = (
                "<span style='background:rgba(16,185,129,0.2); color:#10B981; border:1px solid #10B981; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800;'>✓ OVERRIDE APPROVED</span>"
                if is_approved else
                "<span style='background:rgba(239,68,68,0.2); color:#EF4444; border:1px solid #EF4444; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800;'>ACTION REQUIRED</span>"
            )

            st.markdown(
                f"""
                <div style="background:#1E293B; border-left:4px solid #EF4444; border-radius:12px; padding:16px; margin-bottom:12px; border-top:1px solid #334155; border-right:1px solid #334155; border-bottom:1px solid #334155;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#38BDF8; text-transform:uppercase;">Flood Inundation Breach</span>
                            <h4 style="margin:2px 0 0 0; color:#FFFFFF; font-size:15px; font-weight:800;">Bellandur ORR Underpass Submerged ({water_depth_cm}cm)</h4>
                        </div>
                        {status_badge}
                    </div>
                    <div style="background:#0F172A; padding:10px 12px; border-radius:8px; margin:8px 0; font-size:12.5px; color:#E2E8F0; line-height:1.4;">
                        <b>What Happened:</b> Torrential runoff exceeding 45mm/hr has submerged the low-elevation service road. Water level is {water_depth_cm}cm deep. Impassable for ambulances and small passenger vehicles.
                    </div>
                    <div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">
                        <b>Recommendation:</b> Divert EMS Unit 108 via <b>Sarjapur Elevated Flyover Corridor</b> (+2.1 min detour). Lock Bellandur service road signals to Forced Red.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                if not is_approved:
                    if st.button("✅ Approve Diversion via Sarjapur Flyover (+2.1 min)", key="btn_app_flood", use_container_width=True):
                        st.session_state["action_approved_flood"] = True
                        st.rerun()
                else:
                    if st.button("↩️ Revert Diversion", key="btn_rev_flood", use_container_width=True):
                        st.session_state["action_approved_flood"] = False
                        st.rerun()
            with col2:
                if not is_approved:
                    if st.button("❌ Decline Override", key="btn_dec_flood", use_container_width=True):
                        st.info("Direct route retained. Driver notified of hazardous water levels.")

        # -------------------------------------------------------------
        # Scenario 2: Ecospace Fire Outbreak
        # -------------------------------------------------------------
        if fire_active:
            is_evac_approved = st.session_state.get("action_approved_fire", False)
            fire_badge = (
                "<span style='background:rgba(16,185,129,0.2); color:#10B981; border:1px solid #10B981; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800;'>✓ EVACUATION ACTIVE</span>"
                if is_evac_approved else
                "<span style='background:rgba(249,115,22,0.2); color:#F97316; border:1px solid #F97316; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:800;'>CRITICAL DISPATCH</span>"
            )

            st.markdown(
                f"""
                <div style="background:#1E293B; border-left:4px solid #F97316; border-radius:12px; padding:16px; margin-bottom:12px; border-top:1px solid #334155; border-right:1px solid #334155; border-bottom:1px solid #334155;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
                        <div>
                            <span style="font-size:11px; font-weight:800; color:#F97316; text-transform:uppercase;">Conflagration Incident</span>
                            <h4 style="margin:2px 0 0 0; color:#FFFFFF; font-size:15px; font-weight:800;">Ecospace IT Corridor Perimeter Fire Outbreak</h4>
                        </div>
                        {fire_badge}
                    </div>
                    <div style="background:#0F172A; padding:10px 12px; border-radius:8px; margin:8px 0; font-size:12.5px; color:#E2E8F0; line-height:1.4;">
                        <b>What Happened:</b> Simulated cellular automata boundary detected active heat propagation. Downwind smoke threatens Ecospace Campus Blocks 1A & 1B (Occupancy: 4,200).
                    </div>
                    <div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">
                        <b>Recommendation:</b> Execute immediate phase-1 evacuation toward <b>Kaikondrahalli Lake Safe Assembly Grounds</b>. Dispatch Fire Tender Engine-7.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            col1, col2 = st.columns([2, 1])
            with col1:
                if not is_evac_approved:
                    if st.button("🚨 Broadcast Evacuation to Kaikondrahalli Grounds [Approve]", key="btn_app_fire", use_container_width=True):
                        st.session_state["action_approved_fire"] = True
                        st.rerun()
                else:
                    if st.button("⏹️ Conclude Evacuation Protocol", key="btn_rev_fire", use_container_width=True):
                        st.session_state["action_approved_fire"] = False
                        st.rerun()
            with col2:
                if not is_evac_approved:
                    if st.button("Hold Evacuation", key="btn_dec_fire", use_container_width=True):
                        st.warning("Evacuation held. On-site marshals dispatched for verification.")

        # -------------------------------------------------------------
        # Scenario 3: Seismic Shock Warning
        # -------------------------------------------------------------
        if seismic_magnitude >= 4.5:
            st.markdown(
                f"""
                <div style="background:#1E293B; border-left:4px solid #A855F7; border-radius:12px; padding:16px; margin-bottom:12px; border-top:1px solid #334155; border-right:1px solid #334155; border-bottom:1px solid #334155;">
                    <span style="font-size:11px; font-weight:800; color:#C084FC; text-transform:uppercase;">Seismic Structural Alarm</span>
                    <h4 style="margin:2px 0 6px 0; color:#FFFFFF; font-size:15px; font-weight:800;">Richter {seismic_magnitude:.1f} Ground Motion Detected</h4>
                    <div style="background:#0F172A; padding:10px 12px; border-radius:8px; margin:8px 0; font-size:12.5px; color:#E2E8F0; line-height:1.4;">
                        <b>What Happened:</b> Strong ground motion registered across ORR corridor. Elevated flyovers and high-occupancy IT towers placed on structural yellow alert.
                    </div>
                    <div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">
                        <b>Recommendation:</b> Direct civilian foot traffic into designated open-air assembly grounds: Kaikondrahalli Lake (5,000 capacity) & Bellandur Sports Ground.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("📢 Broadcast Public Shelter Directives via Sirens & PWA [Approve]", key="btn_quake_shelter"):
                st.success("Public Shelter Directives relayed to all citizen mobile devices!")

        # -------------------------------------------------------------
        # Scenario 4: Speed Collapse (40 to 0 km/h) Anomaly
        # -------------------------------------------------------------
        if speed_anomaly:
            st.markdown(
                """
                <div style="background:#1E293B; border-left:4px solid #F43F5E; border-radius:12px; padding:16px; margin-bottom:12px; border-top:1px solid #334155; border-right:1px solid #334155; border-bottom:1px solid #334155;">
                    <span style="font-size:11px; font-weight:800; color:#F43F5E; text-transform:uppercase;">Telemetry Velocity Anomaly</span>
                    <h4 style="margin:2px 0 6px 0; color:#FFFFFF; font-size:15px; font-weight:800;">Sudden Speed Drop: 40 km/h ➔ 0 km/h Standstill</h4>
                    <div style="background:#0F172A; padding:10px 12px; border-radius:8px; margin:8px 0; font-size:12.5px; color:#E2E8F0; line-height:1.4;">
                        <b>What Happened:</b> Sensor probes detected immediate velocity collapse on Bellandur ORR approach. Likely vehicle stall or road blockade.
                    </div>
                    <div style="font-size:12px; color:#94A3B8; margin-bottom:10px;">
                        <b>Recommendation:</b> Engage dynamic message signs at Iblur to redirect approaching traffic onto Sarjapur road bypass before gridlock spills over.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            col1, col2 = st.columns([2, 1])
            with col1:
                if st.button("🔄 Activate Variable Message Sign Divert [Approve]", key="btn_app_vms", use_container_width=True):
                    st.success("VMS Displays active at Iblur Flyover! Inbound traffic diverted.")
            with col2:
                if st.button("Dismiss", key="btn_dec_vms", use_container_width=True):
                    st.write("Telemetry acknowledged.")

        # Default Nominal State
        if rainfall_mm < 45.0 and not fire_active and seismic_magnitude < 4.5 and not speed_anomaly:
            st.markdown(
                """
                <div style="background:#1E293B; border-left:4px solid #10B981; border-radius:12px; padding:16px; border-top:1px solid #334155; border-right:1px solid #334155; border-bottom:1px solid #334155;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:#10B981; font-size:18px;">✅</span>
                        <div>
                            <h4 style="margin:0; color:#FFFFFF; font-size:14px; font-weight:700;">Corridor Nominal • No Critical Action Required</h4>
                            <p style="margin:2px 0 0 0; color:#94A3B8; font-size:12px;">Traffic flowing at 40-55 km/h along ORR Bellandur. Underpass drainage clear.</p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
