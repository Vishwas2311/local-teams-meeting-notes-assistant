"""Professional command-line interface."""

from __future__ import annotations

import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import numpy as np
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from meeting_assistant.audio.base import AudioDevice, AudioSource
from meeting_assistant.audio.devices import load_preferences, save_preferences
from meeting_assistant.audio.mixer import normalize_for_whisper
from meeting_assistant.audio.recorder import verify_audio_signal, write_wav
from meeting_assistant.audio.wasapi import PyAudioWPatchBackend
from meeting_assistant.config import Settings
from meeting_assistant.exceptions import MeetingAssistantError
from meeting_assistant.llm.azure_openai import AzureResponsesClient
from meeting_assistant.meeting.session import MeetingSession, summarize_existing
from meeting_assistant.utils.files import ensure_writable
from meeting_assistant.utils.logging import configure_logging

app = typer.Typer(no_args_is_help=True, help="Local Windows meeting transcription assistant.")
console = Console()


def _settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise typer.BadParameter(f"Invalid configuration:\n{exc}") from exc


def _backend_devices() -> tuple[PyAudioWPatchBackend, list[AudioDevice]]:
    backend = PyAudioWPatchBackend()
    return backend, backend.list_devices()


def _print_devices(all_devices: list[AudioDevice], selected: set[str] | None = None) -> None:
    selected = selected or set()
    for kind, heading in (
        ("SYSTEM", "Available Output / Loopback Devices"),
        ("MIC", "Available Microphones"),
    ):
        table = Table(title=heading)
        for column in ("#", "Index", "Name", "Host API", "In", "Out", "Hz", "Loopback", "Selected"):
            table.add_column(column)
        candidates = [device for device in all_devices if device.kind == kind]
        for number, device in enumerate(candidates, 1):
            table.add_row(
                str(number),
                str(device.index),
                device.name,
                device.host_api,
                str(device.input_channels),
                str(device.output_channels),
                str(device.sample_rate),
                "yes" if device.loopback else "no",
                "yes" if device.stable_key in selected else "",
            )
        console.print(table)


@app.command()
def devices() -> None:
    """List Windows audio devices and loopback capability."""
    try:
        backend, found = _backend_devices()
        try:
            preferences = load_preferences()
            _print_devices(found, set(preferences.values()))
        finally:
            backend.stop()
    except MeetingAssistantError as exc:
        _fail(exc)


def _choose(
    backend: PyAudioWPatchBackend,
    found: list[AudioDevice],
    kind: AudioSource,
    configured: str,
    preference_key: str,
) -> AudioDevice:
    preferences = load_preferences()
    selectors = [
        configured,
        preferences.get(preference_key, ""),
        preferences.get(preference_key.replace("_device", "_name"), ""),
    ]
    for selector in selectors:
        if not selector:
            continue
        try:
            return backend.select_device(selector, kind)
        except MeetingAssistantError:
            continue
    candidates = [device for device in found if device.kind == kind]
    if not candidates:
        return backend.select_device(None, kind)
    if not sys.stdin.isatty():
        return backend.select_device(None, kind)
    console.print(f"\nNo available saved {kind.lower()} device selection. Choose one:")
    for number, device in enumerate(candidates, 1):
        console.print(f"[{number}] {device.name} ({device.host_api})")
    selection = int(typer.prompt("Selection", type=int))
    if selection < 1 or selection > len(candidates):
        raise typer.BadParameter("Selection is outside the displayed range")
    return candidates[selection - 1]


def _resolve_devices(settings: Settings) -> tuple[AudioDevice, AudioDevice | None]:
    backend, found = _backend_devices()
    try:
        system = _choose(
            backend, found, "SYSTEM", settings.system_audio_device, "system_audio_device"
        )
        microphone = None
        if settings.capture_microphone:
            microphone = _choose(
                backend, found, "MIC", settings.microphone_device, "microphone_device"
            )
        save_preferences(system, microphone)
        return system, microphone
    finally:
        backend.stop()


@app.command("test-audio")
def test_audio(
    microphone: Annotated[
        bool, typer.Option("--microphone", help="Test microphone instead.")
    ] = False,
    seconds: Annotated[int, typer.Option(min=1, max=30)] = 10,
) -> None:
    """Capture a diagnostic WAV and verify it contains a signal."""
    settings = _settings()
    try:
        system, mic = _resolve_devices(settings)
        device = mic if microphone else system
        if device is None:
            raise typer.BadParameter("Microphone capture is disabled; enable CAPTURE_MICROPHONE")
        backend = PyAudioWPatchBackend()
        console.print(f"Capturing {seconds} seconds from: {device.name}")
        try:
            backend.start(device)
            remaining = device.sample_rate * seconds
            blocks: list[np.ndarray] = []
            while remaining > 0:
                count = min(4096, remaining)
                blocks.append(backend.read(count))
                remaining -= count
        finally:
            backend.stop()
        samples = normalize_for_whisper(np.concatenate(blocks), device.sample_rate)
        target = (
            settings.data_directory
            / "diagnostics"
            / ("microphone_test.wav" if microphone else "system_test.wav")
        )
        write_wav(target, samples)
        verify_audio_signal(target)
        console.print(f"[green]Capture successful:[/green] {target.resolve()}")
    except (MeetingAssistantError, OSError, ValueError) as exc:
        _fail(exc)


