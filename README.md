# 🛡️ AI Secure Code Reviewer

A Streamlit app that uses Google's Gemini API to scan source code for security
vulnerabilities, score it, and suggest a corrected version — with a follow-up
Q&A panel to ask about specific findings.

## Features

- 🤖 AI-powered vulnerability analysis (SQL injection, command injection,
  hardcoded secrets, unsafe `eval`, etc.)
- 🌐 Multi-language support: Python, C, C++, Java, JavaScript
- 📂 Paste code directly or upload a file
- 📊 Severity dashboard (Critical / High / Medium / Low) with a computed
  security score out of 100
- 📥 Downloadable text report
- 💬 Follow-up chat to ask questions about the report
- 🔒 Structured JSON output from Gemini (not scraped from prose), so the score
  reflects actual findings rather than keyword counts

## Requirements

- Python 3.9+
- A Gemini API key — get one free at https://aistudio.google.com/apikey

## Setup

1. Clone or copy this project, then install dependencies:

   ```bash
   pip install streamlit google-generativeai python-dotenv
   ```

2. Create a `.env` file in the project root:

   ```
   GEMINI_API_KEY=your_key_here
   ```

3. Run the app:

   ```bash
   streamlit run app.py
   ```

4. Open the local URL Streamlit prints (usually `http://localhost:8501`).

## Usage

1. Paste code into the text area, or upload a `.py`, `.c`, `.cpp`, `.java`, or
   `.js` file.
2. Select the language from the dropdown.
3. Click **🔍 Analyze Code**.
4. Review the dashboard, read the full report, and download it if needed.
5. Use the **Ask AI About This Report** box to ask follow-up questions (e.g.
   "Why is SQL injection dangerous?").

## How scoring works

Gemini returns a structured JSON object listing issues by severity. The score
starts at 100 and subtracts per issue found:

| Severity | Points deducted (each) |
|----------|------------------------|
| Critical | 25 |
| High     | 15 |
| Medium   | 8  |
| Low      | 3  |

Score is floored at 0. This is a simple heuristic, not a certified security
metric — treat it as a rough signal, not a compliance score.

## ⚠️ Data privacy

Any code pasted or uploaded is sent to Google's Gemini API for analysis. Do
not submit proprietary or sensitive code you aren't authorized to share
externally.

## Known limitations

- Only as accurate as the underlying Gemini model — always have a human
  review flagged issues before acting on them, especially the suggested
  "improved" code.
- Files larger than ~20,000 characters are truncated before analysis.
- No authentication, rate limiting, or usage caps — if you deploy this
  publicly, add your own throttling in front of the Gemini calls.
- Non-UTF-8 file uploads are decoded with `errors="replace"`, which can
  mangle a small number of characters in rare encodings.

## Tech stack

- [Streamlit](https://streamlit.io/) — UI
- [Google Gemini API](https://ai.google.dev/) — analysis (`gemini-3.5-flash-lite`)
- [python-dotenv](https://pypi.org/project/python-dotenv/) — env var loading


