import streamlit as st
import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv

# -----------------------------
# Configure Page
# -----------------------------

st.set_page_config(
    page_title="AI Secure Code Reviewer",
    page_icon="🛡️",
    layout="wide"
)

# -----------------------------
# Load Gemini API
# -----------------------------

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error(
        "⚠️ GEMINI_API_KEY not found. Add it to a .env file "
        "(GEMINI_API_KEY=your_key_here) before running this app."
    )
    st.stop()

genai.configure(api_key=api_key)

model = genai.GenerativeModel("models/gemini-3.5-flash-lite")

MAX_CODE_CHARS = 20000  # rough guardrail against huge files blowing the context/cost

# Forcing JSON mode (rather than just asking nicely in the prompt) stops Gemini
# from wrapping the response in markdown fences or adding stray commentary.
# max_output_tokens is raised well above the default cap — the previous default
# was truncating longer responses mid-string (usually inside "improved_code"),
# which produced invalid/unparseable JSON.
ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "critical": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
        "high": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
        "medium": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
        "low": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "required": ["title", "detail"],
            },
        },
        "explanation": {"type": "string"},
        "recommendations": {"type": "string"},
        "improved_code": {"type": "string"},
    },
    "required": [
        "critical", "high", "medium", "low",
        "explanation", "recommendations", "improved_code",
    ],
}

ANALYSIS_GENERATION_CONFIG = genai.GenerationConfig(
    response_mime_type="application/json",
    response_schema=ANALYSIS_RESPONSE_SCHEMA,
    max_output_tokens=8192,
)

# -----------------------------
# Session State Setup
# -----------------------------
# Streamlit reruns the whole script on every widget interaction (like clicking
# "Ask AI"). Without session_state, `analyze` and the report would reset to
# their defaults on that rerun and the whole dashboard would disappear.

if "report_data" not in st.session_state:
    st.session_state.report_data = None

if "raw_code_analyzed" not in st.session_state:
    st.session_state.raw_code_analyzed = None

if "qa_history" not in st.session_state:
    st.session_state.qa_history = []

# -----------------------------
# Sidebar
# -----------------------------

st.sidebar.title("🛡️ AI Code Reviewer")

st.sidebar.markdown("""
### Features

✅ AI Powered

✅ Multi-language Support

✅ File Upload

✅ Security Dashboard

✅ Download Report

---

### Built With

- Python
- Streamlit
- Google Gemini
""")

st.sidebar.warning(
    "⚠️ Code you paste or upload is sent to Google's Gemini API for analysis. "
    "Do not submit code you aren't allowed to share externally."
)

# -----------------------------
# Header
# -----------------------------

st.title("🛡️ AI Secure Code Reviewer")

st.caption(
    "Analyze source code using AI to detect vulnerabilities and recommend secure fixes."
)

# -----------------------------
# Upload File
# -----------------------------

uploaded_file = st.file_uploader(
    "📂 Upload Source Code",
    type=["py", "c", "cpp", "java", "js"]
)

left, right = st.columns([3, 1])

with right:

    language = st.selectbox(
        "Language",
        [
            "Python",
            "C",
            "C++",
            "Java",
            "JavaScript"
        ]
    )

with left:

    if uploaded_file:

        try:
            code = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            st.warning(
                "⚠️ File isn't valid UTF-8 — decoding with replacement "
                "characters for anything that doesn't map cleanly."
            )
            uploaded_file.seek(0)
            code = uploaded_file.read().decode("utf-8", errors="replace")

        code = st.text_area(
            "Source Code",
            value=code,
            height=350
        )

    else:

        code = st.text_area(
            "Paste Your Code",
            height=350,
            placeholder="Paste your source code here..."
        )

if code and len(code) > MAX_CODE_CHARS:
    st.warning(
        f"⚠️ Code is {len(code):,} characters, over the {MAX_CODE_CHARS:,} "
        "character guardrail. Only the first "
        f"{MAX_CODE_CHARS:,} characters will be analyzed."
    )

analyze = st.button(
    "🔍 Analyze Code",
    use_container_width=True
)

# -----------------------------
# Prompt / Parsing Helpers
# -----------------------------

REPORT_SCHEMA_HINT = """
Respond with ONLY a single valid JSON object, no markdown fences, no commentary
before or after it. Use exactly this schema:

{
  "critical": [{"title": "...", "detail": "..."}],
  "high": [{"title": "...", "detail": "..."}],
  "medium": [{"title": "...", "detail": "..."}],
  "low": [{"title": "...", "detail": "..."}],
  "explanation": "plain-language explanation of every issue",
  "recommendations": "how to fix every issue",
  "improved_code": "the complete corrected code as a single string"
}

If there are no issues in a severity level, use an empty list for it.
"""


def build_analysis_prompt(language: str, code: str) -> str:
    return f"""
You are a Senior Application Security Engineer.

Analyze the following {language} code for security vulnerabilities.

{REPORT_SCHEMA_HINT}

Code:

{code}
"""


