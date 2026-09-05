"""Optional developer transport for an explicitly configured Kindle host.

This helper is not part of the public installation path. Host, port, user, and
key are supplied through arguments or environment variables; no household
address or private-key path is embedded here.
"""
import argparse
import io
import os
from pathlib import Path
import shlex
import subprocess
import tarfile


def command(remote, host, user, port, key):
    args = ["ssh", "-p", str(port), "-o", "IdentitiesOnly=yes",
            "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
            "-o", "StrictHostKeyChecking=yes"]
    if key:
        args[1:1] = ["-i", key]
    args.extend([f"{user}@{host}", remote])
    return args


def run(remote, host, user, port, key, **kwargs):
    return subprocess.run(command(remote, host, user, port, key), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["exec", "put", "get", "tree"])
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--host", default=os.environ.get("KINDLE_HOST"), required=not os.environ.get("KINDLE_HOST"))
    parser.add_argument("--user", default=os.environ.get("KINDLE_USER", "root"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("KINDLE_PORT", "2222")))
    parser.add_argument("--key", default=os.environ.get("KINDLE_SSH_KEY"))
    args = parser.parse_args()
    if args.action == "exec":
        run(args.paths[0], args.host, args.user, args.port, args.key)
    elif args.action == "get":
        remote, local = args.paths
        path = Path(local)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as target:
            os.chmod(path, 0o600)
            run("cat " + shlex.quote(remote), args.host, args.user, args.port, args.key, stdout=target)
    else:
        local, remote = args.paths
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
            if args.action == "tree":
                for path in sorted(Path(local).rglob("*")):
                    if path.is_file() and not path.is_symlink():
                        archive.add(path, arcname=str(path.relative_to(local)), recursive=False)
                directory = remote
            else:
                archive.add(local, arcname=Path(remote).name, recursive=False)
                directory = str(Path(remote).parent)
        run("mkdir -p " + shlex.quote(directory) + " && tar -xzf - -C " + shlex.quote(directory),
            args.host, args.user, args.port, args.key, input=buffer.getvalue())


if __name__ == "__main__":
    main()
