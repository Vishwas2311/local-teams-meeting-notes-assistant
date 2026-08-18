# GitHub setup and migration

Before every push, run `git status` and verify `.env`, `data`, `.local`, `models`, audio, transcripts,
and notes are absent. Optionally install `pre-commit` and run `pre-commit install` for secret scanning.

Clone on a new Windows laptop, run `setup_windows.ps1`, create that laptop's local `.env`, then test
device discovery, system audio, microphone, and Azure. Audio IDs are intentionally not portable;
the first-run selector resolves the current laptop's endpoint.
