# Architecture

Capture threads own one Windows stream each and never run inference. They normalize stereo/device-rate
float PCM to 16 kHz mono PCM16 WAV, persist it, then enqueue metadata. A bounded queue separates them
from the one persistent faster-whisper worker. System and microphone timelines remain source-tagged.

The transcript writer appends text and JSONL under a lock and flushes plus `fsync`s every segment.
At shutdown producers flush, the queue drains, metadata is finalized, and a text-only Azure adapter
performs map/reduce summarization. Interfaces isolate audio, transcription, storage, and LLM services.

