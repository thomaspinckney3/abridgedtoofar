"""Build runtime resources from their single authoritative repository sources."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithResources(build_py):
    def run(self):
        super().run()
        root = Path(__file__).parent
        for folder in ("prompts", "spec"):
            for source in (root / folder).glob("*.md"):
                target = Path(self.build_lib) / "forage" / "_resources" / folder / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)


setup(cmdclass={"build_py": BuildWithResources})
