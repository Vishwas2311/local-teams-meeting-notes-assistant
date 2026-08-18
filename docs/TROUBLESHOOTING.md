# Troubleshooting

- **No loopback device:** ensure Windows, PyAudioWPatch, and a WASAPI output are present; reconnect the
  headset and rerun `devices`.
- **Silent WAV:** play known audio through the exact selected output, check Windows volume mixer, and
  select again after a route/profile change.
- **Bluetooth:** choose the stereo output for playback where possible; hands-free mode may reduce quality.
- **Slow transcription:** use `tiny`, `base`, or `small`; retain CPU `int8`; increase queue size only
  within available disk/RAM constraints.
- **Whisper first run:** model download requires network access; corporate proxy restrictions may block it.
- **Azure 404:** use the Azure resource endpoint and exact deployment name, not merely the base model name.
- **Azure unsupported request:** confirm the deployment supports Azure v1 Responses API. The transcript
  is safe and can be summarized later.
- **Failed chunk:** inspect preserved WAV names listed in metadata/logs; other chunks continue.

