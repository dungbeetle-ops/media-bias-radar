
import streamlit as st
import requests
import sqlite3
import json
import os
import pandas as pd
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
# --- REPLACED CONFLICTING GOOGLE GENAI CLIENT IMPORT ---
import google.generativeai as genai

# =====================================================================
# 1. PAGE LAYOUT & SETUP
# =====================================================================
st.set_page_config(page_title="AI Bias Radar Station", layout="wide")
st.title("📡 AI Live Media Radar & Automated Data Station")
st.caption("Routing real-time headlines through an AI reasoning engine to log and expose structural media manipulation.")

DB_FILE = "media_radar.db"

# --- Email Configuration ---
SMTP_SERVER = "://gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"
SENDER_PASSWORD = "YOUR_APP_PASSWORD"  # 16-character Google App Password
RECEIVER_EMAIL = "destination_email@gmail.com"

# =====================================================================
# 2. DATABASE UTILITIES (SQLite)
# =====================================================================
def init_database():
    """Builds the local relational SQL schema if it does not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bias_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            headline TEXT,
            source_name TEXT,
            severity TEXT,
            reason TEXT,
            matched_keyword TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_alert_to_db(headline, source, severity, reason, keyword):
    """Inserts a flagged media entry securely into the local database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO bias_alerts (timestamp, headline, source_name, severity, reason, matched_keyword)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (timestamp, headline, source, severity, reason, keyword))
    conn.commit()
    conn.close()

def get_db_stats():
    """Queries the database to calculate real-time analytics."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM bias_alerts")
    total = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT source_name, COUNT(*) as count 
        FROM bias_alerts 
        GROUP BY source_name 
        ORDER BY count DESC 
        LIMIT 5
    """)
    top_offenders = cursor.fetchall()
    conn.close()
    return total, top_offenders

# Initialize database right away
init_database()

# =====================================================================
# 3. SIDEBAR CONTROLS & EXPORTER
# =====================================================================
st.sidebar.header("🎯 Custom Alert Rules")
watch_keywords_input = st.sidebar.text_input(
    "Track Specific Subjects:", 
    placeholder="e.g., Election, Tech, Climate, Economy"
)
WATCH_KEYWORDS = [w.strip().lower() for w in watch_keywords_input.split(",") if w.strip()]

alert_severity = st.sidebar.selectbox(
    "Alert Trigger Severity:",
    ["Flag Any Bias (Sensitive)", "Flag Extreme Manipulation Only"]
)

