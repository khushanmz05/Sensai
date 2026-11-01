"""Local WSL/Linux demo provider in a separate, pinned Python environment."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys

SOURCE = 'https://github.com/searxng/searxng.git'
REVISION = 'cff884f98b1141bb6d5d3f104094fddafba78ef1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true', help='install the pinned provider, then start it')
    args = parser.parse_args()
    if not sys.platform.startswith('linux'):
        parser.error('Run this command in Ubuntu/WSL. Use Docker Compose for other platforms.')
    source = Path.home() / '.cache' / 'sensai-searxng'
    python = source / '.venv/bin/python'
    config = Path(__file__).resolve().with_name('settings.yml')
    def git(*arguments):
        return subprocess.check_output(['git', '-C', str(source), *arguments], text=True).strip()
    if args.install:
        if not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['git', 'clone', '--depth', '1', SOURCE, str(source)], check=True)
        if not (source / '.git').is_dir() or git('remote', 'get-url', 'origin') != SOURCE:
            parser.error('Provider cache is not the expected official repository; inspect it manually.')
        if git('diff', '--name-only') or git('diff', '--cached', '--name-only'):
            parser.error('Provider sources have local changes; inspect them before installing.')
        if git('rev-parse', 'HEAD') != REVISION:
            subprocess.run(['git', '-C', str(source), 'fetch', '--depth', '1', 'origin', REVISION], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--detach', REVISION], check=True)
        if not python.exists():
            subprocess.run([sys.executable, '-m', 'venv', str(source / '.venv')], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(source / 'requirements.txt'), 'setuptools'], check=True)
        subprocess.run([str(python), '-m', 'pip', 'install', '--no-build-isolation', '--no-deps', '-e', str(source)], check=True)
    if not python.exists() or not (source / '.git').is_dir():
        parser.error('Provider is not installed. Run: python deploy/search/local.py --install')
    if git('rev-parse', 'HEAD') != REVISION or git('diff', '--name-only') or git('diff', '--cached', '--name-only'):
        parser.error('Provider revision differs from the tested version; inspect the cache before starting.')
    env = dict(os.environ, SEARXNG_SETTINGS_PATH=str(config), SEARXNG_SECRET=secrets.token_hex(32),
               SEARXNG_BIND_ADDRESS='127.0.0.1', SEARXNG_PORT='8088', SEARXNG_DEBUG='0')
    print('Starting SearXNG on http://127.0.0.1:8088 (local demo only). Keep this terminal open; Ctrl+C stops it.', flush=True)
    os.chdir(source)
    os.execve(str(python), [str(python), '-m', 'searx.webapp'], env)


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError) as error:
        print('Search setup failed. Check network access and the preceding installation error.', file=sys.stderr)
        sys.exit(1)
