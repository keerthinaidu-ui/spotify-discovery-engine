import sys
import os
import gc
import time
import subprocess
import threading
import streamlit as st

# Configure page settings
st.set_page_config(
    page_title="Spotify AI Review Discovery Backend",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add backend directory to sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, "backend")
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Initialize FastAPI backend in background thread
@st.cache_resource
def start_backend():
    import uvicorn
    from app.main import app

    def run_server():
        # Run on local port 8000
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

    # Start FastAPI
    t = threading.Thread(target=run_server, name="UvicornServer", daemon=True)
    t.start()
    
    # Give uvicorn a moment to start
    time.sleep(2)

    # Inject proxy into Tornado
    from tornado.web import Application, RequestHandler
    from tornado.httpclient import AsyncHTTPClient
    from tornado.routing import Rule, PathMatches

    class FastAPIProxyHandler(RequestHandler):
        async def prepare(self):
            # Allow CORS for Vercel integration
            self.set_header("Access-Control-Allow-Origin", "*")
            self.set_header("Access-Control-Allow-Headers", "*")
            self.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE, PATCH")
            if self.request.method == "OPTIONS":
                self.set_status(204)
                self.finish()

        async def get(self, path):
            await self.proxy(path)

        async def post(self, path):
            await self.proxy(path)

        async def put(self, path):
            await self.proxy(path)

        async def delete(self, path):
            await self.proxy(path)

        async def patch(self, path):
            await self.proxy(path)

        async def options(self, path):
            pass

        async def proxy(self, path):
            client = AsyncHTTPClient()
            query = self.request.query
            url = f"http://127.0.0.1:8000/{path}"
            if query:
                url += f"?{query}"
            
            headers = dict(self.request.headers)
            headers.pop("Host", None)
            
            body = self.request.body if self.request.method in ["POST", "PUT", "PATCH"] else None
            
            try:
                response = await client.fetch(
                    url,
                    method=self.request.method,
                    headers=headers,
                    body=body,
                    raise_error=False,
                    request_timeout=120.0
                )
                self.set_status(response.code)
                for header, value in response.headers.get_all():
                    if header.lower() not in ["content-length", "transfer-encoding", "content-encoding", "connection"]:
                        self.set_header(header, value)
                self.write(response.body)
            except Exception as e:
                self.set_status(502)
                self.write({"detail": f"Proxy error: {str(e)}"})
            self.finish()

    try:
        # Find active Tornado Application
        tornado_app = None
        for obj in gc.get_objects():
            if isinstance(obj, Application):
                tornado_app = obj
                break
        
        if tornado_app:
            # Check if proxy is already registered
            already_registered = False
            for rule in tornado_app.wildcard_router.rules:
                if isinstance(rule.matcher, PathMatches) and rule.matcher.regex.pattern.startswith("/api/"):
                    already_registered = True
                    break
            
            if not already_registered:
                tornado_app.wildcard_router.rules.insert(
                    0,
                    Rule(PathMatches(r"/api/(.*)"), FastAPIProxyHandler)
                )
            return "FastAPI running on port 8000. Reverse proxy registered on `/api/*`."
        else:
            return "FastAPI running on port 8000. (Could not find Tornado app to inject proxy handler)"
    except Exception as e:
        return f"FastAPI running on port 8000. (Proxy injection failed: {str(e)})"

# Trigger start
proxy_status = start_backend()

# Streamlit UI Rendering
st.title("🎵 Spotify AI Review Discovery Engine - Backend Gateway")
st.markdown("---")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("System Status")
    st.success(proxy_status)
    
    st.markdown("""
    This Streamlit container serves as the hosting gateway for the FastAPI backend engine. 
    The Next.js frontend deployed on Vercel communicates with this backend via the proxied `/api` path.
    
    * **FastAPI Docs (Swagger)**: `/api/docs`
    * **OpenAPI Schema**: `/api/openapi.json`
    * **Health Endpoint**: `/api/health`
    """)

    st.subheader("Database Metrics")
    try:
        from app.database import SessionLocal
        from app.models.feedback_item import FeedbackItem
        from sqlalchemy import func

        db = SessionLocal()
        try:
            total_items = db.query(func.count(FeedbackItem.id)).scalar()
            analyzed_items = db.query(func.count(FeedbackItem.id)).filter(FeedbackItem.analyzed_at.is_not(None)).scalar()
            pending_items = total_items - analyzed_items
        finally:
            db.close()
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Total Feedback Items", f"{total_items:,}")
        m_col2.metric("Analyzed Items", f"{analyzed_items:,}", delta=f"{analyzed_items / max(1, total_items) * 100:.1f}% Complete")
        m_col3.metric("Pending AI Analysis", f"{pending_items:,}", delta_color="inverse")
    except Exception as e:
        st.error(f"Could not load database metrics: {str(e)}")

with col2:
    st.subheader("Pipeline Actions")
    
    # helper function to run scripts as subprocesses and stream console outputs
    def run_script(script_name, relative_path):
        output_placeholder = st.empty()
        output_placeholder.info(f"Starting {script_name}...")
        
        script_abs_path = os.path.join(root_dir, relative_path)
        env = os.environ.copy()
        env["PYTHONPATH"] = backend_dir
        
        process = subprocess.Popen(
            [sys.executable, "-u", script_abs_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=root_dir,
            env=env
        )
        
        logs = []
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                logs.append(line.strip())
                output_placeholder.code("\n".join(logs[-20:])) # display last 20 lines of log
        
        rc = process.poll()
        if rc == 0:
            st.success(f"{script_name} completed successfully!")
        else:
            st.error(f"{script_name} failed with exit code {rc}")

    # Ingestion Buttons
    if st.button("🚀 Trigger CSV App Reviews Ingestion"):
        run_script("CSV Ingestion", "backend/scripts/ingest_reviews.py")
        st.rerun()

    if st.button("🔍 Trigger External Ingestion (YouTube / Product Hunt)"):
        run_script("External API Ingestions", "backend/scripts/ingest_external_sources.py")
        st.rerun()

    if st.button("🧹 Run Preprocessing & Normalization"):
        run_script("Normalization Service", "backend/scripts/normalize_feedback.py")
        st.rerun()

    if st.button("🤖 Run AI Analysis Pipeline (Gemini/Groq)"):
        with st.spinner("Scheduling batch analysis..."):
            try:
                import requests
                # Trigger via FastAPI endpoint
                res = requests.post("http://127.0.0.1:8000/analysis/run?limit=20")
                if res.status_code == 200:
                    st.success(f"AI Run Scheduled Successfully! Response: {res.json()}")
                else:
                    st.error(f"AI Run failed: Status {res.status_code} - {res.text}")
            except Exception as e:
                st.error(f"Could not connect to FastAPI server: {str(e)}")
