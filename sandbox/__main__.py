"""Run a real smoke check: python -m sandbox."""
import asyncio
import json
from .runner import run_python, SandboxError


def main():
    try:
        result = asyncio.run(run_python('print("Sensai sandbox ready")'))
    except SandboxError as error:
        print(str(error))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'ok' and result['stdout'] == 'Sensai sandbox ready\n' else 1


if __name__ == '__main__':
    raise SystemExit(main())
