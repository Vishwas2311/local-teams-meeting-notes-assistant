# Local Microsoft Teams Meeting Notes Assistant

A visible, consent-first Windows application that captures audio already playing through your selected
speaker/headphone device with WASAPI loopback, optionally captures your microphone as a separate
source, transcribes both locally with faster-whisper, and sends **transcript text only** to your
company-approved Azure OpenAI deployment for structured notes.

It does not use a Teams API, request Teams recording permission, bypass Teams controls, run a meeting
bot, or secretly capture audio. Use it only when organizational policy and participant-consent rules
authorize transcription. The console shows a prominent active indicator for the entire capture.

## Architecture

```text
Teams -> Windows output -> PyAudioWPatch WASAPI loopback --+
Microphone -> PyAudioWPatch input -------------------------+-> persisted WAV chunks
  -> bounded queue -> local faster-whisper -> fsynced TXT + JSONL transcript
  -> text-only hierarchical summaries -> Azure OpenAI v1 Responses API -> Markdown + JSON notes
```

PyAudioWPatch is the primary Windows backend because it exposes WASAPI loopback pseudo-inputs and
supports speakers, wired/USB headsets, and Bluetooth output. A SoundCard WASAPI adapter is included as
an architectural fallback; see [Windows audio](docs/WINDOWS_AUDIO.md). Device preferences store a
portable name/host/kind key under `.local/config.json`, never only a volatile numeric index.

## Privacy and security

Local only: system/microphone audio, temporary WAV chunks, Whisper model/inference, transcripts,
notes, logs. Azure receives only transcript text required for summarization. There is no telemetry,
analytics, public OpenAI fallback, Teams/Graph integration, or raw-audio upload. Prompts treat the
transcript as untrusted data and ignore instructions spoken inside it. TLS verification is never
disabled. Logs redact the configured key and do not include full transcripts.

Do **not** commit `.env`, `.local/`, `data/`, `models/`, audio, transcripts, or notes. They are ignored.
Optional secret scanning is configured in `.pre-commit-config.yaml`.

## Requirements

- Windows 10 or 11 and Python 3.11+
- A WASAPI output device used by Teams
- CPU operation works by default; CUDA is optional
- Internet is needed for the first Whisper model download and Azure note generation
- Azure OpenAI deployment that supports the v1 Responses API

## Windows setup

```powershell
git clone https://github.com/<user>/<repo>.git
cd <repo>
.\setup_windows.ps1
.\.venv\Scripts\Activate.ps1
```

Edit `.env`. Never paste real secrets into `.env.example`.

```dotenv
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com
AZURE_OPENAI_API_KEY=your-real-key-only-in-local-dotenv
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
```

The application appends `/openai/v1/`; either the resource root above or an endpoint already ending
in `/openai/v1` is accepted. The deployment name—not a generic model name—is sent as `model`.

Important local defaults:

```dotenv
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=auto
WHISPER_MODEL_CACHE=./models
CAPTURE_MICROPHONE=true
AUDIO_CHUNK_SECONDS=20
ENABLE_VAD=true
KEEP_RAW_AUDIO=false
```

Use `WHISPER_LANGUAGE=auto` for English/Hindi/Marathi or mixed meetings. The first run downloads the
selected model into `./models`. For compatible NVIDIA CUDA installations, set `WHISPER_DEVICE=cuda`
and a suitable compute type such as `float16`; CPU does not require CUDA.

## First run and selecting Teams audio

Set the Teams speaker to the same physical output shown by the diagnostic. Do not assume index 0:

```powershell
python -m meeting_assistant devices
python scripts/list_audio_devices.py
```

If no saved device matches, `start` opens an interactive selection. Preferences are non-secret and
local. Moving to another laptop triggers selection again if the saved name/host combination is absent.

Play a video or other audio through the chosen Teams output, then test approximately 10 seconds:

```powershell
python -m meeting_assistant test-audio
python scripts/test_audio_capture.py
```

The result is `data/diagnostics/system_test.wav`; silence is reported as a failure. Test the microphone:

```powershell
python -m meeting_assistant test-audio --microphone
```

The result is `data/diagnostics/microphone_test.wav`.

## Azure test

```powershell
python -m meeting_assistant test-azure
python scripts/test_azure_openai.py
```

This makes a minimal text request and never prints the key. Errors distinguish authentication,
authorization, deployment/endpoint, throttling, timeout, connectivity, and unsupported requests.

## Start and stop a meeting

```powershell
python -m meeting_assistant start --title "Document Extraction Discussion"
# or
.\run.ps1 --title "Document Extraction Discussion"
```

Press `Ctrl+C` once. Capture stops, final buffers are persisted, the transcription queue drains,
transcript files close, and Azure notes are generated. Do not close the terminal during this stage.
Raw audio chunks are deleted only after successful transcription when `KEEP_RAW_AUDIO=false`.

Each meeting is stored at:

```text
data/meetings/2026-08-18_103000_document-extraction-discussion/
  metadata.json
  transcript.txt
  transcript.jsonl
  meeting_notes.md
  meeting_notes.json
  logs/
```

If Azure is unavailable, the transcript remains safe. Retry without recording again:

```powershell
python -m meeting_assistant summarize "data\meetings\<meeting-id>"
python -m meeting_assistant summarize "data\meetings\<meeting-id>" --force
```

Explicit cleanup (never automatic):

```powershell
python -m meeting_assistant cleanup --older-than 30
```

## Long meetings and failures

Audio is streamed into independently tagged system/mic chunks; sources are not incorrectly mixed and
no speaker names are invented. The bounded queue prevents unbounded RAM use. Chunks exist on disk
before enqueueing, queue pressure is logged, individual transcription failures retry and leave WAVs
for recovery, and transcript lines are flushed and synced incrementally. Hierarchical summarization
chunks by approximate token budget and reduces evidence before final synthesis.

## Development

```powershell
ruff check .
black --check .
mypy src
pytest -m "not integration"
```

Physical audio and credential tests are integration/manual tests and are not required by CI.

## GitHub and another laptop

```powershell
git init
git add .
git commit -m "Initial local meeting assistant"
git branch -M main
git remote add origin https://github.com/<user>/<repo>.git
git push -u origin main
```

On the other laptop, clone and run `setup_windows.ps1`, edit its new local `.env`, then run device,
audio, microphone, and Azure diagnostics before the first meeting. Never copy credentials through Git.

## Known limitations

- V1 has source labels (`SYSTEM`/`MIC`), not speaker diarization or attendee identification.
- Bluetooth hands-free mode and corporate audio drivers can change available WASAPI endpoints.
- System-loopback capture must be physically verified on each laptop/device route.
- CPU transcription latency depends on model size and hardware; `small`/`int8` is the default balance.
- Mixed-language accuracy varies; Whisper preserves detected text but does not translate by default.
- The included SoundCard fallback is an adapter, not automatic failover during an active capture.
- Periodic summaries are reserved by configuration but intentionally not called in V1 to minimize Azure use.

See [architecture](docs/ARCHITECTURE.md), [privacy](docs/PRIVACY.md),
[troubleshooting](docs/TROUBLESHOOTING.md), and [GitHub setup](docs/GITHUB_SETUP.md).

