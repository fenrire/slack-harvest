"""Click CLI 진입점."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import Config
from .db.schema import init_db
from .db.repository import Repository
from .slack.client import SlackClient

# Windows cp949 터미널에서 한글 깨짐 방지: stdout을 UTF-8로 재설정
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("cp949", "cp1252", "mbcs"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console()
log = logging.getLogger("slack_harvest")


def _setup() -> tuple[Config, SlackClient, Repository]:
    """공통 초기화: Config → auth_test → DB."""
    config = Config.from_env()
    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[red]오류: {e}[/red]")
        sys.exit(1)

    client = SlackClient(config.slack_token)
    auth = client.auth_test()
    config.workspace = auth.get("team", "unknown")
    console.print(f"워크스페이스: [bold]{config.workspace}[/bold]")

    conn = init_db(config.db_path)
    repo = Repository(conn)

    # workspace URL 저장 (export 시 Slack permalink 생성에 사용)
    workspace_url = auth.get("url", "")
    if workspace_url:
        repo.set_meta("workspace_url", workspace_url.rstrip("/"))

    return config, client, repo


def _setup_db_only() -> tuple[Config, Repository]:
    """DB만 필요한 명령용 초기화 (Slack API 연결 불필요)."""
    config = Config.from_env()
    # workspace가 필요하므로 기존 DB 디렉토리에서 추론
    # output_dir 하위에 워크스페이스 디렉토리가 있는지 확인
    output = config.output_dir
    workspaces = [d for d in output.iterdir() if d.is_dir() and (d / "_db").exists()] if output.exists() else []
    if not workspaces:
        console.print("[red]수집된 워크스페이스가 없습니다. 먼저 'slack-harvest fetch'를 실행하세요.[/red]")
        sys.exit(1)
    if len(workspaces) == 1:
        config.workspace = workspaces[0].name
    else:
        console.print("[yellow]워크스페이스를 선택하세요:[/yellow]")
        for i, ws in enumerate(workspaces, 1):
            console.print(f"  {i}. {ws.name}")
        config.workspace = workspaces[0].name  # 기본: 첫 번째

    conn = init_db(config.db_path)
    repo = Repository(conn)
    console.print(f"워크스페이스: [bold]{config.workspace}[/bold]")
    return config, repo


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="상세 로그 출력")
def main(verbose: bool):
    """슬랙 채널/스레드를 로컬에 아카이빙합니다."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── fetch ─────────────────────────────────────────────────


@main.command()
@click.option("--channel", "-c", multiple=True, help="채널 이름 또는 ID (여러 개 가능)")
@click.option("--thread", "-t", help="스레드 URL")
@click.option("--since", help="시작 날짜 (YYYY-MM-DD) 또는 ts")
@click.option("--full", is_flag=True, help="전체 히스토리 수집 (증분 무시)")
@click.option("--refresh-days", "-r", type=int, default=0,
              help="최근 N일 메시지를 재수집하여 수정 감지 (기본: 0=비활성)")
def fetch(
    channel: tuple[str, ...],
    thread: str | None,
    since: str | None,
    full: bool,
    refresh_days: int,
):
    """채널 또는 스레드 메시지를 수집합니다."""
    config, client, repo = _setup()

    # 사용자 먼저 동기화
    _sync_users(client, repo)

    # 채널 목록 동기화
    _sync_channels(client, repo)

    if thread:
        # 단일 스레드 수집
        parsed = SlackClient.parse_thread_url(thread)
        if not parsed:
            console.print("[red]유효하지 않은 스레드 URL입니다.[/red]")
            return
        ch_id, thread_ts = parsed
        _fetch_thread(client, repo, ch_id, thread_ts)
    elif channel:
        # 지정된 채널 수집
        for ch_name in channel:
            ch = repo.get_channel_by_name(ch_name) or repo.get_channel_by_id(ch_name)
            if not ch:
                console.print(f"[red]채널 '{ch_name}'을 찾을 수 없습니다.[/red]")
                continue
            if full:
                oldest = None
            elif since:
                oldest = since
            elif refresh_days > 0:
                oldest = _days_ago_ts(refresh_days)
            else:
                oldest = repo.get_latest_ts(ch["id"])
            _fetch_channel(client, repo, ch["id"], ch["name"], oldest,
                           detect_edits=(refresh_days > 0))
    else:
        console.print("[yellow]--channel 또는 --thread 옵션을 지정하세요.[/yellow]")
        console.print("예: slack-harvest fetch -c general")
        return

    # 누락 사용자 보충 (게스트, 외부 조직 등)
    _backfill_missing_users(client, repo)

    console.print(f"\n[green]수집 완료![/green] (API 호출 {client.api_calls}회)")


