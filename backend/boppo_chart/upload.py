"""Push files to a Boppo tablet over its local HTTPS API.

Mirrors the handoff's curl flow (section 3.5). The device uses a self-signed
cert (hence `-k`/no-verify) and is reachable at `boppo-<SERIAL>.local` over mDNS
on the same LAN. Pairing prompts for physical approval on the tablet.

Uploads under `/sd/activities/user/` and `/sd/config/user/` need no Developer
Mode. These functions talk to real hardware — they are not exercised in tests.
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path


def _base_url(serial: str) -> str:
    return f"https://boppo-{serial}.local"


def pair(
    serial: str,
    request_id: str | None = None,
    *,
    timeout_s: float = 120.0,
    poll_interval_s: float = 2.0,
) -> str:
    """Request a device password, polling until the user approves on the device.

    Pairing is a two-step flow: the POST shows an approval prompt on the tablet
    and returns `{"status": "in-progress"}` until approved, then
    `{"status": "success", "password": ...}`. `request_id` must be numeric (the
    device rejects non-numeric ids); a random one is used if not given.
    """
    if request_id is None:
        request_id = str(random.randint(10000, 99999))
    url = f"{_base_url(serial)}/get-password?requestid={request_id}"

    deadline = time.time() + timeout_s
    prompted = False
    while True:
        result = subprocess.run(
            ["curl", "-k", "-sS", "-X", "POST", url],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"unexpected pairing response: {result.stdout!r}")

        status = data.get("status")
        if status == "success":
            return data["password"]
        if status != "in-progress":
            raise RuntimeError(f"pairing failed ({status!r}): {result.stdout!r}")

        if not prompted:
            print("waiting for approval on the device ...")
            prompted = True
        if time.time() > deadline:
            raise RuntimeError("pairing timed out waiting for device approval")
        time.sleep(poll_interval_s)


def upload(serial: str, password: str, local_file: Path, remote_path: str) -> None:
    """Upload one file to `remote_path` on the device."""
    local_file = Path(local_file)
    url = f"{_base_url(serial)}/files/upload?path={remote_path}"
    subprocess.run(
        [
            "curl", "-k", "-fsS",
            "-H", f"Authorization: Bearer {password}",
            "-X", "POST",
            "--data-binary", f"@{local_file}",
            url,
        ],
        check=True,
    )


def execute_command(serial: str, password: str, command: str) -> str:
    """Run a device command via the /command endpoint. Returns its output.

    `start`, `top_buttons_wakeup`, and `auto_update` are always available; other
    commands need Developer Mode.
    """
    url = f"{_base_url(serial)}/command"
    result = subprocess.run(
        ["curl", "-k", "-fsS", "-H", f"Authorization: Bearer {password}",
         "-X", "POST", "--data", command, url],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def start_activity(serial: str, password: str, activity: str = "rhythm_game") -> str:
    """Launch a user WASM activity (no menu slot / Developer Mode needed).

    Matches boppo_cli: `start wasm user/wasm/<pkg>/<pkg>.wasm`.
    """
    cmd = f"start wasm user/wasm/{activity}/{activity}.wasm"
    return execute_command(serial, password, cmd)


def upload_activity(
    serial: str,
    password: str,
    wasm: Path,
    audio_files,
    activity: str = "rhythm_game",
) -> None:
    """Upload a built activity binary and its song asset(s) in one go.

    Deploys to `/sd/activities/user/wasm/<activity>/` to match boppo_cli's layout:
    the binary as `<activity>.wasm`, each song under `songs/`. `audio_files` may be
    a single path or a list.
    """
    if isinstance(audio_files, (str, Path)):
        audio_files = [audio_files]
    base = f"/sd/activities/user/wasm/{activity}"
    upload(serial, password, wasm, f"{base}/{activity}.wasm")
    for audio in audio_files:
        upload(serial, password, audio, f"{base}/songs/{Path(audio).name}")


def upload_bundle_dir(
    serial: str,
    password: str,
    out_dir: Path,
    wasm: Path,
    activity: str = "rhythm_game",
    on_file=None,
) -> None:
    """Upload the wasm plus every file under the bundle's `songs/` and `names/`.

    Mirrors those folders into the activity dir on the device so the compiled-in
    `audio_file` / `name_audio` paths resolve.
    """
    out_dir = Path(out_dir)
    base = f"/sd/activities/user/wasm/{activity}"
    if on_file:
        on_file(Path(wasm).name)
    upload(serial, password, wasm, f"{base}/{activity}.wasm")
    for sub in ("songs", "names"):
        d = out_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if f.is_file():
                if on_file:
                    on_file(f"{sub}/{f.name}")
                upload(serial, password, f, f"{base}/{sub}/{f.name}")
