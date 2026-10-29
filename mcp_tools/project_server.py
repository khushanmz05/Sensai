"""Sensai's custom read-only MCP server. Run with an explicit workspace root."""
import argparse

from mcp.server.fastmcp import FastMCP
from file_access.reader import WorkspaceReader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    args = parser.parse_args()
    with WorkspaceReader(args.workspace) as reader:
        server = FastMCP('sensai-project')

        @server.tool()
        def read_project_file(relative_path: str) -> str:
            """Read a UTF-8 project file beneath the configured workspace. Use project_notes.md for demo notes."""
            return reader.read_text(relative_path).content

        server.run(transport='stdio')


if __name__ == '__main__':
    main()