def _backfill_missing_users(client: SlackClient, repo: Repository) -> None:
    """메시지에 등장하지만 users 테이블에 없는 사용자를 개별 조회로 보충."""
    missing = repo.get_missing_user_ids()
    if not missing:
        return
    console.print(f"  누락 사용자 {len(missing)}명 보충 중...")
    filled = 0
    for uid in missing:
        user = client.get_user_info(uid)
        if user:
            repo.upsert_user(user)
            filled += 1
    repo.conn.commit()
    console.print(f"  사용자 {filled}명 보충 완료")


def _days_ago_ts(days: int) -> str:
    """N일 전의 Slack ts 문자열을 생성."""
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return f"{dt.timestamp():.6f}"


def _sync_users(client: SlackClient, repo: Repository) -> None:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        p.add_task("사용자 동기화 중...")
        users = client.list_users()
        count = repo.upsert_users(users)
    console.print(f"  사용자 {count}명 동기화")


def _sync_channels(client: SlackClient, repo: Repository) -> None:
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        p.add_task("채널 목록 동기화 중...")
        channels = client.list_channels()
        count = repo.upsert_channels(channels)
    console.print(f"  채널 {count}개 동기화")


def _fetch_channel(
    client: SlackClient,
    repo: Repository,
    channel_id: str,
    channel_name: str,
    oldest: str | None,
    detect_edits: bool = False,
) -> None:
    repo.set_sync_status(channel_id, "syncing")
    console.print(f"\n[bold]#{channel_name}[/bold] 메시지 수집 중...")

    messages = client.fetch_channel_history(channel_id, oldest=oldest)
    if not messages:
        console.print("  새 메시지 없음")
        repo.set_sync_status(channel_id, "done")
        return

    # 수정 감지: upsert 전에 edited_ts 변경분 카운트
    edited_count = 0
    if detect_edits:
        edited_count = repo.count_edited_updates(channel_id, messages)

    repo.upsert_messages(channel_id, messages)
    console.print(f"  메시지 {len(messages)}개 저장")
    if edited_count:
        console.print(f"  [cyan]수정된 메시지 {edited_count}개 업데이트[/cyan]")

    # 스레드 수집 (reply_count > 0)
    thread_parents = [m for m in messages if m.get("reply_count", 0) > 0]
    if thread_parents:
        thread_msg_count = 0
        with Progress(
            SpinnerColumn(), TextColumn("{task.description}"), console=console
        ) as p:
            task = p.add_task(
                f"스레드 {len(thread_parents)}개 수집 중...",
                total=len(thread_parents),
            )
            for parent in thread_parents:
                replies = client.fetch_thread_replies(channel_id, parent["ts"])
                repo.upsert_messages(channel_id, replies)
                thread_msg_count += len(replies)
                p.advance(task)
        console.print(f"  스레드 답글 {thread_msg_count}개 저장")

    # 파일 메타 저장
    file_count = 0
    for msg in messages:
        for f in msg.get("files", []):
            repo.upsert_file(f, channel_id, msg["ts"])
            file_count += 1
    if file_count:
        console.print(f"  파일 메타 {file_count}개 저장")

    # 증분 기준 업데이트
    max_ts = max(m["ts"] for m in messages)
    repo.update_latest_ts(channel_id, max_ts)
    repo.set_sync_status(channel_id, "done")


def _fetch_thread(
    client: SlackClient, repo: Repository, channel_id: str, thread_ts: str
) -> None:
    console.print(f"스레드 {thread_ts} 수집 중...")
    replies = client.fetch_thread_replies(channel_id, thread_ts)
    repo.upsert_messages(channel_id, replies)
    console.print(f"  메시지 {len(replies)}개 저장")


