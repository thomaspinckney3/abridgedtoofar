"""ElevenLabs audiobook generation for assembled abridgments.

The stage reads the published or work-tree abridgment.txt, splits it into
bounded narration chunks, sends each chunk to ElevenLabs text-to-speech, and
writes resumable artifacts under work/<book>/audiobook/.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import Book

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_MODEL = "eleven_multilingual_v2"
DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"
DEFAULT_MAX_CHARS = 9000
DEFAULT_CONTEXT_CHARS = 1200
MANIFEST_VERSION = 2


class AudiobookError(RuntimeError):
    """Raised when audiobook generation cannot proceed."""


@dataclass
class AudiobookChunk:
    id: str
    text: str
    text_path: Path
    audio_path: Path
    text_sha256: str

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class AudiobookResult:
    book_id: str
    source_path: Path
    output_dir: Path
    manifest_path: Path
    chunk_count: int
    generated_count: int
    skipped_count: int
    planned_count: int
    error_count: int
    total_chars: int
    combined_audio_path: Path | None
    published_audio_path: Path | None
    combine_error: str | None = None


class ElevenLabsClient:
    def __init__(self, api_key: str, *, timeout: float = 120.0,
                 retries: int = 2) -> None:
        self.api_key = api_key
        self.timeout = timeout
        self.retries = retries

    def text_to_speech(
        self,
        *,
        voice_id: str,
        text: str,
        model_id: str,
        output_format: str,
        voice_settings: dict[str, Any] | None = None,
        previous_text: str | None = None,
        next_text: str | None = None,
        previous_request_ids: list[str] | None = None,
        seed: int | None = None,
        language_code: str | None = None,
        apply_text_normalization: str | None = None,
        enable_logging: bool = True,
    ) -> tuple[bytes, dict[str, str | None]]:
        body: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
        }
        if voice_settings:
            body["voice_settings"] = voice_settings
        if previous_request_ids:
            body["previous_request_ids"] = previous_request_ids[-3:]
        elif previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text
        if seed is not None:
            body["seed"] = seed
        if language_code:
            body["language_code"] = language_code
        if apply_text_normalization:
            body["apply_text_normalization"] = apply_text_normalization

        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        params = urllib.parse.urlencode({
            "output_format": output_format,
            "enable_logging": "true" if enable_logging else "false",
        })
        voice_path = urllib.parse.quote(voice_id, safe="")
        url = f"{ELEVENLABS_TTS_URL}/{voice_path}?{params}"
        req = urllib.request.Request(
            url,
            data=encoded,
            method="POST",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": _accept_header(output_format),
            },
        )

        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = resp.read()
                    headers = {
                        "request_id": (
                            resp.headers.get("request-id")
                            or resp.headers.get("x-request-id")
                        ),
                        "character_cost": resp.headers.get(
                            "character-cost"
                        ),
                    }
                    return data, headers
            except urllib.error.HTTPError as e:
                error_text = _decode_error_body(e)
                if e.code not in (429, 500, 502, 503, 504):
                    raise AudiobookError(
                        f"ElevenLabs HTTP {e.code}: {error_text}"
                    ) from e
                last_error = AudiobookError(
                    f"ElevenLabs HTTP {e.code}: {error_text}"
                )
                _sleep_before_retry(e, attempt)
            except urllib.error.URLError as e:
                last_error = e
                _sleep_before_retry(None, attempt)
        raise AudiobookError(f"ElevenLabs request failed: {last_error}")


def generate_audiobook(
    book: Book,
    *,
    voice_id: str | None,
    input_path: Path | None = None,
    output_dir: Path | None = None,
    model_id: str = DEFAULT_MODEL,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
    max_chars: int = DEFAULT_MAX_CHARS,
    context_chars: int = DEFAULT_CONTEXT_CHARS,
    voice_settings: dict[str, Any] | None = None,
    seed: int | None = None,
    language_code: str | None = None,
    apply_text_normalization: str | None = "auto",
    enable_logging: bool = True,
    stitch: bool = True,
    combine: bool = True,
    overwrite: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
    timeout: float = 120.0,
    retries: int = 2,
) -> AudiobookResult:
    source_path = input_path or default_abridgment_path(book)
    if not source_path.exists():
        raise AudiobookError(
            f"no abridgment text at {source_path}; run `forage assemble "
            f"{book.book_id}` first or pass --input"
        )
    if max_chars < 1000:
        raise AudiobookError("--max-chars must be at least 1000")
    if context_chars < 0:
        raise AudiobookError("--context-chars cannot be negative")
    if limit is not None and limit < 0:
        raise AudiobookError("--limit cannot be negative")

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not dry_run:
        if not api_key:
            raise AudiobookError(
                "ELEVENLABS_API_KEY is required unless --dry-run is set"
            )
        if not voice_id:
            raise AudiobookError(
                "a voice id is required; set audiobook.voice_id in "
                f"books/{book.book_id}/metadata.json or pass --voice-id"
            )

    output_dir = output_dir or (book.work_dir / "audiobook")
    # A preview has its own sidecars and manifest. It must never relabel real
    # audio with text or settings which have not been synthesized.
    artifact_dir = output_dir / "preview" if dry_run else output_dir
    manifest_path = artifact_dir / "audiobook_manifest.json"
    chunks_dir = artifact_dir / "chunks"
    audio_dir = output_dir / "audio"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        audio_dir.mkdir(parents=True, exist_ok=True)

    text = source_path.read_text(encoding="utf-8", errors="replace")
    chunks = _make_chunks(text, max_chars=max_chars, chunks_dir=chunks_dir,
                          audio_dir=audio_dir, output_format=output_format)
    if not chunks:
        raise AudiobookError("abridgment text contains no narration chunks")

    client = ElevenLabsClient(api_key or "", timeout=timeout, retries=retries)

    old_manifest = _load_manifest(output_dir / "audiobook_manifest.json")
    previous_ids: list[str] = []
    generated = skipped = planned = errors = 0
    entries: list[dict[str, Any]] = []
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    for index, chunk in enumerate(chunks):
        ids = previous_ids[-3:] if stitch and enable_logging else []
        request = {
            "voice_id": voice_id or "",
            "text": chunk.text,
            "model_id": model_id,
            "output_format": output_format,
            "voice_settings": voice_settings or None,
            # ElevenLabs ignores previous_text when request IDs are supplied.
            "previous_text": (
                _context_before(chunks, index, context_chars)
                if stitch and not ids else None
            ),
            "next_text": (
                _context_after(chunks, index, context_chars) if stitch else None
            ),
            "previous_request_ids": ids or None,
            "seed": seed,
            "language_code": language_code or None,
            "apply_text_normalization": apply_text_normalization or None,
            "enable_logging": enable_logging,
        }
        request_sha256 = _json_sha256({
            "version": MANIFEST_VERSION,
            "provider": ELEVENLABS_TTS_URL,
            "request": request,
            "stitch": stitch,
            "context_chars": context_chars if stitch else 0,
        })
        old_entry = _old_chunk_entry(old_manifest, chunk, request_sha256)
        request_id: str | None = None
        status = "planned"
        error: str | None = None
        character_cost: str | None = None
        api_ms: int | None = None
        audio_sha256: str | None = None
        audio_size: int | None = None

        if dry_run:
            _atomic_write(chunk.text_path, (chunk.text + "\n").encode("utf-8"))
            planned += 1
        elif not overwrite and old_entry:
            status = "skipped"
            skipped += 1
            request_id = old_entry.get("request_id")
            character_cost = old_entry.get("character_cost")
            audio_sha256 = old_entry["audio_sha256"]
            audio_size = old_entry["audio_size"]
        elif limit is not None and index >= limit:
            planned += 1
        else:
            start = time.monotonic()
            try:
                audio, headers = client.text_to_speech(**request)
                if not isinstance(audio, bytes) or not audio:
                    raise AudiobookError("ElevenLabs returned empty or invalid audio")
                request_id = headers.get("request_id")
                character_cost = headers.get("character_cost")
                _replace_chunk_output(chunk, audio)
                audio_sha256 = hashlib.sha256(audio).hexdigest()
                audio_size = len(audio)
                api_ms = int((time.monotonic() - start) * 1000)
                status = "generated"
                generated += 1
            except Exception as e:
                status = "error"
                error = str(e)
                request_id = None
                errors += 1

        if status in ("generated", "skipped") and request_id:
            previous_ids = [*previous_ids, request_id][-3:]
        else:
            # Do not stitch around an unsuccessful predecessor using old IDs.
            previous_ids = []

        entries.append({
            "id": chunk.id,
            "text_path": (
                str(chunk.text_path)
                if dry_run or status in ("generated", "skipped") else None
            ),
            "audio_path": (
                str(chunk.audio_path)
                if status in ("generated", "skipped") else None
            ),
            "chars": chunk.char_count,
            "text_sha256": chunk.text_sha256,
            "request_sha256": request_sha256,
            "audio_sha256": audio_sha256,
            "audio_size": audio_size,
            "status": status,
            "request_id": request_id,
            "character_cost": character_cost,
            "api_ms": api_ms,
            "error": error,
        })

    combined_audio_path: Path | None = None
    published_audio_path: Path | None = None
    combine_error: str | None = None
    if combine and not dry_run and (errors or planned):
        combine_error = f"cannot combine incomplete narration: {errors} failed and {planned} planned chunks"
    elif combine and not dry_run:
        audio_paths = [c.audio_path for c in chunks]
        generated_enough = all(
            entry["status"] in ("generated", "skipped")
            and _verified_audio(chunk.audio_path, entry)
            for chunk, entry in zip(chunks, entries)
        )
        if generated_enough:
            try:
                combined_audio_path, combine_error = combine_audio_chunks(
                    audio_paths, output_dir / f"audiobook{_extension(output_format)}",
                    output_format=output_format,
                )
            except OSError as e:
                combine_error = f"could not combine audio: {e}"
            if combined_audio_path:
                publication_path = (
                    book.source_path.parent
                    / f"audiobook{_extension(output_format)}"
                )
                try:
                    _atomic_write(publication_path, combined_audio_path.read_bytes())
                    published_audio_path = publication_path
                except OSError as e:
                    combine_error = f"could not publish combined audio: {e}"
        else:
            combine_error = "chunk audio changed before combination"

    _atomic_write_json(manifest_path, {
        "version": MANIFEST_VERSION,
        "book_id": book.book_id,
        "source_text_path": str(source_path),
        "output_dir": str(output_dir),
        "generated_at": generated_at,
        "dry_run": dry_run,
        "voice_id": voice_id,
        "model_id": model_id,
        "output_format": output_format,
        "max_chars": max_chars,
        "context_chars": context_chars,
        "enable_logging": enable_logging,
        "stitch": stitch,
        "voice_settings": voice_settings or {},
        "seed": seed,
        "language_code": language_code,
        "apply_text_normalization": apply_text_normalization,
        "chunk_count": len(chunks),
        "total_chars": sum(c.char_count for c in chunks),
        "generated_count": generated,
        "skipped_count": skipped,
        "planned_count": planned,
        "error_count": errors,
        "combined_audio_path": (
            str(combined_audio_path) if combined_audio_path else None
        ),
        "published_audio_path": (
            str(published_audio_path) if published_audio_path else None
        ),
        "combine_error": combine_error,
        "chunks": entries,
    })

    return AudiobookResult(
        book_id=book.book_id,
        source_path=source_path,
        output_dir=output_dir,
        manifest_path=manifest_path,
        chunk_count=len(chunks),
        generated_count=generated,
        skipped_count=skipped,
        planned_count=planned,
        error_count=errors,
        total_chars=sum(c.char_count for c in chunks),
        combined_audio_path=combined_audio_path,
        published_audio_path=published_audio_path,
        combine_error=combine_error,
    )


def default_abridgment_path(book: Book) -> Path:
    published = book.source_path.parent / "abridgment.txt"
    if published.exists():
        return published
    return book.work_dir / "abridgment.txt"


def split_text_into_chunks(text: str, *, max_chars: int = DEFAULT_MAX_CHARS
                           ) -> list[str]:
    chunks: list[str] = []
    current = ""
    for unit in _split_units(text, max_chars=max_chars):
        sep = "\n\n" if current else ""
        candidate = f"{current}{sep}{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = unit
    if current:
        chunks.append(current)
    return chunks


def combine_audio_chunks(
    audio_paths: list[Path],
    output_path: Path,
    *,
    output_format: str,
) -> tuple[Path | None, str | None]:
    if not output_format.startswith("mp3_"):
        return None, "automatic combine currently supports mp3 output only"
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None, "ffmpeg not found; chunk audio files were left separate"

    list_path = output_path.with_suffix(".concat.txt")
    list_path.write_text(
        "".join(f"file '{_ffmpeg_path(p)}'\n" for p in audio_paths),
        encoding="utf-8",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # ffmpeg can leave a partial output on failure. Keep the previous complete
    # combined file until a nonempty replacement has been produced.
    with tempfile.TemporaryDirectory(prefix=".combine-", dir=output_path.parent) as temp:
        staged = Path(temp) / output_path.name
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-c", "copy", str(staged),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if not staged.is_file() or not staged.stat().st_size:
                raise AudiobookError("ffmpeg returned no audio")
            staged.replace(output_path)
            return output_path, None
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or e.stdout or str(e)).strip()
            return None, msg
        except (OSError, AudiobookError) as e:
            return None, str(e)


def _make_chunks(text: str, *, max_chars: int, chunks_dir: Path,
                 audio_dir: Path, output_format: str) -> list[AudiobookChunk]:
    extension = _extension(output_format)
    chunks: list[AudiobookChunk] = []
    for i, chunk_text in enumerate(split_text_into_chunks(
        text, max_chars=max_chars
    ), 1):
        chunk_id = f"{i:04d}"
        digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()
        chunks.append(AudiobookChunk(
            id=chunk_id,
            text=chunk_text,
            text_path=chunks_dir / f"{chunk_id}.txt",
            audio_path=audio_dir / f"{chunk_id}{extension}",
            text_sha256=digest,
        ))
    return chunks


def _split_units(text: str, *, max_chars: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    paragraphs = [
        re.sub(r"\n+", " ", part).strip()
        for part in re.split(r"\n\s*\n", normalized)
        if part.strip()
    ]
    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue
        units.extend(_split_long_paragraph(paragraph, max_chars=max_chars))
    return units


def _split_long_paragraph(text: str, *, max_chars: int) -> list[str]:
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", text)
        if s.strip()
    ]
    units: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                units.append(current)
                current = ""
            units.extend(_split_words(sentence, max_chars=max_chars))
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                units.append(current)
            current = sentence
    if current:
        units.append(current)
    return units


def _split_words(text: str, *, max_chars: int) -> list[str]:
    units: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                units.append(current)
            if len(word) > max_chars:
                units.extend(
                    word[i:i + max_chars] for i in range(0, len(word), max_chars)
                )
                current = ""
            else:
                current = word
    if current:
        units.append(current)
    return units


def _context_before(chunks: list[AudiobookChunk], index: int,
                    context_chars: int) -> str | None:
    if index <= 0 or context_chars == 0:
        return None
    return chunks[index - 1].text[-context_chars:]


def _context_after(chunks: list[AudiobookChunk], index: int,
                   context_chars: int) -> str | None:
    if index >= len(chunks) - 1 or context_chars == 0:
        return None
    return chunks[index + 1].text[:context_chars]


def _old_chunk_entry(manifest: dict[str, Any] | None,
                     chunk: AudiobookChunk,
                     request_sha256: str) -> dict[str, Any]:
    if (not manifest or manifest.get("version") != MANIFEST_VERSION
            or manifest.get("dry_run") is not False):
        return {}
    items = manifest.get("chunks")
    if not isinstance(items, list):
        return {}
    for item in items:
        if (isinstance(item, dict)
                and item.get("id") == chunk.id
                and item.get("status") in ("generated", "skipped")
                and item.get("error") is None
                and item.get("text_sha256") == chunk.text_sha256
                and item.get("request_sha256") == request_sha256
                and _verified_audio(chunk.audio_path, item)):
            try:
                if chunk.text_path.read_text(encoding="utf-8") == chunk.text + "\n":
                    return item
            except (OSError, UnicodeError):
                pass
    return {}


def _verified_audio(path: Path, entry: dict[str, Any]) -> bool:
    try:
        audio = path.read_bytes()
    except OSError:
        return False
    return (bool(audio)
            and len(audio) == entry.get("audio_size")
            and hashlib.sha256(audio).hexdigest() == entry.get("audio_sha256"))


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".audiobook-",
                                     delete=False) as handle:
        staged = Path(handle.name)
        try:
            handle.write(data)
            handle.close()
            staged.replace(path)
        finally:
            staged.unlink(missing_ok=True)


def _atomic_write_json(path: Path, data: Any) -> None:
    _atomic_write(path, (json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                  .encode("utf-8"))


def _replace_chunk_output(chunk: AudiobookChunk, audio: bytes) -> None:
    """Stage both files, restoring earlier outputs if either replacement fails.

    The manifest is written only after success. A process interruption between
    replacements is detected by the next run's byte and sidecar checks.
    """
    temp_dir = Path(tempfile.mkdtemp(prefix=".chunk-", dir=chunk.audio_path.parent))
    retain_recovery = False
    try:
        replacements = [
            (chunk.audio_path, audio),
            (chunk.text_path, (chunk.text + "\n").encode("utf-8")),
        ]
        backups: dict[Path, Path | None] = {}
        staged: dict[Path, Path] = {}
        for index, (path, content) in enumerate(replacements):
            staged[path] = temp_dir / f"{index}.new"
            staged[path].write_bytes(content)
            backup = temp_dir / f"{index}.old" if path.exists() else None
            if backup is not None:
                shutil.copyfile(path, backup)
            backups[path] = backup
        replaced: list[Path] = []
        try:
            for path, _ in replacements:
                staged[path].replace(path)
                replaced.append(path)
        except BaseException as error:
            rollback_errors = []
            for path in reversed(replaced):
                backup = backups[path]
                try:
                    if backup is None:
                        path.unlink(missing_ok=True)
                    else:
                        backup.replace(path)
                except OSError as rollback_error:
                    rollback_errors.append((path, backup, rollback_error))
            if rollback_errors:
                retain_recovery = True
                recovery = "; ".join(
                    f"restore {path} from {backup}" if backup else f"remove partial {path}"
                    for path, backup, _ in rollback_errors
                )
                raise AudiobookError(
                    f"chunk replacement rollback failed; recovery files retained in "
                    f"{temp_dir}: {recovery}"
                ) from error
            raise
    finally:
        if not retain_recovery:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _load_manifest(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def _extension(output_format: str) -> str:
    if output_format.startswith("mp3_"):
        return ".mp3"
    if output_format.startswith("wav_"):
        return ".wav"
    if output_format.startswith("pcm_"):
        return ".pcm"
    if output_format.startswith("ulaw_"):
        return ".ulaw"
    return ".audio"


def _accept_header(output_format: str) -> str:
    if output_format.startswith("mp3_"):
        return "audio/mpeg"
    if output_format.startswith("wav_"):
        return "audio/wav"
    return "application/octet-stream"


def _decode_error_body(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read().decode("utf-8", errors="replace")
    except Exception:
        body = ""
    return body.strip() or error.reason


def _sleep_before_retry(error: urllib.error.HTTPError | None,
                        attempt: int) -> None:
    retry_after = None
    if error is not None:
        retry_after = error.headers.get("retry-after")
    try:
        delay = float(retry_after) if retry_after else 0.5 * (2 ** attempt)
    except ValueError:
        delay = 0.5 * (2 ** attempt)
    time.sleep(min(delay, 10.0))


def _ffmpeg_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "'\\''")
