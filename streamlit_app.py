import os
import streamlit as st
import requests

st.set_page_config(
    page_title="Spotify AI Review Discovery Engine",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

BACKEND_BASE_URL = st.secrets.get("BACKEND_BASE_URL", os.getenv("BACKEND_BASE_URL", "")).rstrip("/")

def api_get(path: str, timeout: int = 30):
    if not BACKEND_BASE_URL:
        raise ValueError("BACKEND_BASE_URL is not configured.")
    return requests.get(f"{BACKEND_BASE_URL}{path}", timeout=timeout)

def api_post(path: str, timeout: int = 60):
    if not BACKEND_BASE_URL:
        raise ValueError("BACKEND_BASE_URL is not configured.")
    return requests.post(f"{BACKEND_BASE_URL}{path}", timeout=timeout)

st.title("🎵 Spotify AI Review Discovery Engine")
st.markdown("---")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("System Status")

    if not BACKEND_BASE_URL:
        st.error("Backend URL is not configured.")
        st.code('BACKEND_BASE_URL = "https://your-backend-url"')
    else:
        try:
            health_res = api_get("/health")
            if health_res.status_code == 200:
                st.success(f"Backend connected: {BACKEND_BASE_URL}")
            else:
                st.warning(f"Backend responded with status {health_res.status_code}")
        except Exception as e:
            st.error(f"Could not connect to backend: {str(e)}")

    st.markdown(
        """
        This Streamlit app is the frontend dashboard.
        The FastAPI backend should be deployed separately and connected through `BACKEND_BASE_URL`.

        Example endpoints:
        - `/health`
        - `/docs`
        - `/openapi.json`
        - `/analysis/run?limit=20`
        """
    )

    st.subheader("Database Metrics")
    if BACKEND_BASE_URL:
        try:
            metrics_res = api_get("/health")
            if metrics_res.status_code == 200:
                st.info("Backend is reachable. Add a dedicated metrics endpoint if you want live DB metrics here.")
            else:
                st.warning("Metrics are unavailable right now.")
        except Exception as e:
            st.error(f"Could not load metrics: {str(e)}")

with col2:
    st.subheader("Pipeline Actions")

    if st.button("🤖 Run AI Analysis Pipeline"):
        if not BACKEND_BASE_URL:
            st.error("Set BACKEND_BASE_URL first.")
        else:
            with st.spinner("Scheduling batch analysis..."):
                try:
                    res = api_post("/analysis/run?limit=20")
                    if res.status_code == 200:
                        try:
                            st.success(f"AI Run Scheduled Successfully: {res.json()}")
                        except Exception:
                            st.success("AI Run Scheduled Successfully.")
                    else:
                        st.error(f"AI Run failed: Status {res.status_code} - {res.text}")
                except Exception as e:
                    st.error(f"Could not connect to backend: {str(e)}")
