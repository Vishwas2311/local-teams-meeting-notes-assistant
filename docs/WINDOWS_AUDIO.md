# Windows audio

PyAudioWPatch is the primary backend. It exposes WASAPI output loopbacks as input devices, including
speaker/headphone/USB/Bluetooth routes. The selected loopback must correspond to the output Teams is
actually using. Device indexes are diagnostic only; persisted preferences use backend, host API,
source kind, and name. SoundCard provides a secondary WASAPI implementation for future/manual fallback.

Always run `python -m meeting_assistant test-audio` while known audio is playing. A WAV file existing
does not prove the correct route; listen to it and confirm expected content. Headset reconnects,
Bluetooth profile changes, docking, and Windows updates can change endpoints.

