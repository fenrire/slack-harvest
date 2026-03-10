"""CLI 엔트리포인트"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .config import Config
from .db import SlackHarvestDB

console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _get_db(ctx: click.Context) -> SlackHarvestDB:
    db_path = Path(ctx.obj.get("db_path", "data/slack_harvest.db"))
    return SlackHarvestDB(db_path)


@click.group()
@click.option("--db", "db_path", default="data/slack_harvest.db", help="DB 파일 경로")
@click.option("-v", "--verbose", is_flag=True, help="상세 로그 출력")
@click.pass_context
def cli(ctx: click.Context, db_path: str, verbose: bool) -> None:
    """Slack Harvest - Slack 워크스페이스 아카이빙 도구"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path
    _setup_logging(verbose)


@cli.command()
@click.option("--full", is_flag=True, help="전체 재동기화 (증분 무시)")
@click.option("-c", "--channel", multiple=True, help="특정 채널만 동기화")
@click.option("--include-archived", is_flag=True, help="보관된 채널 포함")
@click.option("--include-private", is_flag=True, help="비공개 채널 포함")
@click.pass_context
def sync(
    ctx: click.Context,
    full: bool,
    channel: tuple[str, ...],
    include_archived: bool,
    include_private: bool,
) -> None:
    """Slack에서 데이터 동기화"""
    from .harvester import SlackHarvester

    try:
        config = Config.from_env()
    except ValueError as e:
        console.print(f"[red]설정 오류:[/red] {e}")
        sys.exit(1)

    db = _get_db(ctx)
    harvester = SlackHarvester(config.slack_bot_token, db)

    try:
        stats = harvester.sync_all(
            full=full,
            channel_names=list(channel) if channel else None,
            include_archived=include_archived,
            include_private=include_private,
        )

        console.print()
        console.print("[bold green]동기화 완료![/bold green]")
        console.print(f"  사용자: {stats['users']}명")
        console.print(f"  채널: {stats['channels']}개")
        console.print(f"  메시지: {stats['messages']}개")
        console.print(f"  스레드: {stats['threads']}개")
    except Exception as e:
        console.print(f"[red]동기화 실패:[/red] {e}")
        logging.getLogger(__name__).exception("동기화 중 오류")
        sys.exit(1)
    finally:
        db.close()


@cli.command()
@click.option("--force", is_flag=True, help="전체 재생성 (증분 무시)")
@click.option("-c", "--channel", multiple=True, help="특정 채널만 내보내기")
@click.option("-o", "--output", default="export", help="내보내기 디렉토리")
@click.pass_context
def export(
    ctx: click.Context,
    force: bool,
    channel: tuple[str, ...],
    output: str,
) -> None:
    """DB를 Markdown 파일로 내보내기 (QMD용)"""
    from .exporter import MarkdownExporter

    db = _get_db(ctx)
    exporter = MarkdownExporter(db, Path(output))

    try:
        stats = exporter.export_all(
            force=force,
            channel_names=list(channel) if channel else None,
        )

        console.print()
        console.print("[bold green]내보내기 완료![/bold green]")
        console.print(f"  채널: {stats['channels']}개")
        console.print(f"  파일 생성: {stats['files']}개")
        console.print(f"  스킵 (변경 없음): {stats['skipped']}개")
        console.print(f"\n  출력 경로: {Path(output).resolve()}")
    finally:
        db.close()


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """동기화 상태 조회"""
    db = _get_db(ctx)

    try:
        counts = db.get_total_counts()
        channel_stats = db.get_channel_stats()

        console.print()
        console.print("[bold]전체 통계[/bold]")
        console.print(
            f"  사용자: {counts['users']}  채널: {counts['channels']}  "
            f"메시지: {counts['messages']}  리액션: {counts['reactions']}  "
            f"파일: {counts['files']}"
        )
        console.print()

        if not channel_stats:
            console.print("[yellow]동기화된 채널이 없습니다. 'harvest sync'를 실행하세요.[/yellow]")
            return

        table = Table(title="채널별 동기화 상태")
        table.add_column("채널", style="cyan")
        table.add_column("메시지 수", justify="right")
        table.add_column("기간", style="dim")
        table.add_column("마지막 동기화", style="green")
        table.add_column("상태")

        for ch in channel_stats:
            name = ch["name"] or ch["id"]
            msg_count = str(ch["message_count"])
            archived = " (보관)" if ch["is_archived"] else ""

            # 기간
            if ch["earliest_ts"] and ch["latest_ts"]:
                start = _ts_to_date(ch["earliest_ts"])
                end = _ts_to_date(ch["latest_ts"])
                period = f"{start} ~ {end}"
            else:
                period = "-"

            last_sync = ch.get("last_sync_at") or "-"
            status_val = ch.get("status") or "미동기화"

            status_style = {
                "idle": "[green]완료[/green]",
                "syncing": "[yellow]진행중[/yellow]",
                "error": "[red]오류[/red]",
            }.get(status_val, f"[dim]{status_val}[/dim]")

            table.add_row(
                f"#{name}{archived}",
                msg_count,
                period,
                last_sync,
                status_style,
            )

        console.print(table)
    finally:
        db.close()


@cli.command()
@click.argument("query")
@click.option("-c", "--channel", multiple=True, help="특정 채널에서만 검색")
@click.option("--limit", default=20, help="결과 수 제한")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    channel: tuple[str, ...],
    limit: int,
) -> None:
    """메시지 텍스트 검색"""
    db = _get_db(ctx)

    try:
        user_map = db.get_user_display_map()

        if channel:
            # 채널 이름 → ID 변환
            channel_ids = []
            for name in channel:
                ch = db.get_channel_by_name(name)
                if ch:
                    channel_ids.append(ch["id"])
                else:
                    console.print(f"[yellow]채널 '{name}'을 찾을 수 없습니다.[/yellow]")

            if not channel_ids:
                return

            placeholders = ",".join("?" * len(channel_ids))
            sql = f"""
                SELECT m.*, c.name as channel_name
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE m.text LIKE ? AND m.channel_id IN ({placeholders})
                ORDER BY m.ts DESC
                LIMIT ?
            """
            params = [f"%{query}%"] + channel_ids + [limit]
        else:
            sql = """
                SELECT m.*, c.name as channel_name
                FROM messages m
                JOIN channels c ON m.channel_id = c.id
                WHERE m.text LIKE ?
                ORDER BY m.ts DESC
                LIMIT ?
            """
            params = [f"%{query}%", limit]

        rows = db.conn.execute(sql, params).fetchall()

        if not rows:
            console.print(f"[yellow]'{query}'에 대한 결과가 없습니다.[/yellow]")
            return

        console.print(f"\n[bold]검색 결과: {len(rows)}건[/bold]\n")

        for row in rows:
            r = dict(row)
            date = _ts_to_date(r["ts"])
            time = _ts_to_time(r["ts"])
            user = user_map.get(r["user_id"], r.get("user_id", "?"))
            ch_name = r["channel_name"]
            text = r.get("text", "")

            # 텍스트에서 검색어 하이라이트
            text_preview = text[:200]
            if len(text) > 200:
                text_preview += "..."

            console.print(f"[cyan]#{ch_name}[/cyan] [dim]{date} {time}[/dim] [bold]{user}[/bold]")
            console.print(f"  {text_preview}")
            console.print()

    finally:
        db.close()


def _ts_to_date(ts: str) -> str:
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _ts_to_time(ts: str) -> str:
    dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    return dt.strftime("%H:%M")