# --- Automated Email Export Function ---
def export_db_and_send_email():
    try:
        conn = sqlite3.connect(DB_FILE)
        df = pd.read_sql_query("SELECT * FROM bias_alerts", conn)
        conn.close()
        
        if df.empty:
            st.sidebar.warning("Database is empty. Nothing to export yet!")
            return
            
        csv_filename = "media_bias_audit_export.csv"
        df.to_csv(csv_filename, index=False)
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"📊 Media Bias Audit Export - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = "Attached is your automated SQLite database export mapping out recent media bias tracking records."
        msg.attach(MIMEText(body, 'plain'))
        
        with open(csv_filename, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {csv_filename}")
            msg.attach(part)
            
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        st.sidebar.success(f"📬 Spreadsheet emailed to {RECEIVER_EMAIL}!")
    except Exception as e:
        st.sidebar.error(f"Failed to generate email export: {e}")

st.sidebar.divider()
st.sidebar.header("📤 Data Export Hub")
if st.sidebar.button("📦 Email Me Database Log (CSV)"):
    with st.spinner("Compiling tables and transmitting stream..."):
        export_db_and_send_email()
# =====================================================================
# 4. EXTERNAL DATA PIPELINES (News & AI APIs)
# =====================================================================
# Safe Lookups: Variable assignment MUST happen first
GNEWS_API_KEY = st.secrets.get("GNEWS_API_KEY") if "GNEWS_API_KEY" in st.secrets else "YOUR_GNEWS_API_KEY"
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") if "GEMINI_API_KEY" in st.secrets else "YOUR_GEMINI_API_KEY"

if not GNEWS_API_KEY or GNEWS_API_KEY == "YOUR_GNEWS_API_KEY":
    st.sidebar.error("🔑 Missing GNews API Key. Add it to your Streamlit Cloud Secrets.")

if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    st.sidebar.error("🔑 Missing Gemini API Key. Add it to your Streamlit Cloud Secrets.")

def get_ai_client(api_key):
    """Bypasses namespace constructors to configure universal model auth state."""
    if api_key and api_key != "YOUR_GEMINI_API_KEY":
        genai.configure(api_key=api_key)
        return True
    return False

def fetch_live_headlines(api_key):
    # Ensure api_key is treated purely as a text string with no extra spacing
    clean_key = str(api_key).strip() if api_key else ""
    
    if clean_key == "YOUR_GNEWS_API_KEY" or not clean_key:
        st.warning("⚠️ Please insert your valid GNews API Key into your Streamlit Secrets.")
        return []
        
    # Hardcoded base web URL with a strict cutoff to prevent domain bleeding
    url = "https://gnews.io/api/v4/top-headlines"
    
    # Official GNews query parameters mapped out in a separate structure
    query_parameters = {
        "category": "general",
        "lang": "en",
        "apikey": clean_key  # Using the mandatory 'apikey' query parameter
    }
    
    try:
        # Pass parameters cleanly through the network engine
        response = requests.get(url, params=query_parameters, timeout=10)
        
        if response.status_code != 200:
            st.error(f"🚫 GNews Server Connection Blocked (Status Code {response.status_code}). Raw message: {response.text}")
            return []
            
        try:
            data = response.json()
            return data.get("articles", [])
        except Exception:
            st.error(f"🚫 Data Parsing Error: GNews returned text content that wasn't clean JSON.")
            return []
            
    except Exception as e:
        st.error(f"Failed to connect to media stream network layer: {e}")
        return []

def analyze_headline_with_ai(headline_text):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        return '{"bias_found": false, "severity": "Low", "technique_detected": "None", "manipulated_term": "None", "forensic_breakdown": "Gemini Key Missing."}'
        
    prompt = f"""
    You are an expert system specialized in forensic linguistics, media literacy, and propaganda analysis.
    Deconstruct the following news headline for narrative bias and psychological persuasion techniques:
    "{headline_text}"
    
    Examine the text explicitly for these advanced manipulation mechanics:
    1. Manufactured Urgency / Panic: Creating false anxiety or framing natural volatility as a catastrophic event.
    2. Character Assassination / Poisoning the Well: Inserting subjective adjectives (e.g., 'defiant', 'scrambling', 'desperate') to pre-condition the reader's view of an individual.
    3. Structural Omission / False Choice: Presenting a nuanced situation as a rigid, high-stakes binary conflict.
    4. Epistemic Bias: Presenting a contested claim or opinion as an established objective fact.
    
    You must format your response strictly as a valid JSON object with the following keys:
    {{
        "bias_found": true/false,
        "severity": "Low" or "Medium" or "High",
        "technique_detected": "Name of the propaganda or rhetorical technique found, or 'None'",
        "manipulated_term": "The exact word or phrase causing the spin, or 'None'",
        "forensic_breakdown": "A precise 1-sentence analytical explanation detailing how the text attempts to persuade the reader."
    }}
    Do not wrap the output in markdown code blocks like ```json. Output raw text only.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI error: {e}"

def parse_ai_response(ai_text):
    """Processes string responses securely into structured Python dictionary items."""
    fallback = {"bias": False, "severity": "Low", "technique": "None", "term": "None", "reason": "Failed to parse AI payload"}
    try:
        data = json.loads(ai_text.strip())
        return {
            "bias": data.get("bias_found", False),
            "severity": data.get("severity", "Low"),
            "technique": data.get("technique_detected", "None"),
            "term": data.get("manipulated_term", "None"),
            "reason": data.get("forensic_breakdown", "")
        }
    except Exception:
        return fallback

# =====================================================================
# 5. CORE INTERFACE RUNNER
# =====================================================================
if st.button("🔄 Sync Live Feed & Audit Media"):
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        st.error("Please add your Gemini API Key before running.")
    else:
        with st.spinner("Streaming global data feeds and processing through AI..."):
            articles = fetch_live_headlines(GNEWS_API_KEY)
            
            if articles:
                for idx, article in enumerate(articles):
                    title = article.get("title", "")
                    source = article.get("source", {}).get("name", "Unknown Source")
                    link = article.get("url", "#")
                    
                    headline_lower = title.lower()
                    matched_kw = next((kw for kw in WATCH_KEYWORDS if kw in headline_lower), None)
                    keyword_matched = matched_kw is not None if WATCH_KEYWORDS else False
                    
                    ai_raw = analyze_headline_with_ai(title)
                    analysis = parse_ai_response(ai_raw)
                    
                    trigger_alert = False
                    if keyword_matched and analysis["bias"]:
                        if alert_severity == "Flag Any Bias (Sensitive)":
                            trigger_alert = True
                        elif alert_severity == "Flag Extreme Manipulation Only" and analysis["severity"] in ["Medium", "High"]:
                            trigger_alert = True
                    
                    # --- FORCED LOG TO DATABASE FOR TESTING ---
                    if True:
                        log_alert_to_db(title, source, analysis["severity"], analysis["reason"], matched_kw)
                    
                    with st.container():
                        if trigger_alert:
                            st.error("🚨 ALERT RECORDED: Logged into local database rules.")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"### {idx+1}. {title}")
                            st.caption(f"Source: **{source}** | [Link]({link})")
                            if keyword_matched:
                                st.markdown(f"🎯 *Matched keyword rule: `{matched_kw}`*")
                        with col2:
                            if analysis["bias"]:
                                st.warning(f"⚠️ **AI Audit ({analysis['severity']} Bias):**")
                                st.markdown(f"- **Tactic:** `{analysis['technique']}`")
                                st.markdown(f"- **Trigger:** :red-background[*{analysis['term']}*]")
                                st.markdown(f"- **Analysis:** *{analysis['reason']}*")
                            else:
                                st.success(f"✅ **AI Audit:** {analysis['reason']}")
                        st.divider()

# =====================================================================
# 6. FORCE LAYOUT METRICS DISPLAY PANEL
# =====================================================================
st.sidebar.divider()
st.sidebar.header("📊 Database Audit Metrics")

try:
    total_alerts, top_publishers = get_db_stats()
    
    # Extract row count safely from tuple structure
    total_count = total_alerts[0] if total_alerts and isinstance(total_alerts, tuple) else 0
    st.sidebar.metric(label="Total Logged Incidents", value=total_count)

    if top_publishers:
        st.sidebar.markdown("### Top Sources Flagged:")
        for pub, count in top_publishers:
            st.sidebar.write(f"- **{pub}**: {count} flags")
    else:
        st.sidebar.caption("No sources logged in database yet.")
except Exception as e:
    st.sidebar.error(f"Metrics panel failed to load: {e}")
