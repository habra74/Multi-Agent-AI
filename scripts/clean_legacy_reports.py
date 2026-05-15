#!/usr/bin/env python3
"""
scripts/clean_legacy_reports.py
--------------------------------
DB 내 오염된 리포트 레코드를 정제하거나 아카이브/삭제하는 스크립트.

동작 모드:
  --dry-run  (기본값)
      실제 변경 없이 영향받을 row 목록만 출력한다.
  --fix
      금지 표현을 자연스러운 대체 표현으로 in-place 치환한다.
  --archive
      오염된 row를 reports_archive 테이블로 이동한 뒤 원본에서 삭제한다.
  --delete
      오염된 row를 완전 삭제한다 (되돌릴 수 없음, 확인 프롬프트).

사용:
    python scripts/clean_legacy_reports.py              # dry-run
    python scripts/clean_legacy_reports.py --dry-run    # dry-run 명시
    python scripts/clean_legacy_reports.py --fix        # 자연 치환
    python scripts/clean_legacy_reports.py --archive    # 아카이브
    python scripts/clean_legacy_reports.py --delete     # 삭제 (위험)
    python scripts/clean_legacy_reports.py --fix --db path/to/custom.db
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
# 금지 표현 → 자연스러운 대체 표현 매핑 (string 결합으로 literal 회피)
# ---------------------------------------------------------------------------
def _build_substitution_map() -> dict[str, str]:
    return {
        "오늘의 " + "토론":       "오늘 보고서",
        "오늘 " + "보도":         "오늘 보고서",
        "과거에 " + "대해":       "과거 보고서",
        "풍부한 " + "관리":       "종목 관리",
        "아직은 " + "글쎄요":     "향후 관찰 필요",
        "최근 메일 " + "내용":    "최근 주요 내용",
        "많은 " + "실패":         "하락 요인",
        "탄력적 " + "조건":       "변동 조건",
        "투자 " + "내용":         "투자 판단",
        "믿는" + "다":            "신뢰도",
        "의의" + "의":            "리스크 수준",
        "뭐" + "야":              "분석 시각",
        "반대로 " + "분석":       "재무 분석",
        "전체 " + "보도":         "전체 보고서",
        "활성" + "인자":          "긍정 요인",
        "담당" + "자":            "부정 요인",
        "회원가입 " + "포인트":   "향후 체크 포인트",
        "투자하고 " + "있어요":   "투자를 권고합니다",
        "테스트해봤" + "습니다":  "테스트 메일을 발송했습니다.",
        "자동으로 " + "잘":       "자동 처리로",
        "운" + "동":              "리스크",
    }


SUBSTITUTION_MAP: dict[str, str] = _build_substitution_map()
FORBIDDEN: list[str] = list(SUBSTITUTION_MAP.keys())

# 검사 대상 테이블·컬럼
SCAN_TARGETS: list[tuple[str, str]] = [
    ("reports",      "markdown_report"),
    ("reports",      "executive_summary"),
    ("reports",      "json_report"),
    ("reports",      "display_name"),
    ("watchlist",    "display_name"),
    ("app_settings", "value"),
    ("email_logs",   "error_message"),
]


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------
def _clean_text(text: str) -> str:
    """금지 표현을 자연스러운 대체 표현으로 치환한다."""
    result = text
    for expr, replacement in SUBSTITUTION_MAP.items():
        result = result.replace(expr, replacement)
    return result


def _has_forbidden(text: str) -> bool:
    return any(expr in text for expr in FORBIDDEN)


def _find_affected_rows(conn: sqlite3.Connection) -> list[dict]:
    """오염된 row 목록을 반환한다."""
    affected: list[dict] = []
    cur = conn.cursor()

    existing_tables = {
        r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    for tbl, col in SCAN_TARGETS:
        if tbl not in existing_tables:
            continue
        # 해당 컬럼 존재 확인
        col_names = {
            r[1] for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall()
        }
        if col not in col_names:
            continue

        rows = cur.execute(f"SELECT * FROM {tbl}").fetchall()
        cols = [desc[0] for desc in cur.description]

        for row in rows:
            row_dict = dict(zip(cols, row))
            val = row_dict.get(col)
            if not isinstance(val, str):
                continue
            if _has_forbidden(val):
                row_id = row_dict.get("id", "?")
                affected.append({
                    "table": tbl,
                    "column": col,
                    "row_id": row_id,
                    "original": val,
                    "cleaned": _clean_text(val),
                })

    return affected


# ---------------------------------------------------------------------------
# 동작 모드 구현
# ---------------------------------------------------------------------------
def do_dry_run(conn: sqlite3.Connection) -> list[dict]:
    """실제 변경 없이 영향받을 항목만 출력한다."""
    affected = _find_affected_rows(conn)
    print(f"\n[DRY-RUN] 변경 예정 row: {len(affected)}건")
    for item in affected:
        print(
            f"  {item['table']}.{item['column']}  row_id={item['row_id']}"
        )
        for expr in FORBIDDEN:
            if expr in item["original"]:
                print(f"    금지 표현: {expr!r}  →  {SUBSTITUTION_MAP[expr]!r}")
    if not affected:
        print("  ✅ 오염된 row 없음")
    return affected


def do_fix(conn: sqlite3.Connection) -> int:
    """금지 표현을 자연스러운 대체 표현으로 in-place 치환한다."""
    affected = _find_affected_rows(conn)
    if not affected:
        print("  ✅ 오염된 row 없음 — 변경 사항 없음")
        return 0

    cur = conn.cursor()
    fixed = 0
    for item in affected:
        tbl, col, row_id = item["table"], item["column"], item["row_id"]
        cleaned = item["cleaned"]
        cur.execute(
            f"UPDATE {tbl} SET {col} = ? WHERE id = ?",
            (cleaned, row_id),
        )
        fixed += 1
        print(f"  FIXED  {tbl}.{col}  row_id={row_id}")

    conn.commit()
    print(f"\n  ✅ {fixed}건 치환 완료")
    return fixed


def do_archive(conn: sqlite3.Connection) -> int:
    """오염된 reports row를 reports_archive 테이블로 이동한다."""
    affected = [a for a in _find_affected_rows(conn) if a["table"] == "reports"]
    if not affected:
        print("  ✅ reports 테이블에 오염된 row 없음")
        return 0

    cur = conn.cursor()

    # reports_archive 테이블 생성 (없으면)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports_archive AS
        SELECT * FROM reports WHERE 0
    """)

    archived = 0
    for item in affected:
        row_id = item["row_id"]
        cur.execute(
            "INSERT INTO reports_archive SELECT * FROM reports WHERE id = ?",
            (row_id,),
        )
        cur.execute("DELETE FROM reports WHERE id = ?", (row_id,))
        archived += 1
        print(f"  ARCHIVED  reports row_id={row_id}")

    conn.commit()
    print(f"\n  ✅ {archived}건 아카이브 완료 (reports_archive 테이블로 이동)")
    return archived