# ── channels ──────────────────────────────────────────────


@main.command()
@click.option("--private/--no-private", default=True, help="Private 채널 포함 (기본: 포함)")
def channels(private: bool):
    """Slack API에서 접근 가능한 채널 목록을 조회합니다."""
    config, client, repo = _setup()

    ch_list = client.list_channels(include_private=private)

    table = Table(title=f"접근 가능한 채널 ({len(ch_list)}개)")
    table.add_column("채널", style="bold")
    table.add_column("멤버", justify="right")
    table.add_column("Private")
    table.add_column("Topic")

    for ch in sorted(ch_list, key=lambda c: c.get("name", "")):
        name = ch.get("name", "")
        members = str(ch.get("num_members", 0))
        private_mark = "Y" if ch.get("is_private") else ""
        topic = (ch.get("topic") or {}).get("value", "")
        if len(topic) > 50:
            topic = topic[:47] + "..."
        table.add_row(f"#{name}", members, private_mark, topic)

    console.print(table)


# ── sync-users ────────────────────────────────────────────


@main.command("sync-users")
def sync_users_cmd():
    """사용자 프로필을 동기화합니다."""
    config, client, repo = _setup()
    _sync_users(client, repo)
    console.print("[green]사용자 동기화 완료![/green]")


# ── export ────────────────────────────────────────────────


@main.command()
@click.option("--channel", "-c", help="특정 채널만 내보내기")
@click.option("--nexus", is_flag=True, help="NexusEvent JSONL도 내보내기")
def export(channel: str | None, nexus: bool):
    """수집된 데이터를 Markdown으로 내보냅니다."""
    config, client, repo = _setup()

    from .export.markdown import MarkdownExporter
    from .export.linker import Linker
    from .export.downloader import FileDownloader

    # 사용자/채널 맵 구축
    users = {u["id"]: u for u in repo.get_all_users()}
    channels = {c["id"]: c for c in repo.list_channels()}

    linker = Linker(users, channels, config.workspace_dir)
    exporter = MarkdownExporter(repo, linker, config.workspace_dir)

    if channel:
        ch = repo.get_channel_by_name(channel) or repo.get_channel_by_id(channel)
        if not ch:
            console.print(f"[red]채널 '{channel}'을 찾을 수 없습니다.[/red]")
            return
        exporter.export_channel(ch)
    else:
        exporter.export_all()

    console.print("[green]Markdown 내보내기 완료![/green]")

    # 파일 다운로드
    downloader = FileDownloader(config.slack_token, repo, config.workspace_dir)
    count = downloader.download_pending()
    if count:
        console.print(f"  파일 {count}개 다운로드 완료")

    # NexusEvent JSONL
    if nexus and config.nexus_outbox:
        from .export.nexus import NexusExporter

        nx = NexusExporter(repo, config.workspace)
        nx_count = nx.export_to_jsonl(config.nexus_outbox)
        console.print(f"  NexusEvent {nx_count}개 내보내기 완료")
    elif nexus and not config.nexus_outbox:
        console.print("[yellow]NEXUS_OUTBOX_DIR이 설정되지 않았습니다.[/yellow]")


# ── summarize ─────────────────────────────────────────────


