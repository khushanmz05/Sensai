"""Trusted entry point INSIDE the namespace; install limits before user code."""
import ctypes
import errno
from pathlib import Path
import resource
import sys
import traceback


def restrict():
    for kind, limit in (
        (resource.RLIMIT_AS, 256 * 1024 * 1024),
        (resource.RLIMIT_CPU, 2),
        (resource.RLIMIT_FSIZE, 0),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 32),
    ):
        resource.setrlimit(kind, (limit, limit))
    # Default-deny syscalls. In particular: no exec/fork/clone, sockets, namespace
    # creation, mounts, ptrace or kernel administration, even via ctypes.
    sec = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    sec.seccomp_init.argtypes = [ctypes.c_uint32]
    sec.seccomp_init.restype = ctypes.c_void_p
    sec.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    sec.seccomp_syscall_resolve_name.restype = ctypes.c_int
    sec.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    sec.seccomp_rule_add.restype = ctypes.c_int
    sec.seccomp_load.argtypes = [ctypes.c_void_p]
    sec.seccomp_load.restype = ctypes.c_int
    sec.seccomp_release.argtypes = [ctypes.c_void_p]
    ctx = sec.seccomp_init(0x00050000 | errno.EPERM)
    if not ctx:
        raise RuntimeError('Cannot initialize syscall filter')
    allowed = (
        'read write readv writev pread64 close close_range lseek fstat newfstatat '
        'stat lstat statx open openat readlink readlinkat getdents getdents64 '
        'access faccessat faccessat2 fcntl getcwd '
        'mmap mprotect munmap mremap brk madvise futex '
        'clock_gettime clock_getres nanosleep clock_nanosleep gettimeofday time '
        'getpid getppid gettid getuid geteuid getgid getegid uname sysinfo '
        'sched_getaffinity sched_yield getrandom '
        'rt_sigaction rt_sigprocmask rt_sigreturn sigaltstack exit exit_group'
    ).split()
    try:
        for name in allowed:
            number = sec.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and sec.seccomp_rule_add(ctx, 0x7FFF0000, number, 0) != 0:
                raise RuntimeError('Cannot configure syscall filter')
        if sec.seccomp_load(ctx) != 0:
            raise RuntimeError('Cannot load syscall filter')
    finally:
        sec.seccomp_release(ctx)


def main():
    try:
        source = Path('/work/code.py').read_text(encoding='utf-8')
        restrict()
    except BaseException:
        print('Sandbox isolation setup failed; user code was not executed.', file=sys.stderr)
        return 125
    try:
        exec(compile(source, '/work/code.py', 'exec'), {'__name__': '__main__', '__file__': '/work/code.py'})
    except SystemExit as error:
        if error.code is None:
            return 0
        if isinstance(error.code, int):
            return error.code
        print(error.code, file=sys.stderr)
        return 1
    except BaseException:
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
