"""Install the pinned official Alpaca CLI into the ignored local tool directory."""

import hashlib
import io
import platform
import tarfile
from pathlib import Path

import httpx

VERSION = "0.0.14"
# SHA-256 digests published on the official v0.0.14 release.
DIGESTS = {
    "darwin_amd64": "9b2a420b6a3e2e0dbaf408d14c8ef1b9e01608764c84bf479e2839bca2f41246",
    "darwin_arm64": "142b26997157748e6db4146133f63066c29ef18be5857eae4b05f9d3157ccfd5",
    "linux_amd64": "6c82ef31f94dd61aae1c90e40fc41fdfaf8111bd50e9a2780b9d8d304eb2ba66",
    "linux_arm64": "621270e2b935dbae587e6ae05fe04a10bc178b4c9c638961a3d0214568ff2617",
}


def main() -> None:
    destination = Path(__file__).resolve().parents[1] / ".local/bin/alpaca"
    if destination.exists():
        print("An Alpaca CLI already exists at .local/bin/alpaca; left unchanged.")
        return
    architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(
        platform.machine().lower(), platform.machine().lower()
    )
    target = f"{platform.system().lower()}_{architecture}"
    if target not in DIGESTS:
        raise SystemExit("Supported systems: macOS/Linux, amd64/arm64. Use WSL on Windows.")
    url = (
        f"https://github.com/alpacahq/cli/releases/download/v{VERSION}/"
        f"cli_{VERSION}_{target}.tar.gz"
    )
    response = httpx.get(url, follow_redirects=True, timeout=120)
    response.raise_for_status()
    archive = response.content
    if hashlib.sha256(archive).hexdigest() != DIGESTS[target]:
        raise SystemExit("Official release checksum mismatch; nothing installed.")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        members = [m for m in bundle.getmembers() if m.isfile() and Path(m.name).name == "alpaca"]
        if len(members) != 1:
            raise SystemExit("Expected exactly one Alpaca executable; nothing installed.")
        executable = bundle.extractfile(members[0])
        if executable is None:
            raise SystemExit("Cannot read Alpaca executable; nothing installed.")
        binary = executable.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as installed:
        installed.write(binary)
    destination.chmod(0o755)
    print(f"Installed official Alpaca CLI v{VERSION} at .local/bin/alpaca (SHA-256 verified).")


if __name__ == "__main__":
    main()