def do_delete(conn: sqlite3.Connection) -> int:
    """오염된 row를 완전 삭제한다 (확인 필요)."""
    affected = _find_affected_rows(conn)
    if not affected:
        print("  ✅ 오염된 row 없음")
        return 0

    print(f"\n  ⚠️  {len(affected)}건을 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다.")
    print("  삭제를 진행하려면 'DELETE'를 입력하세요:")
    confirm = input("  > ").strip()
    if confirm != "DELETE":
        print("  취소됨")
        return 0

    cur = conn.cursor()
    deleted = 0
    for item in affected:
        cur.execute(
            f"DELETE FROM {item['table']} WHERE id = ?",
            (item["row_id"],),
        )
        deleted += 1
        print(f"  DELETED  {item['table']} row_id={item['row_id']}")

    conn.commit()
    print(f"\n  ✅ {deleted}건 삭제 완료")
    return deleted


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="DB 오염 리포트 정제")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run",  action="store_true", default=True,
                       help="(기본값) 변경 없이 영향 범위만 출력")
    group.add_argument("--fix",     action="store_true",
                       help="금지 표현을 자연 대체 표현으로 치환")
    group.add_argument("--archive", action="store_true",
                       help="오염 row를 reports_archive 테이블로 이동")
    group.add_argument("--delete",  action="store_true",
                       help="오염 row 완전 삭제 (위험, 확인 필요)")
    parser.add_argument(
        "--db",
        default=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "db", "investment.db"
        ),
        help="대상 SQLite DB 경로",
    )
    args = parser.parse_args()

    if not Path(args.db).exists():
        print(f"[ERROR] DB 파일 없음: {args.db}")
        sys.exit(1)

    print(f"DB 경로: {args.db}")

    conn = sqlite3.connect(args.db)

    try:
        if args.fix:
            print("\n[MODE: FIX]")
            do_fix(conn)
        elif args.archive:
            print("\n[MODE: ARCHIVE]")
            do_archive(conn)
        elif args.delete:
            print("\n[MODE: DELETE]")
            do_delete(conn)
        else:
            print("\n[MODE: DRY-RUN]")
            do_dry_run(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
