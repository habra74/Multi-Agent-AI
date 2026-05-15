#!/usr/bin/env python3
"""
scripts/scan_text_artifacts.py
-------------------------------
투자 분석 시스템 텍스트 오염 탐지 스크립트.

SQLite DB의 모든 텍스트 컬럼과 프로젝트 .py 파일을 대상으로
금지 표현(비공식·비전문 표현)의 존재 여부를 검사한 뒤 결과를 출력한다.

사용:
    python scripts/scan_text_artifacts.py
    python scripts/scan_text_artifacts.py --db path/to/custom.db
    python scripts/scan_text_artifacts.py --no-source  # DB만 검사

출력:
    - FOUND: 금지 표현이 발견된 위치(테이블/컬럼/row id, 파일/줄번호)
    - CLEAN: 금지 표현 없음
    - 종료 코드: 0=clean, 1=발견
"""

from __future__ import annotations

import argparse
import io
import os
import sqlite3
import sys
from pathlib import Path

# Windows 콘솔 UTF-8 출력 보장
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# 금지 표현 목록 (string 결합으로 literal 회피)
# ---------------------------------------------------------------------------
def _build_forbidden() -> list[str]:
    return [
        "오늘의 " + "토론",
        "오늘 " + "보도",
        "과거에 " + "대해",
        "풍부한 " + "관리",
        "아직은 " + "글쎄요",
        "최근 메일 " + "내용",
        "많은 " + "실패",
        "탄력적 " + "조건",
        "투자 " + "내용",
        "믿는" + "다",
        "의의" + "의",
        "뭐" + "야",
        "반대로 " + "분석",
        "전체 " + "보도",
        "활성" + "인자",
        "담당" + "자",
        "회원가입 " + "포인트",
        "투자하고 " + "있어요",
        "테스트해봤" + "습니다",
        "자동으로 " + "잘",
        "운" + "동",
    ]


FORBIDDEN: list[str] = _build_forbidden()


# ---------------------------------------------------------------------------
# DB 검사
# ---------------------------------------------------------------------------
def scan_db(db_path: str) -> list[dict]:
    """DB 내 모든 텍스트 컬럼을 검사해 발견 목록을 반환한다."""
    findings: list[dict] = []

    if not Path(db_path).exists():
        print(f"[WARN] DB 파일 없음: {db_path}")
        return findings

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 테이블 목록
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    for tbl in tables:
        cur.execute(f"PRAGMA table_info({tbl})")
        col_info = cur.fetchall()
        text_cols = [
            c["name"] for c in col_info
            if c["type"].upper() in ("TEXT", "")
            or "TEXT" in c["type"].upper()
        ]

        cur2 = conn.cursor()
        cur2.execute(f"SELECT * FROM {tbl}")
        rows = cur2.fetchall()

        for row in rows:
            row_id = row["id"] if "id" in row.keys() else "?"
            for col in text_cols:
                try:
                    val = row[col]
                    if not isinstance(val, str):
                        continue
                    for expr in FORBIDDEN:
                        if expr in val:
                            findings.append({
                                "source": "db",
                                "table": tbl,
                                "column": col,
                                "row_id": row_id,
                                "expr": expr,
                                "snippet": _snippet(val, expr),
                            })
                except Exception:
                    pass

    conn.close()
    return findings


def _snippet(text: str, expr: str, ctx: int = 40) -> str:
    """발견된 표현 주변 문맥(ctx 글자)을 반환한다."""
    idx = text.find(expr)
    if idx < 0:
        return ""
    start = max(0, idx - ctx)
    end = min(len(text), idx + len(expr) + ctx)
    snippet = text[start:end].replace("\n", " ")
    return f"...{snippet}..."


# ---------------------------------------------------------------------------
# Python 소스 검사
# ---------------------------------------------------------------------------
def scan_source(project_root: str) -> list[dict]:
    """프로젝트 .py 파일을 검사해 발견 목록을 반환한다.

    단, _make_substitution_map / _make_blocklist / _build_forbidden 내부는
    의도적으로 문자열을 결합하는 곳이므로 무시한다.
    """
    findings: list[dict] = []
    skip_funcs = {
        "_make_substitution_map", "_make_blocklist", "_build_forbidden",
        "FORBIDDEN_EXPRESSIONS",  # 테스트 파일의 금지 표현 목록 상수
    }

    root = Path(project_root)
    for py_file in sorted(root.rglob("*.py")):
        # __pycache__, .git 등 무시
        if any(part.startswith((".git", "__pycache__", ".pytest_cache"))
               for part in py_file.parts):
            continue

        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        in_skip_block = False
        for lineno, line in enumerate(lines, start=1):
            # skip block 진입/탈출 감지
            if any(fn in line for fn in skip_funcs):
                in_skip_block = True
            if in_skip_block:
                # 빈 줄 또는 def 로 시작하는 새 함수면 skip 종료
                stripped = line.strip()
                if stripped == "" or (stripped.startswith("def ") and lineno > 1):
                    pass  # block 계속
                # return 으로 끝나는 줄 이후 종료
                if stripped.startswith("return "):
                    in_skip_block = False
                continue

            for expr in FORBIDDEN:
                if expr in line:
                    findings.append({
                        "source": "py",
                        "file": str(py_file.relative_to(root)),
                        "line": lineno,
                        "expr": expr,
                        "snippet": line.strip(),
                    })

    return findings


# ---------------------------------------------------------------------------
# 리포트 출력
# ---------------------------------------------------------------------------
def print_report(db_findings: list[dict], src_findings: list[dict]) -> int:
    """결과를 출력하고 종료 코드(0=clean, 1=발견)를 반환한다."""
    total = len(db_findings) + len(src_findings)

    print("=" * 60)
    print("  텍스트 오염 탐지 결과")
    print("=" * 60)

    if db_findings:
        print(f"\n[DB] {len(db_findings)}건 발견:")
        for f in db_findings:
            print(
                f"  FOUND  {f['table']}.{f['column']}  "
                f"row_id={f['row_id']}  expr={f['expr']!r}"
            )
            print(f"         {f['snippet']}")
    else:
        print("\n[DB] CLEAN — 금지 표현 없음")

    if src_findings:
        print(f"\n[SOURCE] {len(src_findings)}건 발견:")
        for f in src_findings:
            print(
                f"  FOUND  {f['file']}:{f['line']}  expr={f['expr']!r}"
            )
            print(f"         {f['snippet']}")
    else:
        print("\n[SOURCE] CLEAN — 금지 표현 없음")

    print("\n" + "=" * 60)
    if total == 0:
        print("  ✅ 전체 CLEAN")
    else:
        print(f"  ⚠️  총 {total}건 발견 — clean_legacy_reports.py 로 정제 필요")
    print("=" * 60)

    return 0 if total == 0 else 1


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="텍스트 오염 탐지")
    parser.add_argument(
        "--db",
        default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "db", "investment.db"),
        help="검사할 SQLite DB 경로",
    )
    parser.add_argument(
        "--no-source",
        action="store_true",
        help="Python 소스 파일 검사 생략",
    )
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"DB 경로  : {args.db}")
    print(f"프로젝트 : {project_root}")
    print()

    db_findings = scan_db(args.db)
    src_findings = [] if args.no_source else scan_source(project_root)

    exit_code = print_report(db_findings, src_findings)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
