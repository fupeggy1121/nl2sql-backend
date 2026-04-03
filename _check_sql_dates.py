"""Quick probe: what does the backend return for time-variant yield queries?"""
import httpx, json, os, re, sys
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

queries = [
    ("1wk",  "\u6700\u8fd11\u4e2a\u661f\u671f\u7684\u4e00\u6b21\u826f\u7387"),   # 最近1个星期的一次良率
    ("2wk",  "\u6700\u8fd1\u4e24\u4e2a\u661f\u671f\u7684\u4e00\u6b21\u826f\u7387"),  # 最近两个星期的一次良率
    ("1mo",  "\u4e0a\u4e2a\u6708\u5404\u5de5\u7ad9\u7684\u4e00\u6b21\u826f\u7387"),  # 上个月各工站的一次良率
    ("3d",   "\u6700\u8fd1\u4e09\u5929\u7684\u4e00\u6b21\u826f\u7387"),              # 最近三天的一次良率
    ("qtr",  "\u672c\u5b63\u5ea6\u5404\u5de5\u7ad9\u7684\u8fd4\u5de5\u7387"),        # 本季度各工站的返工率
]

DATE_PAT = re.compile(
    r"gmt_create\s*(?:>=|<=|BETWEEN)\s*['\"]?(\d{4}-\d{2}-\d{2})|"
    r"INTERVAL\s+(\d+)\s+(DAY|WEEK|MONTH)|"
    r"DATE_SUB\s*\(|CURDATE\s*\(",
    re.IGNORECASE,
)


def find_sql_in_body(body: dict) -> str:
    inner = body.get("data") or {}
    # direct fields
    for fld in ("sql", "generated_sql", "query", "data_source_sql"):
        v = inner.get(fld) or ""
        if v:
            return v
    # pipeline_trace
    for step in (inner.get("pipeline_trace") or body.get("pipeline_trace") or []):
        s = (step.get("data_source_config") or {}).get("sql") or ""
        if s:
            return s
    # analysis.metadata.data_source_sql
    analysis = inner.get("analysis") or {}
    return (analysis.get("metadata") or {}).get("data_source_sql") or ""


SEP = "=" * 60

for label, q in queries:
    print(f"\n{SEP}")
    print(f"[{label}]  {q}")
    try:
        r = httpx.post("http://localhost:8000/api/v1/chat",
                       json={"message": q}, timeout=120)
        body = r.json()
        sql = find_sql_in_body(body)

        if sql:
            # show lines with date-relevant content
            date_lines = [ln.strip() for ln in sql.splitlines()
                          if DATE_PAT.search(ln)]
            if date_lines:
                print("  Date-relevant SQL lines:")
                for ln in date_lines:
                    print(f"    {ln[:120]}")
            else:
                print("  SQL found but NO date line detected:")
                for ln in sql.splitlines()[:10]:
                    print(f"    {ln[:120]}")
        else:
            # dump the inner keys to help locate where SQL lives
            inner = body.get("data") or {}
            analysis = inner.get("analysis") or {}
            meta = analysis.get("metadata") or {}
            print(f"  No SQL field found.")
            print(f"  inner keys  : {list(inner.keys())}")
            print(f"  analysis keys: {list(analysis.keys())}")
            print(f"  meta keys   : {list(meta.keys())}")
            # print metadata fully
            if meta:
                print(f"  metadata    : {json.dumps(meta, ensure_ascii=False)[:400]}")

    except Exception as e:
        print(f"  ERROR: {e}")