@main.command()
@click.option("--channel", "-c", help="특정 채널만 대상")
@click.option("--export", "export_path", type=click.Path(), help="미요약 스레드를 JSON으로 출력")
@click.option("--import", "import_path", type=click.Path(exists=True), help="요약 JSON을 DB에 저장")
@click.option("--llm", is_flag=True, help="Gemini API로 직접 요약 (GEMINI_API_KEY 필요)")
@click.option("--min-replies", default=5, show_default=True, help="최소 답글 수 필터 (--llm 전용)")
def summarize(channel: str | None, export_path: str | None, import_path: str | None, llm: bool, min_replies: int):
    """스레드 요약을 관리합니다 (LLM 요약 캐시)."""
    config, repo = _setup_db_only()

    channel_id = None
    if channel:
        ch = repo.get_channel_by_name(channel) or repo.get_channel_by_id(channel)
        if not ch:
            console.print(f"[red]채널 '{channel}'을 찾을 수 없습니다.[/red]")
            return
        channel_id = ch["id"]

    if import_path:
        # JSON → DB 저장
        data = json.loads(Path(import_path).read_text(encoding="utf-8"))
        count = 0
        with repo.conn:
            for item in data:
                repo.upsert_thread_summary(
                    item["channel_id"],
                    item["thread_ts"],
                    item["summary"],
                    item.get("method", "llm"),
                )
                count += 1
        console.print(f"[green]요약 {count}개 저장 완료![/green]")
        return

    if llm:
        from .summarize.gemini import GeminiSummarizer
        if not config.gemini_api_key:
            console.print("[red]GEMINI_API_KEY가 설정되지 않았습니다.[/red]")
            return
        pending = repo.get_unsummarized_threads(channel_id)
        targets = [t for t in pending if (t["reply_count"] or 0) >= min_replies]
        console.print(f"대상: [bold]{len(targets)}[/bold]개 (답글 {min_replies}개 이상)")
        if not targets:
            console.print("[green]요약할 스레드가 없습니다.[/green]")
            return

        summarizer = GeminiSummarizer(config.gemini_api_key)
        ok = fail = 0
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
            task = progress.add_task("요약 중...", total=len(targets))
            for t in targets:
                replies = repo.get_thread_messages(t["channel_id"], t["thread_ts"])
                reply_texts = [r.get("text", "") for r in replies if r.get("text")]
                summary = summarizer.summarize(t["text"] or "", reply_texts)
                if summary:
                    with repo.conn:
                        repo.upsert_thread_summary(t["channel_id"], t["thread_ts"], summary, "gemini")
                    ok += 1
                else:
                    fail += 1
                progress.advance(task)
                progress.update(task, description=f"요약 중... ({ok}완료 {fail}실패)")
        console.print(f"[green]완료: {ok}개 저장, {fail}개 실패[/green]")
        return

    pending = repo.get_unsummarized_threads(channel_id)

    if export_path:
        # 미요약 스레드 → JSON 출력
        out = []
        for t in pending:
            out.append({
                "channel_id": t["channel_id"],
                "channel_name": t["channel_name"],
                "thread_ts": t["thread_ts"],
                "text": t["text"],
                "reply_count": t["reply_count"],
            })
        Path(export_path).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        console.print(f"[green]미요약 스레드 {len(out)}개 → {export_path}[/green]")
        return

    # 기본: 현황 표시
    console.print(f"\n미요약 스레드: [bold]{len(pending)}[/bold]개")
    if pending:
        table = Table(title="미요약 스레드 (최근 10개)")
        table.add_column("채널", style="bold")
        table.add_column("답글", justify="right")
        table.add_column("내용 미리보기")

        for t in pending[-10:]:
            text_preview = (t["text"] or "")[:60]
            if len(t["text"] or "") > 60:
                text_preview += "..."
            table.add_row(
                f"#{t['channel_name']}", str(t["reply_count"]), text_preview
            )
        console.print(table)
        console.print(
            "\n[dim]사용법: slack-harvest summarize --export pending.json"
            " → Claude Code에서 요약 생성 → slack-harvest summarize --import summaries.json[/dim]"
        )


# ── list ──────────────────────────────────────────────────


@main.command("list")
def list_cmd():
    """수집된 채널 목록을 표시합니다."""
    config, client, repo = _setup()

    channels = repo.list_channels()
    if not channels:
        console.print("수집된 채널이 없습니다. 'slack-harvest fetch'를 실행하세요.")
        return

    table = Table(title="수집된 채널")
    table.add_column("채널", style="bold")
    table.add_column("메시지 수", justify="right")
    table.add_column("Private")
    table.add_column("마지막 수집")

    for ch in channels:
        msg_count = repo.get_message_count(ch["id"])
        private = "Y" if ch["is_private"] else ""
        latest = ch.get("latest_ts", "-")
        table.add_row(f"#{ch['name']}", str(msg_count), private, latest or "-")

    console.print(table)
