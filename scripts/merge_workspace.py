"""워크스페이스 DB 머지 스크립트.

워크스페이스 이름(URL) 변경으로 SlackArchive에 폴더가 분리된 경우,
소스 DB의 모든 행을 타겟 DB로 합집합 머지한다.

- 동일 워크스페이스 전제 (user_id → email 동일성으로 사전 검증할 것).
- 모든 테이블 INSERT OR IGNORE: PK 충돌 시 타겟(최신 수집) 우선, 나머지는 전부 합침.
- 컬럼 순서가 DB마다 다를 수 있으므로 SELECT *를 쓰지 않고 공통 컬럼을 명시 지정.
- 멱등: 재실행해도 결과 동일.

사용:
    python scripts/merge_workspace.py --src "<소스 DB>" --dst "<타겟 DB>" [--apply]

--apply 없이 실행하면 dry-run(이관 예상 행수만 출력).
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# 머지 대상 테이블과 PK (NOT EXISTS 카운트 및 정합성 검증용).
# schema_info / workspace_meta 는 머지 대상 아님 (메타).
TABLES = {
    "channels": ["id"],
    "users": ["id"],
    "messages": ["channel_id", "ts"],
    "files": ["id"],
    "sync_state": ["channel_id"],
    "thread_summaries": ["channel_id", "thread_ts"],
}


def common_columns(con: sqlite3.Connection, table: str) -> list[str]:
    """main/src 양쪽에 공통으로 존재하는 컬럼만 (순서는 main 기준)."""
    main_cols = [r[1] for r in con.execute(f"PRAGMA main.table_info({table})")]
    src_cols = {r[1] for r in con.execute(f"PRAGMA src.table_info({table})")}
    return [c for c in main_cols if c in src_cols]


def count_new(con: sqlite3.Connection, table: str, pk: list[str]) -> int:
    cond = " AND ".join(f"m.{k}=s.{k}" for k in pk)
    sql = (
        f"SELECT COUNT(*) FROM src.{table} s "
        f"WHERE NOT EXISTS (SELECT 1 FROM main.{table} m WHERE {cond})"
    )
    return con.execute(sql).fetchone()[0]


def verify_same_workspace(con: sqlite3.Connection) -> tuple[bool, str]:
    """겹치는 user_id의 email 불일치가 있으면 다른 워크스페이스로 판단."""
    rows = con.execute(
        """SELECT COUNT(*) FROM main.users m JOIN src.users s ON m.id=s.id
           WHERE m.email<>'' AND s.email<>'' AND m.email<>s.email"""
    ).fetchone()[0]
    if rows > 0:
        return False, f"겹치는 유저 중 이메일 불일치 {rows}건 — 다른 워크스페이스 의심"
    return True, "동일 워크스페이스 확인 (겹치는 유저 이메일 불일치 0건)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="소스 DB 경로")
    ap.add_argument("--dst", required=True, help="타겟 DB 경로")
    ap.add_argument("--apply", action="store_true", help="실제 머지 실행 (없으면 dry-run)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    src, dst = Path(args.src), Path(args.dst)
    if not src.exists() or not dst.exists():
        print(f"DB 경로 오류: src={src.exists()} dst={dst.exists()}")
        return 1

    con = sqlite3.connect(str(dst))
    con.execute("ATTACH ? AS src", (str(src),))

    ok, msg = verify_same_workspace(con)
    print(f"[검증] {msg}")
    if not ok:
        print("→ 머지 중단. 워크스페이스 동일성 확인 필요.")
        return 2

    print(f"\n[{'APPLY' if args.apply else 'DRY-RUN'}] {src.name} → {dst.name}\n")
    total_new = 0
    for t, pk in TABLES.items():
        new = count_new(con, t, pk)
        total_new += new
        cols = common_columns(con, t)
        if args.apply and new > 0:
            collist = ", ".join(cols)
            con.execute(
                f"INSERT OR IGNORE INTO main.{t} ({collist}) "
                f"SELECT {collist} FROM src.{t}"
            )
        after = con.execute(f"SELECT COUNT(*) FROM main.{t}").fetchone()[0]
        print(f"  {t:18s} 신규 {new:>8,}  → 머지후 {after:>9,}")

    if args.apply:
        con.commit()
        print(f"\n총 {total_new:,}행 이관 완료. VACUUM 실행 중...")
        con.execute("VACUUM")
        print("VACUUM 완료.")
    else:
        print(f"\n총 {total_new:,}행 이관 예정 (dry-run, 적용 안 함). --apply로 실행.")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
