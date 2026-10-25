"""
Control Panel Component - Stage 1 Frontend
Interactive simulation controls for rainfall intensity, wind vectors, earthquake magnitude,
and speed collapse anomalies along Bengaluru's Bellandur / ORR corridor.
"""

from typing import Dict, Any
import streamlit as st


class ControlPanel:
    """Manages Streamlit sidebar sliders, toggles, and preset scenario triggers."""

    def render_controls(self) -> Dict[str, Any]:
        """
        Renders sidebar control widgets and returns reactive simulation parameters.
        """
        st.sidebar.markdown(
            """
            <div style="background:#1E293B; padding:12px 14px; border-radius:10px; border:1px solid #334155; margin-bottom:14px;">
                <div style="font-size:11px; font-weight:800; color:#38BDF8; text-transform:uppercase; letter-spacing:0.05em;">Simulation Engine</div>
                <div style="font-size:16px; font-weight:800; color:#FFFFFF;">Hazard Control Hub</div>
                <div style="font-size:11px; color:#94A3B8;">Sector: Bengaluru ORR / Bellandur</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # -------------------------------------------------------------
        # Quick Scenario Presets
        # -------------------------------------------------------------
        st.sidebar.markdown("<p style='font-size:12px; font-weight:700; color:#CBD5E1; margin-bottom:6px;'>⚡ Quick Disaster Scenarios</p>", unsafe_allow_html=True)
        col1, col2 = st.sidebar.columns(2)
        preset_rain = False
        preset_fire = False
        preset_quake = False
        preset_jam = False
        preset_reset = False

        with col1:
            if st.button("🌊 Monsoon Flood", use_container_width=True, key="btn_flood"):
                preset_rain = True
            if st.button("🔥 Ecospace Fire", use_container_width=True, key="btn_fire"):
                preset_fire = True
        with col2:
            if st.button("💥 Richter 5.8 Shock", use_container_width=True, key="btn_quake"):
                preset_quake = True
            if st.button("🛑 0km/h Gridlock", use_container_width=True, key="btn_jam"):
                preset_jam = True

        if st.sidebar.button("🔄 Reset Nominal Conditions", use_container_width=True, key="btn_reset"):
            preset_reset = True

        st.sidebar.markdown("<hr style='border:none; border-top:1px solid #334155; margin:14px 0;'/>", unsafe_allow_html=True)

        # -------------------------------------------------------------
        # Environmental Hazard Sliders
        # -------------------------------------------------------------
        st.sidebar.markdown("<p style='font-size:13px; font-weight:800; color:#38BDF8;'>🌧️ 1. Hydrological Flood Modeling</p>", unsafe_allow_html=True)
        
        default_rain = 15.0
        if preset_rain:
            default_rain = 75.0
        elif preset_reset:
            default_rain = 10.0

        rainfall_mm = st.sidebar.slider(
            "Rainfall Severity (mm / hr)",
            min_value=0.0,
            max_value=140.0,
            value=default_rain,
            step=5.0,
            help="Threshold >45mm submerges Bellandur Underpass and raises the blue water polygon."
        )

        st.sidebar.markdown("<p style='font-size:13px; font-weight:800; color:#FB923C; margin-top:10px;'>🔥 2. Wildland / Tech Park Fire Spread</p>", unsafe_allow_html=True)
        fire_active_default = preset_fire
        fire_active = st.sidebar.toggle("Ignite Simulated Fire Origin (Ecospace)", value=fire_active_default, key="toggle_fire")

        wind_speed_kmh = st.sidebar.slider(
            "Wind Velocity (km/h)",
            min_value=5.0,
            max_value=70.0,
            value=35.0 if preset_fire else 15.0,
            step=5.0
        )
        wind_direction_deg = st.sidebar.slider(
            "Wind Direction Vector (°)",
            min_value=0,
            max_value=360,
            value=55,
            step=15
        )

        st.sidebar.markdown("<p style='font-size:13px; font-weight:800; color:#C084FC; margin-top:10px;'>⚡ 3. Seismic Ground Motion</p>", unsafe_allow_html=True)
        default_quake = 5.8 if preset_quake else 0.0
        seismic_magnitude = st.sidebar.slider(
            "Earthquake Magnitude (Richter)",
            min_value=0.0,
            max_value=7.5,
            value=default_quake,
            step=0.2,
            help="Values >4.5 Richter activate on-screen jitter and shelter allocations."
        )

        st.sidebar.markdown("<p style='font-size:13px; font-weight:800; color:#F43F5E; margin-top:10px;'>🚗 4. Vehicle Speed Drop Anomaly</p>", unsafe_allow_html=True)
        anomaly_active_default = preset_jam
        speed_anomaly = st.sidebar.toggle("Inject 40km/h ➔ 0km/h Gridlock Drop", value=anomaly_active_default, key="toggle_speed_drop")

        custom_speed = 0.0
        if speed_anomaly:
            custom_speed = st.sidebar.slider("Simulated Edge Speed (km/h)", min_value=0.0, max_value=40.0, value=0.0, step=5.0)

        st.sidebar.markdown("<hr style='border:none; border-top:1px solid #334155; margin:14px 0;'/>", unsafe_allow_html=True)

        # Emergency Corridors
        ems_green_wave = st.sidebar.toggle("🚑 Force EMS Green Wave Preemption", value=(rainfall_mm >= 45.0 or fire_active or speed_anomaly))

        return {
            "rainfall_mm": rainfall_mm,
            "fire_active": fire_active,
            "wind_speed_kmh": wind_speed_kmh,
            "wind_direction_deg": wind_direction_deg,
            "seismic_magnitude": seismic_magnitude,
            "speed_anomaly": speed_anomaly,
            "custom_speed": custom_speed,
            "ems_green_wave": ems_green_wave
        }
