#!/usr/bin/env python3
"""
install_epm.py

Downloads epm.py from the protected URL and installs it as a global
command "epm", cleaning up after itself.

Usage:
    python3 install_epm.py <password>
    python3 install_epm.py --uninstall
"""
import os
import sys
import stat
import shutil
import tempfile
import urllib.request
import urllib.error
import argparse
from pathlib import Path

BASE_URL = "https://epm.nahcrof.com/install/epm.py"
EXPORT_MARK = "# added by install_epm.py"


def download_epm(dest_path: Path, password: str):
    url = f"{BASE_URL}?password={password}"
    print(f"Downloading {url} → {dest_path}")
    try:
        with urllib.request.urlopen(url) as resp, open(dest_path, "wb") as out:
            if resp.status != 200:
                raise urllib.error.HTTPError(
                    url, resp.status, resp.reason, resp.headers, None
                )
            out.write(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error: HTTP {e.code} {e.reason}", file=sys.stderr)
        print(password)
        print(dest_path)
        sys.exit(1)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)


def make_executable(path: Path):
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_path_in_shell_rc(bin_dir: Path):
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    rc_file = None
    if shell.endswith("bash"):
        rc_file = home / ".bashrc"
    elif shell.endswith("zsh"):
        rc_file = home / ".zshrc"
    if not rc_file:
        return
    export_line = f'export PATH="{bin_dir}:$PATH"'
    content = rc_file.read_text() if rc_file.exists() else ""
    if export_line not in content:
        print(f"Adding PATH export to {rc_file}")
        with open(rc_file, "a") as f:
            f.write(f"\n{EXPORT_MARK}\n{export_line}\n")


def remove_path_from_shell_rc(bin_dir: Path):
    shell = os.environ.get("SHELL", "")
    home = Path.home()
    rc_file = None
    if shell.endswith("bash"):
        rc_file = home / ".bashrc"
    elif shell.endswith("zsh"):
        rc_file = home / ".zshrc"
    if not rc_file or not rc_file.exists():
        return
    lines = rc_file.read_text().splitlines()
    export_line = f'export PATH="{bin_dir}:$PATH"'
    new_lines = []
    skip = False
    for line in lines:
        if line.strip() == EXPORT_MARK:
            skip = True
            continue
        if skip and line.strip() == export_line:
            skip = False
            continue
        new_lines.append(line)
    rc_file.write_text("\n".join(new_lines))
    print(f"Cleaned PATH export from {rc_file}")


def install(password: str):
    is_root = os.geteuid() == 0
    target_dir = (
        Path("/usr/local/bin") if is_root else Path.home() / ".local" / "bin"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "epm"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        epm_py = tmp_path / "epm.py"

        download_epm(epm_py, password)

        text = epm_py.read_text()
        if not text.startswith("#!"):
            text = "#!/usr/bin/env python3\n" + text
            epm_py.write_text(text)

        make_executable(epm_py)
        print(f"Moving to {target_path}")
        shutil.move(str(epm_py), str(target_path))

    print("Installed epm →", target_path)
    if not is_root:
        ensure_path_in_shell_rc(target_dir)
        shell_rc = (
            ".bashrc" if os.environ.get("SHELL", "").endswith("bash") else ".zshrc"
        )
        print("Reload your shell or run:")
        print(f"  source {Path.home() / shell_rc}")

        # ----------------------------------------------------------------
        # Create a small 'root wrapper' so that `sudo epm ...` still works.
        # ----------------------------------------------------------------
        # We install /usr/local/bin/epm (must be writable via sudo) as a tiny
        # shell script that execs the real ~/.local/bin/epm with all args.
        wrapper_path = Path("/usr/local/bin/epm")
        real_epm = target_path  # e.g. /home/alice/.local/bin/epm
        wrapper_sh = f"""#!/usr/bin/env bash
exec "{real_epm}" "$@"
"""
        try:
            # echo wrapper_sh | sudo tee /usr/local/bin/epm >/dev/null
            proc = __import__("subprocess").run(
                ["sudo", "tee", str(wrapper_path)],
                input=wrapper_sh.encode(),
                stdout=__import__("subprocess").DEVNULL,
                check=True,
            )
            __import__("subprocess").run(
                ["sudo", "chmod", "+x", str(wrapper_path)], check=True
            )
            print(f"Installed sudo‐wrapper → {wrapper_path}")
        except Exception as e:
            print(
                "Warning: could not write root‐wrapper:", e, file=sys.stderr
            )
        # ----------------------------------------------------------------
    print("Done.")


def uninstall():
    is_root = os.geteuid() == 0
    target_dir = (
        Path("/usr/local/bin") if is_root else Path.home() / ".local" / "bin"
    )
    target_path = target_dir / "epm"

    if target_path.exists():
        print(f"Removing {target_path}")
        target_path.unlink()
    else:
        print(f"No epm binary found at {target_path}")

    if not is_root:
        remove_path_from_shell_rc(target_dir)
    print("Uninstall complete.")


def main():
    parser = argparse.ArgumentParser(description="Install or uninstall epm.")
    parser.add_argument("password", nargs="?", help="Password to download epm")
    parser.add_argument(
        "--uninstall", action="store_true", help="Uninstall epm"
    )
    args = parser.parse_args()

    if args.uninstall:
        uninstall()
    else:
        if not args.password:
            parser.error("Password is required for installation")
        install(args.password)


if __name__ == "__main__":
    main()


