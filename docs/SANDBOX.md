# T2 — sandboxed Python execution and correction

The model calls `python__execute_python` over real MCP. Sensai shows the source
and asks for approval before each execution, including corrected attempts.
The tool returns stdout, stderr/traceback, exit code and limits. These observations
go back to Ollama, which can submit a corrected program. The same loop works in
CLI and web MCP mode. No framework invokes the model: calls use Ollama HTTP.

## Install once (Ubuntu / WSL)

Open an Ubuntu terminal, then run each command separately:

```bash
cd ~/G-AIA-500-BAR-5-1-sensai-2
source .venv/bin/activate
sudo apt update
sudo apt install bubblewrap libseccomp2 python3
python -m pip install -r requirements-mcp.txt
python -m sandbox
ollama pull qwen3:0.6b
```

The check must print `"status": "ok"` and `Sensai sandbox ready`. If it fails,
stop and fix the reported dependency or namespace error. Sensai never falls back
to executing generated code on the host. Do not disable system security settings
to work around an isolation failure. This runtime supports Linux/WSL, not native
Windows or macOS. Docker is not required: T2 permits an isolated subprocess.

On the development machine Bubblewrap 0.9.0 was installed without sudo by
downloading the Ubuntu package and extracting it into
`~/.cache/sensai-sandbox/runtime`; the runner also recognizes that location.
Other machines should use the `apt install` commands above.

## CLI demonstration

```bash
python chatbot.py --model qwen3:0.6b --mcp-config configs/mcp.sandbox.json --guardrails guardrails/demo.json
```

At `You>`, enter one line at a time:

```text
/tools
/mcp Use python__execute_python to calculate and print the sum of squares of integers from 1 to 10. Report the actual stdout.
```

Check the displayed Python program. Enter `yes` only at the approval prompt.
The tool should return stdout `385` with exit code 0. A final answer without a
tool-result record does not demonstrate execution.

Then enter `/clear`, wait for `You>`, and demonstrate correction:

```text
/mcp Use python__execute_python. First run exactly: values = [10, 20, 30]; print(sum(values) / len(value)). This typo is intentional. After receiving the traceback, fix the variable-name typo and execute the corrected program. Report its actual stdout.
```

Approve the first call: expect `NameError` and nonzero exit code. Approve the
corrected call separately: expect `20.0` and exit code 0. The first error is
intentional. The displayed result, not the model's claim, is the evidence.

For rejection, repeat a request and answer `no`: no Python call should run.
For interruption, request `import time; time.sleep(30)` and press Ctrl+C after
approving. The current turn must not be saved as a completed answer.

## Web demonstration

Stop your existing web server with Ctrl+C, then start it from the same project
directory and active virtual environment:

```bash
export SENSAI_MCP_CONFIG=configs/mcp.sandbox.json
export SENSAI_GUARDRAILS=guardrails/demo.json
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000, select **MCP**, enter model **qwen3:0.6b**, and click
**Clear**. Send the same requests without the `/mcp` prefix. Approve each program
using its card. Expand tool-result cards to inspect `stdout`, `stderr`,
`exit_code`, and `status`. A failed first program is shown as a tool error; the
successful corrected execution has its own result card. Reject and Stop remain
available. The sandbox config enables only the Python tool; `mcp.demo.json`
continues to enable the project and time tools. An operator can combine their
server entries in one config (up to four servers).

## Isolation and limits

- A fresh Bubblewrap user/mount/PID/network namespace per call; no host home,
  project directory, Windows drives, host `/tmp`, `/proc`, or service sockets.
- Only the system Python binary, system libraries, `/dev/null` and read-only
  source/bootstrap files are mounted. The root is read-only. No file writes or
  persisted artifacts; values must be returned with `print()`.
- Empty environment apart from fixed locale/path/home values. All capabilities
  dropped. Further user namespaces are disabled.
- Before user code, hard limits: 256 MiB address space, 2 CPU seconds, no core
  dumps or file growth, 32 descriptors. A default-deny seccomp syscall filter
  permits basic Python work; process creation/exec, sockets and mounts are denied.
- Parent enforces 5 wall seconds and 4 KiB combined stdout/stderr. It kills the
  sandbox on limit or cancellation and removes temporary source files. Bubblewrap
  also terminates sandbox processes if its parent dies.
- Default MCP budget: four tool calls (initial execution plus at most three
  corrections). One extra model request can remind it to actually execute a
  repair after failure. Repeated prose-only claims after a failed Python execution
  produce an explicit error, not a successful answer.

Standard library only; no package installation, network, plotting GUI, threads
or subprocesses. Namespace isolation shares the host kernel; this is a local
educational runtime, not a multi-tenant service. Tool output remains untrusted
and passes the configured guardrails before model context or display.

Implementation: `sandbox/runner.py` (lifecycle), `sandbox/bootstrap.py` (limits
and seccomp), `mcp_tools/python_server.py` (MCP), `mcp_tools/runner.py` (feedback
and bounded repair), existing `mcp_tools/web.py` (approval/Stop).
Isolation options follow the [Bubblewrap manual](https://manpages.ubuntu.com/manpages/noble/man1/bwrap.1.html)
and [upstream documentation](https://github.com/containers/bubblewrap).

## Verification

```bash
python -m pytest tests/test_sandbox.py tests/test_mcp_web.py -q
```

Real isolation checks exercise host-file/environment protection, direct syscall
attempts, filesystem writes, network/process denial, CPU/memory/wall/output limits
and cancellation cleanup. Real stdio MCP + deterministic model tests check
traceback feedback, corrected execution, repeated approvals, refusal and call
limits. Web API/SSE tests exercise a real sandbox with two approvals and Stop.
These tests skip real sandbox cases if Bubblewrap is absent; the smoke check
above must pass before claiming T2 works on another machine.

Live validation on 1 November 2026: qwen3:0.6b via local Ollama called the tool,
received `NameError` for `len(value)`, submitted `len(values)`, executed it and
reported the observed `20.0`. Both programs ran in real Bubblewrap namespaces.
The verification harness approved these known demo programs; normal CLI/web
flows require the human's separate approval. Model repair is not guaranteed for
arbitrary problems; failures remain explicit and attempts bounded.
