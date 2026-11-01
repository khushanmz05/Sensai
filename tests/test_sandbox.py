"""Real namespace/seccomp isolation, limits, cleanup and MCP feedback tests."""
import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from sandbox import runner

ROOT = Path(__file__).resolve().parents[1]
try:
    runner.bubblewrap()
    AVAILABLE = True
except runner.SandboxError:
    AVAILABLE = False


class ValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_source_never_starts_a_process(self):
        with patch.object(runner.asyncio, 'create_subprocess_exec') as launch:
            for code in ('', ' ', None, 'x' * 16385, '\ud800'):
                with self.subTest(code=str(code)[:15]), self.assertRaises(runner.SandboxError):
                    await runner.run_python(code)
            launch.assert_not_called()

    async def test_missing_isolation_never_falls_back_to_python(self):
        with patch.object(runner, 'bubblewrap', side_effect=runner.SandboxError('Unavailable')), \
             patch.object(runner.asyncio, 'create_subprocess_exec') as launch:
            with self.assertRaises(runner.SandboxError):
                await runner.run_python('print(1)')
            launch.assert_not_called()


@unittest.skipUnless(AVAILABLE, 'Install bubblewrap and libseccomp2 on Linux/WSL')
class IsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_python_and_tracebacks(self):
        result = await runner.run_python('import math, json; print(json.dumps([math.factorial(5), "Привет"]))')
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(json.loads(result['stdout']), [120, 'Привет'])
        for source, error in [('print(1/0)', 'ZeroDivisionError'), ('def broken(:', 'SyntaxError')]:
            with self.subTest(error=error):
                result = await runner.run_python(source)
                self.assertEqual(result['status'], 'error', result)
                self.assertIn(error, result['stderr'])
                self.assertNotEqual(result['exit_code'], 0)

    async def test_host_files_environment_network_processes_and_writes_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / 'secret.txt'
            secret.write_text('PRIVATE_HOST_VALUE')
            source = f'''
import os, socket, subprocess, ctypes
denied = []
checks = [
    lambda: open({str(secret)!r}).read(),
    lambda: open('/proc/1/environ').read(),
    lambda: open('/work/code.py', 'w'),
    lambda: open('/new-file', 'w'),
    lambda: socket.socket(),
    lambda: os.fork(),
    lambda: subprocess.run(['/usr/bin/python3', '-c', 'print(1)']),
]
for action in checks:
    try:
        action()
        denied.append(False)
    except OSError:
        denied.append(True)
assert all(denied), denied
assert 'SENSAI_TEST_SECRET' not in os.environ
print('isolated', len(denied))
'''
            with patch.dict(os.environ, {'SENSAI_TEST_SECRET': 'PRIVATE_ENV_VALUE'}):
                result = await runner.run_python(source)
            self.assertEqual(result['status'], 'ok', result)
            self.assertEqual(result['stdout'], 'isolated 7\n')
            self.assertEqual(secret.read_text(), 'PRIVATE_HOST_VALUE')

    async def test_direct_syscalls_cannot_bypass_filter(self):
        result = await runner.run_python('''
import ctypes, errno
lib = ctypes.CDLL('libc.so.6', use_errno=True)
assert lib.socket(2, 1, 0) == -1 and ctypes.get_errno() == errno.EPERM
assert lib.fork() == -1 and ctypes.get_errno() == errno.EPERM
assert lib.unshare(0x10000000) == -1 and ctypes.get_errno() == errno.EPERM
assert lib.mount(b'none', b'/work', b'tmpfs', 0, None) == -1
print('blocked')
''')
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['stdout'], 'blocked\n')

    async def test_wall_cpu_memory_and_output_limits(self):
        sleepy = await runner.run_python('import time; time.sleep(30)')
        self.assertTrue(sleepy['timed_out'], sleepy)
        self.assertLess(sleepy['duration_ms'], 8000)
        busy = await runner.run_python('while True: pass')
        self.assertNotEqual(busy['exit_code'], 0, busy)
        self.assertLess(busy['duration_ms'], 5000)
        memory = await runner.run_python('x = bytearray(300 * 1024 * 1024)')
        self.assertEqual(memory['status'], 'error', memory)
        self.assertIn('MemoryError', memory['stderr'])
        output = await runner.run_python('while True: print("x" * 4000)')
        self.assertTrue(output['output_truncated'], output)
        self.assertEqual(len(output['stdout'].encode()) + len(output['stderr'].encode()), runner.MAX_OUTPUT_BYTES)

    async def test_cancellation_reaps_process_and_cleans_temporary_directory(self):
        launch = runner.asyncio.create_subprocess_exec
        children, directories = [], []
        async def capture(*args, **kwargs):
            directories.append(next(Path(arg) for arg in args if isinstance(arg, str) and '/sensai-python-' in arg))
            child = await launch(*args, **kwargs)
            children.append(child)
            return child
        with patch.object(runner.asyncio, 'create_subprocess_exec', capture):
            task = asyncio.create_task(runner.run_python('import time; time.sleep(30)'))
            for _ in range(100):
                if children:
                    break
                await asyncio.sleep(.01)
            self.assertTrue(children)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(children[0].returncode)
        self.assertFalse(directories[0].exists())


