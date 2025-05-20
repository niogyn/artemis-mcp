import argparse
import json
import os
import subprocess
from pathlib import Path


def find_package_json(start: Path) -> Path | None:
    current = start
    while True:
        candidate = current / "package.json"
        if candidate.exists():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def build_framework() -> None:
    print("MCP Build Script Starting...")
    print("Finding project root...")
    start_dir = Path.cwd()
    print(f"Starting search from: {start_dir}")

    pkg_path = find_package_json(start_dir)
    if not pkg_path:
        raise RuntimeError("Could not find package.json in current directory or any parent directories")

    project_root = pkg_path.parent
    skip_validation = os.environ.get("MCP_SKIP_VALIDATION") == "true"
    if skip_validation:
        print("Skipping dependency validation")
    else:
        pkg = json.loads(pkg_path.read_text())
        if "mcp-framework" not in pkg.get("dependencies", {}):
            raise RuntimeError("This directory is not an MCP project (mcp-framework not found in dependencies)")

    print(f"Running tsc in {project_root}")
    cmd = ["npx", "tsc"] if os.name != "nt" else ["npx.cmd", "tsc"]
    subprocess.check_call(cmd, cwd=project_root)

    dist_path = project_root / "dist"
    index_path = dist_path / "index.js"
    shebang = "#!/usr/bin/env node\n"
    if index_path.exists():
        content = index_path.read_text()
        if not content.startswith(shebang):
            index_path.write_text(shebang + content)
    print("Build completed successfully!")


def create_project(name: str | None, http: bool = False, cors: bool = False, port: int = 8080,
                    install: bool = True, example: bool = True) -> None:
    if not name:
        name = input("Project name: ").strip()
    if not name:
        raise RuntimeError("Project name is required")

    project_dir = Path.cwd() / name
    src_dir = project_dir / "src"
    tools_dir = src_dir / "tools"
    prompts_dir = src_dir / "prompts"
    resources_dir = src_dir / "resources"

    project_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(exist_ok=True)
    tools_dir.mkdir(exist_ok=True)
    prompts_dir.mkdir(exist_ok=True)
    resources_dir.mkdir(exist_ok=True)

    package_json = {
        "name": name,
        "version": "0.0.1",
        "description": f"{name} MCP server",
        "type": "module",
        "bin": {name: "./dist/index.js"},
        "files": ["dist"],
        "scripts": {
            "build": "tsc && mcp-build",
            "watch": "tsc --watch",
            "start": "node dist/index.js"
        },
        "dependencies": {"mcp-framework": "^0.2.2"},
        "devDependencies": {"@types/node": "^20.11.24", "typescript": "^5.3.3"},
        "engines": {"node": ">=18.19.0"}
    }

    tsconfig = {
        "compilerOptions": {
            "target": "ESNext",
            "module": "ESNext",
            "moduleResolution": "node",
            "outDir": "./dist",
            "rootDir": "./src",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True
        },
        "include": ["src/**/*"],
        "exclude": ["node_modules"]
    }

    if http:
        transport_config = f"\n  transport: {{\n    type: 'http-stream',\n    options: {{\n      port: {port}"
        if cors:
            transport_config += ",\n      cors: {\n        allowOrigin: '*'\n      }"
        transport_config += "\n    }\n  }"
        index_ts = f"import {{ MCPServer }} from 'mcp-framework';\n\nconst server = new MCPServer({{{transport_config}}});\n\nserver.start();\n"
    else:
        index_ts = "import { MCPServer } from 'mcp-framework';\n\nconst server = new MCPServer();\n\nserver.start();\n"

    files = [
        (project_dir / "package.json", json.dumps(package_json, indent=2)),
        (project_dir / "tsconfig.json", json.dumps(tsconfig, indent=2)),
        (project_dir / "README.md", f"# {name}\n\nCreated with mcp-framework"),
        (src_dir / "index.ts", index_ts)
    ]

    if example:
        example_tool = (
            tools_dir / "ExampleTool.ts",
            "import { MCPTool } from 'mcp-framework';\n"
            "import { z } from 'zod';\n\n"
            "interface ExampleInput {\n  message: string;\n}\n\n"
            "class ExampleTool extends MCPTool<ExampleInput> {\n"
            "  name = 'example_tool';\n"
            "  description = 'An example tool that processes messages';\n\n"
            "  schema = {\n"
            "    message: {\n"
            "      type: z.string(),\n"
            "      description: 'Message to process'\n"
            "    }\n"
            "  };\n\n"
            "  async execute(input: ExampleInput) {\n"
            "    return `Processed: ${input.message}`;\n"
            "  }\n"
            "}\n\nexport default ExampleTool;\n"
        )
        files.append(example_tool)

    for path, content in files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    os.chdir(project_dir)
    subprocess.check_call(["git", "init"])

    if install:
        subprocess.check_call(["npm", "install"])
        subprocess.check_call(["npx", "tsc"], cwd=project_dir)
        env = os.environ.copy()
        env["MCP_SKIP_VALIDATION"] = "true"
        subprocess.check_call(["npx", "mcp-build"], cwd=project_dir, env=env)
        print(f"Project {name} created and built successfully!")
    else:
        print(f"Project {name} created successfully (without dependencies)!")


