"""A fresh Bubblewrap namespace per call; never fall back to host execution."""
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

MAX_CODE_BYTES = 16384
MAX_OUTPUT_BYTES = 4096
WALL_SECONDS = 5


class SandboxError(Exception):
    pass


def bubblewrap():
    if sys.platform != 'linux':
        raise SandboxError('T2 requires Linux/WSL. Run it inside Ubuntu WSL.')
    executable = shutil.which('bwrap')
    if not executable:
        candidate = Path.home() / '.cache/sensai-sandbox/runtime/usr/bin/bwrap'
        if candidate.is_file() and os.access(candidate, os.X_OK):
            executable = str(candidate)
    if not executable:
        raise SandboxError('Install the sandbox: sudo apt install bubblewrap libseccomp2 python3')
    return executable


def command(directory):
    # Fixed operator-owned runtime. No model-supplied paths, flags or executable.
    python = Path('/usr/bin/python3').resolve()
    if not python.is_file():
        raise SandboxError('System Python is missing: sudo apt install python3')
    args = [bubblewrap(), '--unshare-all', '--unshare-user', '--unshare-pid',
            '--unshare-net', '--disable-userns', '--new-session', '--die-with-parent',
            '--cap-drop', 'ALL', '--clearenv', '--setenv', 'PATH', '/usr/bin',
            '--setenv', 'HOME', '/nonexistent', '--setenv', 'LANG', 'C.UTF-8',
            '--hostname', 'sensai-sandbox', '--ro-bind', str(python), str(python)]
    # Only system libraries/interpreter are exposed; no /home, /mnt, project,
    # host /tmp, credentials, daemon sockets or host /proc.
    for path in ('/usr/lib', '/usr/lib64'):
        if Path(path).exists():
            args += ['--ro-bind', path, path]
    args += ['--symlink', 'usr/lib', '/lib', '--symlink', 'usr/lib64', '/lib64',
             '--ro-bind', '/dev/null', '/dev/null',
             '--ro-bind', str(directory), '/work', '--chdir', '/work',
             '--remount-ro', '/', '--', str(python), '-I', '-S', '-B', '-u',
             '/work/bootstrap.py']
    return args


async def run_python(code):
    if not isinstance(code, str) or not code.strip():
        raise SandboxError('Provide a nonempty Python program.')
    try:
        encoded = code.encode('utf-8')
    except UnicodeError as error:
        raise SandboxError('Python source must be valid UTF-8.') from error
    if len(encoded) > MAX_CODE_BYTES:
        raise SandboxError('Python source exceeds 16 KiB.')
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='sensai-python-') as temporary:
        directory = Path(temporary)
        (directory / 'code.py').write_bytes(encoded)
        shutil.copyfile(Path(__file__).with_name('bootstrap.py'), directory / 'bootstrap.py')
        args = command(directory)
        try:
            process = await asyncio.create_subprocess_exec(
                *args, stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                limit=MAX_OUTPUT_BYTES, start_new_session=True,
            )
        except OSError as error:
            raise SandboxError('Cannot start Bubblewrap; no code was executed.') from error
        buffers = [bytearray(), bytearray()]
        total, truncated, timed_out = 0, False, False

        def kill():
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()

        async def drain(stream, index):
            nonlocal total, truncated
            while True:
                chunk = await stream.read(4096)
                if not chunk:
                    return
                remaining = MAX_OUTPUT_BYTES - total
                buffers[index].extend(chunk[:remaining])
                total += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    truncated = True
                    kill()

        readers = [asyncio.create_task(drain(process.stdout, 0)),
                   asyncio.create_task(drain(process.stderr, 1))]
        try:
            try:
                await asyncio.wait_for(process.wait(), WALL_SECONDS)
            except asyncio.TimeoutError:
                timed_out = True
                kill()
                await process.wait()
            await asyncio.gather(*readers)
        finally:
            # Applies to Ctrl+C, web Stop, MCP cancellation and disconnect too.
            kill()
            await process.wait()
            for task in readers:
                task.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
        status = ('timeout' if timed_out else 'output_limit' if truncated else
                  'ok' if process.returncode == 0 else 'error')
        return {'status': status, 'exit_code': process.returncode,
                'stdout': buffers[0].decode('utf-8', errors='replace'),
                'stderr': buffers[1].decode('utf-8', errors='replace'),
                'timed_out': timed_out, 'output_truncated': truncated,
                'duration_ms': round((time.monotonic() - started) * 1000),
                'limits': {'wall_seconds': WALL_SECONDS, 'cpu_seconds': 2,
                           'memory_mib': 256, 'output_bytes': MAX_OUTPUT_BYTES},
                'isolation': 'bubblewrap+seccomp; no network, host files, writes or child processes'}
