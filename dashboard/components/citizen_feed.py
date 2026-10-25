"""
Citizen Feed Component - Stage 1 Frontend
Renders real-time visual stream cards representing live crowdsourced hazard reports
originating from the Citizen Mobile PWA along Bellandur / ORR.
"""

from typing import List, Dict, Any
import streamlit as st


class CitizenFeedRenderer:
    """Renders citizen report cards and dispatch handoffs."""

    def __init__(self):
        # Default mock feed tickets
        self.default_tickets = [
            {
                "id": "BLR-HAZ-8921",
                "category": "waterlogging",
                "emoji": "💧",
                "title": "Severe Waterlogging (35cm)",
                "location": "Bellandur Underpass Service Rd",
                "time": "2 mins ago",
                "reporter": "Commuter via PWA",
                "status": "DISPATCHED",
                "ai_verified": True,
                "confidence": "94.8%"
            },
            {
                "id": "BLR-HAZ-8919",
                "category": "gridlock",
                "emoji": "🚗",
                "title": "Deadlock (0 km/h) Stoppage",
                "location": "Ecospace Ingress Gate",
                "time": "8 mins ago",
                "reporter": "Tech Park Security",
                "status": "UNDER_REVIEW",
                "ai_verified": True,
                "confidence": "91.2%"
            },
            {
                "id": "BLR-HAZ-8912",
                "category": "road_block",
                "emoji": "🛑",
                "title": "Downed Tree & Electric Wire",
                "location": "Sakra Hospital Access Corridor",
                "time": "18 mins ago",
                "reporter": "Citizen Volunteer",
                "status": "RESOLVING",
                "ai_verified": True,
                "confidence": "88.5%"
            },
            {
                "id": "BLR-HAZ-8904",
                "category": "ems_obstruction",
                "emoji": "🚑",
                "title": "Ambulance Trapped in Service Lane",
                "location": "Near Iblur Junction Merge",
                "time": "31 mins ago",
                "reporter": "EMS Driver 108",
                "status": "RESOLVED",
                "ai_verified": True,
                "confidence": "96.4%"
            }
        ]

    def render_feed(self, rainfall_mm: float = 0.0, speed_anomaly: bool = False):
        """
        Render interactive stream cards with dispatcher action buttons.
        """
        st.markdown(
            """
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;">
                <h4 style="margin:0; font-size:15px; font-weight:800; color:#FFFFFF;">📱 Citizen Mobile PWA Live Stream</h4>
                <span style="font-size:11px; background:rgba(56,189,248,0.15); color:#38BDF8; padding:3px 8px; border-radius:99px; font-weight:700;">Live Geofenced Telemetry</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        tickets = list(self.default_tickets)

        # Dynamic injection based on simulation triggers
        if rainfall_mm >= 50.0:
            tickets.insert(0, {
                "id": "BLR-HAZ-9004",
                "category": "waterlogging",
                "emoji": "🌊",
                "title": "Flash Inundation Warning",
                "location": "Bellandur Basin Depression",
                "time": "Just now",
                "reporter": "Auto-Sensor Probe #4B",
                "status": "CRITICAL_ALERT",
                "ai_verified": True,
                "confidence": "98.2%"
            })

        for i, t in enumerate(tickets[:4]):
            status_color = "#38BDF8"
            if t["status"] in ["CRITICAL_ALERT", "DISPATCHED"]:
                status_color = "#EF4444"
            elif t["status"] == "RESOLVED":
                status_color = "#10B981"

            st.markdown(
                f"""
                <div style="background:#1E293B; border:1px solid #334155; border-radius:10px; padding:12px 14px; margin-bottom:8px;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span style="font-size:20px;">{t['emoji']}</span>
                            <div>
                                <div style="font-size:13px; font-weight:700; color:#FFFFFF;">{t['title']}</div>
                                <div style="font-size:11.5px; color:#94A3B8;">📍 {t['location']} • <span style="color:#64748B;">{t['time']}</span></div>
                            </div>
                        </div>
                        <span style="font-size:10px; font-weight:800; color:{status_color}; background:rgba(15,23,42,0.8); border:1px solid {status_color}; padding:2px 7px; border-radius:99px;">{t['status']}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px; font-size:11px; color:#64748B;">
                        <span>Source: {t['reporter']}</span>
                        <span style="color:#10B981;">✓ Edge AI Conf: {t['confidence']}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Dispatcher Ack", key=f"ack_{t['id']}_{i}", use_container_width=True):
                    st.toast(f"Ticket {t['id']} acknowledged by Command Desk.")
            with c2:
                if st.button(f"BBMP Handoff", key=f"handoff_{t['id']}_{i}", use_container_width=True):
                    st.toast(f"Ticket {t['id']} pushed to BBMP Sahaaya 2.0 API.")