@unittest.skipUnless(AVAILABLE, 'Install sandbox dependencies for real MCP checks')
class FeedbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_mcp_error_returned_to_model_then_corrected_with_two_approvals(self):
        from mcp_tools.config import load_config
        from mcp_tools.gateway import connect
        from mcp_tools.runner import tool_loop
        calls, approvals = [], []
        def tool(source):
            return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
                'name': 'python__execute_python', 'arguments': {'code': source}}}]}
        async def model(host, model, messages, definitions, timeout):
            calls.append(messages[:])
            if len(calls) == 1:
                return tool('print(1 / 0)')
            if len(calls) == 2:
                self.assertIn('ZeroDivisionError', messages[-1]['content'])
                return {'role': 'assistant', 'content': 'I fixed it; it prints 42.'}
            if len(calls) == 3:
                self.assertIn('No corrected program', messages[-1]['content'])
                return tool('print(6 * 7)')
            observed = json.loads(messages[-1]['content'])['structuredContent']
            self.assertEqual(observed['stdout'], '42\n')
            self.assertEqual(observed['exit_code'], 0)
            return {'role': 'assistant', 'content': 'The corrected program printed 42.'}
        def approve(name, args):
            approvals.append(args['code'])
            return True
        async with connect(load_config(ROOT / 'configs/mcp.sandbox.json')) as gateway:
            result = await tool_loop(gateway, [], 'unused', 'fake-model', 10,
                                     approve=approve, request=model)
        self.assertEqual(len(result.evidence), 2)
        self.assertEqual(approvals, ['print(1 / 0)', 'print(6 * 7)'])

    async def test_failed_execution_cannot_be_reported_as_success_without_repair(self):
        from mcp_tools.config import load_config, McpError
        from mcp_tools.gateway import connect
        from mcp_tools.runner import tool_loop
        count = 0
        async def model(*args):
            nonlocal count
            count += 1
            if count == 1:
                return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
                    'name': 'python__execute_python', 'arguments': {'code': 'print(1/0)'}}}]}
            return {'role': 'assistant', 'content': 'Successfully executed the corrected code!'}
        async with connect(load_config(ROOT / 'configs/mcp.sandbox.json')) as gateway:
            with self.assertRaisesRegex(McpError, 'did not verify'):
                await tool_loop(gateway, [], 'unused', 'fake', 10, approve=lambda *a: True, request=model)
        self.assertEqual(count, 3)

    async def test_rejection_prevents_execution_and_call_limit_stops_repairs(self):
        from mcp_tools.config import load_config, McpError
        from mcp_tools.gateway import connect
        from mcp_tools.runner import tool_loop
        async def model(*args):
            return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {
                'name': 'python__execute_python', 'arguments': {'code': 'print(1/0)'}}}]}
        async with connect(load_config(ROOT / 'configs/mcp.sandbox.json')) as gateway:
            with patch.object(gateway, 'call', wraps=gateway.call) as execute:
                with self.assertRaisesRegex(McpError, 'rejected'):
                    await tool_loop(gateway, [], 'unused', 'fake', 10, approve=lambda *a: False, request=model)
                execute.assert_not_called()
                with self.assertRaisesRegex(McpError, 'limit'):
                    await tool_loop(gateway, [], 'unused', 'fake', 10, max_calls=2,
                                    approve=lambda *a: True, request=model)
                self.assertEqual(execute.await_count, 2)
