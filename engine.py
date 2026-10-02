import json, os, re, sqlite3
import time
import urllib.error
import urllib.request
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data.db")
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
MAX_ROWS = 500
BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|replace|vacuum)\b", re.I
)


def connect_ro():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def is_safe(sql: str) -> bool:
    s = sql.strip().rstrip(";").strip()
    if not s.lower().startswith(("select", "with")):
        return False
    return ";" not in s and not BLOCKED.search(s)


def get_schema(sample_rows: int = 2) -> str:
    conn = connect_ro()
    out = []
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info('{t}')").fetchall()
        col_txt = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        sample = pd.read_sql_query(f"SELECT * FROM '{t}' LIMIT {sample_rows}", conn)
        out.append(f"TABLE {t} ({col_txt})\nSAMPLE:\n{sample.to_csv(index=False)}")
    conn.close()
    return "\n".join(out)


def _chat_json(system: str, user: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY in your .env file.")

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
    request_data = json.dumps(payload).encode("utf-8")
    for attempt in range(3):
        request = urllib.request.Request(
            url,
            data=request_data,
            headers={"Content-Type": "application/json", "X-Goog-Api-Key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                result = json.load(response)
            break
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"Gemini API request failed ({error.code}): {detail}") from error

            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                delay = min(max(float(retry_after), 0), 10) if retry_after else 2 ** attempt
            except ValueError:
                delay = 2 ** attempt
            time.sleep(delay)

    candidates = result.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {result}")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts)
    if not text:
        raise RuntimeError(f"Gemini returned no text: {result}")
    return json.loads(text)


def generate_sql(question: str, schema: str, error: str | None = None) -> dict:
    system = (
        "You convert business questions into ONE read-only SQLite SELECT query. "
        "Use only the tables and columns in the schema. "
        'Return JSON: {"answerable": bool, "sql": str, "explanation": str}. '
        "If the data cannot answer the question, set answerable=false and sql=\"\"."
    )
    user = f"SCHEMA:\n{schema}\n\nQUESTION: {question}"
    if error:
        user += f"\n\nYour previous SQL failed with: {error}\nFix it."
    return _chat_json(system, user)


def run_query(sql: str) -> pd.DataFrame:
    if not is_safe(sql):
        raise ValueError("Blocked: only a single read-only SELECT is allowed.")
    conn = connect_ro()
    try:
        return pd.read_sql_query(sql, conn).head(MAX_ROWS)
    finally:
        conn.close()


def ask(question: str) -> dict:
    """Returns {answerable, sql, explanation, df, error}."""
    schema = get_schema()
    gen = generate_sql(question, schema)
    if not gen.get("answerable") or not gen.get("sql"):
        return {"answerable": False, "explanation": gen.get("explanation", ""), "sql": "", "df": None}
    for attempt in range(2):  # one retry with the error fed back
        try:
            df = run_query(gen["sql"])
            return {"answerable": True, "sql": gen["sql"], "explanation": gen.get("explanation", ""), "df": df}
        except Exception as e:
            if attempt == 1:
                return {"answerable": True, "sql": gen["sql"], "explanation": "", "df": None, "error": str(e)}
            gen = generate_sql(question, schema, error=str(e))


def ungrounded_numbers(text: str, df: pd.DataFrame) -> list[str]:
    """Numbers quoted in an insight that don't appear in the result rows."""
    haystack = df.to_csv(index=False).replace(",", "")
    nums = re.findall(r"\d[\d,]*\.?\d*", text)
    return [n for n in nums if n.replace(",", "").rstrip(".") not in haystack]


def recommend(question: str, sql: str, df: pd.DataFrame) -> list[dict]:
    system = (
        "You are a business analyst. Use ONLY values present in the result rows. "
        'Return JSON: {"insights":[{"insight": str, "action": str, "evidence": str}]} '
        "with 2-3 items. 'evidence' must cite the specific rows/values you relied on."
    )
    user = f"QUESTION: {question}\nSQL: {sql}\nRESULT (CSV):\n{df.head(50).to_csv(index=False)}"
    response = _chat_json(system, user)
    items = response if isinstance(response, list) else response.get("insights", []) if isinstance(response, dict) else []
    recommendations = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        insight = str(item.get("insight", ""))
        action = str(item.get("action", ""))
        evidence = str(item.get("evidence", ""))
        recommendations.append({
            "insight": insight,
            "action": action,
            "evidence": evidence,
            "ungrounded": ungrounded_numbers(insight + " " + evidence, df),
        })
    return recommendations