def parse_report_json(raw_text: str) -> dict:
    """Extract a JSON object from the model's response, tolerating stray
    markdown fences or leading/trailing text some models add anyway."""
    text = raw_text.strip()
    text = re.sub(r"^```(json)?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    text = text.strip()

    # Fallback: grab the first {...} block if there's still extra text around it
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

    data = json.loads(text)

    for key in ("critical", "high", "medium", "low"):
        data.setdefault(key, [])
    data.setdefault("explanation", "")
    data.setdefault("recommendations", "")
    data.setdefault("improved_code", "")

    return data


def compute_score(data: dict) -> int:
    score = 100 - (
        len(data["critical"]) * 25
        + len(data["high"]) * 15
        + len(data["medium"]) * 8
        + len(data["low"]) * 3
    )
    return max(0, min(score, 100))


def render_issue_list(items: list) -> str:
    if not items:
        return "_None found._"
    lines = []
    for item in items:
        title = item.get("title", "Untitled issue")
        detail = item.get("detail", "")
        lines.append(f"- **{title}**: {detail}" if detail else f"- **{title}**")
    return "\n".join(lines)


def report_as_text(data: dict, score: int) -> str:
    """Flat text version for the download button."""
    parts = [
        f"Security Score: {score}/100",
        "",
        "Critical Vulnerabilities",
        render_issue_list(data["critical"]),
        "",
        "High Vulnerabilities",
        render_issue_list(data["high"]),
        "",
        "Medium Vulnerabilities",
        render_issue_list(data["medium"]),
        "",
        "Low Vulnerabilities",
        render_issue_list(data["low"]),
        "",
        "Detailed Explanation",
        data["explanation"],
        "",
        "Secure Recommendations",
        data["recommendations"],
        "",
        "Improved Secure Code",
        data["improved_code"],
    ]
    return "\n".join(parts)


# -----------------------------
# AI Analysis
# -----------------------------

if analyze:

    if code.strip() == "":
        st.warning("⚠️ Please paste or upload some code first.")

    else:

        code_to_send = code[:MAX_CODE_CHARS]
        prompt = build_analysis_prompt(language, code_to_send)

        try:

            with st.spinner("🔍 AI is reviewing your code..."):
                response = model.generate_content(
                    prompt,
                    generation_config=ANALYSIS_GENERATION_CONFIG,
                )

            data = parse_report_json(response.text)

            st.session_state.report_data = data
            st.session_state.raw_code_analyzed = code_to_send
            st.session_state.qa_history = []  # reset follow-up thread for new report

        except json.JSONDecodeError:
            st.error(
                "The AI's response wasn't valid JSON, so it couldn't be scored. "
                "Here's the raw response instead:"
            )
            st.code(response.text)
            st.session_state.report_data = None

        except Exception as e:
            st.error("Something went wrong while contacting Gemini.")
            st.exception(e)
            st.session_state.report_data = None

# -----------------------------
# Dashboard (persists across reruns via session_state)
# -----------------------------

if st.session_state.report_data:

    data = st.session_state.report_data
    score = compute_score(data)

    st.success("✅ Analysis Complete!")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("🛡️ Score", f"{score}/100")
    c2.metric("🔴 Critical", len(data["critical"]))
    c3.metric("🟠 High", len(data["high"]))
    c4.metric("🟡 Medium", len(data["medium"]))
    c5.metric("🟢 Low", len(data["low"]))

    st.markdown("---")

    st.subheader("📄 AI Security Report")

    st.markdown("**Critical Vulnerabilities**")
    st.markdown(render_issue_list(data["critical"]))

    st.markdown("**High Vulnerabilities**")
    st.markdown(render_issue_list(data["high"]))

    st.markdown("**Medium Vulnerabilities**")
    st.markdown(render_issue_list(data["medium"]))

    st.markdown("**Low Vulnerabilities**")
    st.markdown(render_issue_list(data["low"]))

    st.markdown("**Detailed Explanation**")
    st.markdown(data["explanation"])

    st.markdown("**Secure Recommendations**")
    st.markdown(data["recommendations"])

    st.markdown("**Improved Secure Code**")
    st.code(data["improved_code"], language=language.lower())

    st.download_button(
        "📥 Download Security Report",
        report_as_text(data, score),
        file_name="security_report.txt",
        mime="text/plain"
    )

    st.markdown("---")

    st.subheader("💬 Ask AI About This Report")

    follow_up = st.text_input(
        "Example: Why is SQL Injection dangerous?",
        key="follow_up_input"
    )

    if st.button("Ask AI", key="ask_ai_button"):

        if follow_up.strip() == "":
            st.warning("⚠️ Type a question first.")
        else:
            with st.spinner("Thinking..."):
                try:
                    answer = model.generate_content(
                        f"""
The following is a security report (JSON):

{json.dumps(data)}

User Question:

{follow_up}

Answer clearly and briefly.
"""
                    )
                    st.session_state.qa_history.append(
                        {"question": follow_up, "answer": answer.text}
                    )
                except Exception as e:
                    st.error("Something went wrong while contacting Gemini.")
                    st.exception(e)

    for qa in reversed(st.session_state.qa_history):
        st.markdown(f"**Q: {qa['question']}**")
        st.info(qa["answer"])

# -----------------------------
# Footer
# -----------------------------

st.markdown("---")

st.caption(
    "🛡️ AI Secure Code Reviewer | Built with Python, Streamlit & Google Gemini"
)