@app.command("test-azure")
def test_azure() -> None:
    """Make a minimal text-only Azure OpenAI request."""
    settings = _settings()
    try:
        AzureResponsesClient(settings).health_check()
        console.print("[green]Azure OpenAI connection successful.[/green]")
        console.print(f"Deployment: {settings.azure_openai_deployment}")
    except MeetingAssistantError as exc:
        _fail(exc)


@app.command()
def start(
    title: Annotated[str, typer.Option(help="Human-readable meeting title.")] = "Meeting",
) -> None:
    """Start visible local recording/transcription; Ctrl+C finalizes it."""
    settings = _settings()
    try:
        ensure_writable(settings.data_directory)
        system, microphone = _resolve_devices(settings)
        console.print("[bold]Loading local Whisper model (first run may download it)...[/bold]")
        session = MeetingSession(
            settings,
            title=title,
            system_device=system,
            microphone_device=microphone,
            on_transcript_line=lambda line: console.print(line),
        )
        configure_logging(session.storage.logs, settings.log_level, [settings.azure_openai_api_key])
        console.print("=" * 52)
        console.print("[bold]AI Meeting Notes Assistant[/bold]")
        console.print("=" * 52)
        console.print(f"Meeting: {title}\nSystem Audio: [green]✓[/green] {system.name}")
        console.print(
            f"Microphone: {'[green]✓[/green] ' + microphone.name if microphone else 'disabled'}"
        )
        console.print(
            f"Whisper: [green]✓[/green] {settings.whisper_model} / "
            f"{settings.whisper_device} / {settings.whisper_compute_type}"
        )
        console.print(
            "Azure OpenAI: "
            + (
                "[green]✓ Configured[/green]"
                if settings.azure_configured
                else "[yellow]WARNING not configured[/yellow]"
            )
        )
        console.print("\nRecording/Transcription Status: [bold red]● ACTIVE[/bold red]")
        console.print("Visible capture is active. Press Ctrl+C to finish and generate notes.")
        console.print("Capture only with authorization and participant consent.")
        console.print("=" * 52)
        session.start()
        capture_error: Exception | None = None
        try:
            while True:
                time.sleep(0.5)
                failures = [p for p in session.producers if p.error]
                if failures:
                    raise failures[0].error or RuntimeError("Audio capture failed")
        except KeyboardInterrupt:
            console.print("\nMeeting stopped. Processing remaining audio...")
        except Exception as exc:
            capture_error = exc
            console.print(f"\n[yellow]Capture stopped unexpectedly:[/yellow] {exc}")
            console.print("Saving all recoverable audio and transcript data...")
        transcript, notes, summary_error = session.stop_and_finalize()
        console.print(f"\n[green]Transcript finalized:[/green] {transcript.resolve()}")
        if notes:
            console.print(f"[green]Meeting notes:[/green] {notes.resolve()}")
        elif summary_error:
            console.print(f"[yellow]AI summarization failed:[/yellow] {summary_error}")
            console.print(
                f'Run later: python -m meeting_assistant summarize "{session.storage.root}"'
            )
        elif not settings.azure_configured:
            console.print("[yellow]Azure is not configured; transcript is safe locally.[/yellow]")
        if capture_error:
            _fail(capture_error)
    except (MeetingAssistantError, OSError, ValueError) as exc:
        _fail(exc)


@app.command()
def summarize(
    meeting_directory: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    force: Annotated[bool, typer.Option(help="Overwrite existing generated notes.")] = False,
) -> None:
    """Generate or regenerate notes from a saved transcript."""
    try:
        output = summarize_existing(_settings(), meeting_directory.resolve(), force)
        console.print(f"[green]Meeting notes generated:[/green] {output.resolve()}")
    except (MeetingAssistantError, OSError, ValueError) as exc:
        _fail(exc)


@app.command()
def cleanup(
    older_than: Annotated[int, typer.Option(min=1, help="Delete meetings older than N days")],
    yes: Annotated[bool, typer.Option("--yes", help="Skip confirmation.")] = False,
) -> None:
    """Explicitly delete old local meeting directories."""
    root = (_settings().data_directory / "meetings").resolve()
    if not root.exists():
        console.print("No meeting directory exists.")
        return
    cutoff = datetime.now().astimezone() - timedelta(days=older_than)
    targets = [
        child.resolve()
        for child in root.iterdir()
        if child.is_dir() and datetime.fromtimestamp(child.stat().st_mtime).astimezone() < cutoff
    ]
    targets = [target for target in targets if target.parent == root]
    if not targets:
        console.print("No meetings match the retention threshold.")
        return
    console.print("Directories to delete:")
    for target in targets:
        console.print(f"- {target}")
    if not yes and not typer.confirm("Permanently delete these local meeting directories?"):
        console.print("Cancelled.")
        return
    for target in targets:
        shutil.rmtree(target)
    console.print(f"Deleted {len(targets)} meeting director{'y' if len(targets) == 1 else 'ies'}.")


def _fail(exc: Exception) -> None:
    Console(stderr=True).print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1)
