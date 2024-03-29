from pathlib import Path

import librosa

# Get the full path of the current file
current_file_path = Path(__file__).resolve()

# Get the path of the parent directory
parent_dir = current_file_path.parent
# Load an audio file as a NumPy array
start_recording, samplerate = librosa.load(
    parent_dir / "start_recording.wav", sr=None, mono=True
)
stop_recording, samplerate = librosa.load(
    parent_dir / "stop_recording.wav", sr=None, mono=True
)
