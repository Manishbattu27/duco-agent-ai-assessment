from __future__ import annotations

from pathlib import Path
import os
import subprocess


def write_tts_audio(text: str, output_path: Path) -> Path | None:
    """Generate a local WAV briefing when the OS TTS engine is available."""
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        return _valid_audio_path(output_path)
    except Exception:
        return _write_windows_sapi_audio(text, output_path)


def _write_windows_sapi_audio(text: str, output_path: Path) -> Path | None:
    if os.name != "nt":
        return None
    input_path = output_path.with_suffix(".tts.txt")
    input_path.write_text(text, encoding="utf-8")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$s.SetOutputToWaveFile('{str(output_path)}'); "
        f"$s.Speak((Get-Content -Raw '{str(input_path)}')); "
        "$s.Dispose();"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            check=True,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return _valid_audio_path(output_path)
    except Exception:
        return None
    finally:
        try:
            input_path.unlink()
        except OSError:
            pass


def _valid_audio_path(output_path: Path) -> Path | None:
    if output_path.exists() and output_path.stat().st_size > 1024:
        return output_path
    try:
        output_path.unlink()
    except OSError:
        pass
    return None
