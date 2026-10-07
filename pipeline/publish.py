"""Publiser dist/ til gh-pages-grenen (force-push, uten historikk for indeksfilene)."""
import subprocess

from common import CACHE, DIST, ROOT, rmtree

GITDIR = CACHE / "gh-pages.git"  # utenfor dist/, slik at neste bygging kan slette dist/ fritt


def git(*args):
    print("  git", " ".join(args))
    subprocess.run(["git", f"--git-dir={GITDIR}", f"--work-tree={DIST}", *args], cwd=DIST, check=True)


def publish():
    remote = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    rmtree(GITDIR)
    git("init", "-q", "-b", "gh-pages")
    git("add", "-A")
    git("-c", "user.name=statsbudsjett-bot", "-c", "user.email=noreply@github.com",
        "commit", "-q", "-m", "Publiser nettstedet")
    git("push", "-f", remote, "gh-pages")
    print("Publisert.")


if __name__ == "__main__":
    publish()
