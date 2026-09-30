"""Locate archived source without requiring it in a fresh public checkout."""
import os
from pathlib import Path
import re
import subprocess
import unittest


def history_repository(root, revisions):
    override = os.environ.get('EXEC816_HISTORY_REPO')
    repository = Path(override).expanduser().resolve() if override else root
    for revision in set(revisions):
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise RuntimeError('Invalid historical revision: ' + revision)
        result = subprocess.run(
            ['git', 'cat-file', '-e', revision + '^{commit}'],
            cwd=repository, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode:
            reason = 'Historical commit is unavailable: ' + revision
            if override:
                raise RuntimeError(reason + ' in EXEC816_HISTORY_REPO')
            raise unittest.SkipTest(
                reason + '; set EXEC816_HISTORY_REPO to the development archive')
    return repository
