from pathlib import Path


class IndexingAgent:

    def __init__(self):
        self.ignored_directories = {
            ".git",
            ".venv",
            "venv",
            "agent",
            "__pycache__",
            "node_modules",
            ".idea",
            ".vscode"
        }

    def index_project(self, project_path: str):
        project = Path(project_path)

        if not project.exists():
            raise FileNotFoundError("Project path does not exist")

        if not project.is_dir():
            raise ValueError("Project path is not a directory")

        files = []

        for file in project.rglob("*"):

            if not file.is_file():
                continue

            if any(
                directory in self.ignored_directories
                for directory in file.parts
            ):
                continue

            files.append({
                "path": str(file.relative_to(project)),
                "extension": file.suffix,
                "size": file.stat().st_size
            })

        return {
            "project_name": project.name,
            "file_count": len(files),
            "files": files
        }
    