def to_pascal_case(value: str) -> str:
    return ''.join(word.capitalize() for word in value.replace('_', '-').split('-'))


def add_component(name: str | None, kind: str) -> None:
    pkg = find_package_json(Path.cwd())
    if not pkg:
        raise RuntimeError("Must be run from an MCP project directory")
    if not name:
        name = input(f"{kind.capitalize()} name: ").strip()
    if not name:
        raise RuntimeError(f"{kind.capitalize()} name is required")

    class_name = to_pascal_case(name)
    file_name = f"{class_name}{kind.capitalize()}.ts"
    dir_map = {
        'tool': Path.cwd() / 'src/tools',
        'prompt': Path.cwd() / 'src/prompts',
        'resource': Path.cwd() / 'src/resources'
    }
    content_map = {
        'tool': f"import {{ MCPTool }} from 'mcp-framework';\nimport {{ z }} from 'zod';\n\ninterface {class_name}Input {{\n  message: string;\n}}\n\nclass {class_name}Tool extends MCPTool<{class_name}Input> {{\n  name = '{name}';\n  description = '{class_name} tool description';\n\n  schema = {{\n    message: {{\n      type: z.string(),\n      description: 'Message to process'\n    }}\n  }};\n\n  async execute(input: {class_name}Input) {{\n    return `Processed: ${input.message}`;\n  }}\n}}\n\nexport default {class_name}Tool;\n",
        'prompt': f"import {{ MCPPrompt }} from 'mcp-framework';\nimport {{ z }} from 'zod';\n\ninterface {class_name}Input {{\n  message: string;\n}}\n\nclass {class_name}Prompt extends MCPPrompt<{class_name}Input> {{\n  name = '{name}';\n  description = '{class_name} prompt description';\n\n  schema = {{\n    message: {{\n      type: z.string(),\n      description: 'Message to process',\n      required: true\n    }}\n  }};\n\n  async generateMessages({{ message }}: {class_name}Input) {{\n    return [{{ role: 'user', content: {{ type: 'text', text: message }} }}];\n  }}\n}}\n\nexport default {class_name}Prompt;\n",
        'resource': f"import {{ MCPResource, ResourceContent }} from 'mcp-framework';\n\nclass {class_name}Resource extends MCPResource {{\n  uri = 'resource://{name}';\n  name = '{class_name}';\n  description = '{class_name} resource description';\n  mimeType = 'application/json';\n\n  async read(): Promise<ResourceContent[]> {{\n    return [{{ uri: this.uri, mimeType: this.mimeType, text: JSON.stringify({{ message: 'Hello from {class_name} resource' }}) }}];\n  }}\n}}\n\nexport default {class_name}Resource;\n"
    }
    target_dir = dir_map[kind]
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / file_name
    file_path.write_text(content_map[kind])
    print(f"{kind.capitalize()} {name} created at {file_path.relative_to(Path.cwd())}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog='mcp', description='CLI for managing MCP server projects')
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('build', help='Build the MCP project')

    create_parser = subparsers.add_parser('create', help='Create a new MCP server project')
    create_parser.add_argument('name', nargs='?')
    create_parser.add_argument('--http', action='store_true')
    create_parser.add_argument('--cors', action='store_true')
    create_parser.add_argument('--port', type=int, default=8080)
    create_parser.add_argument('--no-install', dest='install', action='store_false')
    create_parser.add_argument('--no-example', dest='example', action='store_false')

    add_parser = subparsers.add_parser('add', help='Add a new component')
    add_sub = add_parser.add_subparsers(dest='add_command')
    for kind in ('tool', 'prompt', 'resource'):
        p = add_sub.add_parser(kind)
        p.add_argument('name', nargs='?')

    args = parser.parse_args(argv)

    if args.command == 'build':
        build_framework()
    elif args.command == 'create':
        create_project(args.name, args.http, args.cors, args.port, args.install, args.example)
    elif args.command == 'add':
        if args.add_command:
            add_component(args.name, args.add_command)
        else:
            parser.error('add requires a subcommand (tool, prompt, resource)')
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
