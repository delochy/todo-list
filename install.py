#!/usr/bin/env python3
"""Install/update the skill, preserving a rollback copy. No network or dependencies."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile
import time

FILES = ('SKILL.md', 'agents/openai.yaml', 'scripts/board.py', 'scripts/core.py',
         'scripts/webserver.py', 'scripts/live_review.py', 'assets/board.html', 'assets/board.css', 'assets/board.js', 'assets/locales.json')

def install(destination):
    source = Path(__file__).resolve().parent / 'skill' / 'todo-list'
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.todo-list-install-', dir=destination.parent))
    backup = None
    try:
        for relative in FILES:
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        if destination.exists():
            backups = destination.parent / '.todo-list-backups'
            backups.mkdir(exist_ok=True)
            backup = backups / (time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns()))
            destination.rename(backup)
        try:
            stage.rename(destination)
        except OSError:
            if backup: backup.rename(destination)
            raise
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return destination, backup

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path,
                        default=Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))/'skills'/'todo-list')
    args = parser.parse_args()
    destination, backup = install(args.destination)
    print('Installed:', destination)
    if backup: print('Rollback copy:', backup)
