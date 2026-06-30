# Forwarding module to expose src.taskmesh.api.main as taskmesh.main
from src.taskmesh.api.main import app

__all__ = ["app"]
