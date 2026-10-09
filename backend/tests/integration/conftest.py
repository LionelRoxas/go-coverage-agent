# AI-generated with Claude Code from a human-approved spec and plan; each task independently AI-reviewed; integrated and verified by Lionel Derrick Roxas.
from pathlib import Path

import pytest

from app.config import Settings
from app.gotools import GoTools
from app.workspace import Workspace

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def make_ws(tmp_path):
    def _make(name: str = "gomod") -> Workspace:
        return Workspace.create(tmp_path / "work", "job", FIXTURES / name)
    return _make


@pytest.fixture
def tools_for(settings):
    def _tools(ws: Workspace) -> GoTools:
        return GoTools(ws.root, settings)
    return _tools
