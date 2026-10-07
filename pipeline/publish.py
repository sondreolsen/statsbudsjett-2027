"""Publiser dist/ til gh-pages-grenen (force-push, uten historikk for indeksfilene)."""
import subprocess
import sys

from common import DIST, ROOT


def git(*args, cwd=DIST):
    print("  git", " ".join(args))
    subprocess.run(["git", *args], cwd=cwd, check=True)


def publish():
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    if (DIST / ".git").exists():
        import shutil
        shutil.rmtree(DIST / ".git", ignore_errors=True)
    git("init", "-q", "-b", "gh-pages")
    git("add", "-A")
    git("-c", "user.name=statsbudsjett-bot", "-c", "user.email=noreply@github.com",
        "commit", "-q", "-m", "Publiser nettstedet")
    git("push", "-f", remote, "gh-pages")
    print("Publisert.")


if __name__ == "__main__":
    publish()
    sys.exit(0)
