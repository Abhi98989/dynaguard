"""Automatic stack detection across project trees and monorepos."""
from pathlib import Path
from typing import Set

EXCLUDE_DIRS = {'.git', '.venv', 'venv', 'node_modules', '.next', 'build', 'dist', '__pycache__', '.dart_tool', '.idea'}

STACK_MARKERS = {
    'laravel': [
        'artisan',
        'composer.json',
    ],
    'node': [
        'package.json',
        'package-lock.json',
        'yarn.lock',
        'pnpm-lock.yaml',
    ],
    'nextjs': [
        'next.config.js',
        'next.config.mjs',
        'next.config.ts',
    ],
    'python': [
        'requirements.txt',
        'pyproject.toml',
        'setup.py',
        'Pipfile',
        'manage.py',
    ],
    'flutter': [
        'pubspec.yaml',
        'pubspec.lock',
    ],
    'database': [
        'schema.sql',
        'alembic.ini',
    ],
    'firebase': [
        'firestore.rules',
        'firebase.json',
        'storage.rules',
    ],
    'docker': [
        'Dockerfile',
        'docker-compose.yml',
        'docker-compose.yaml',
        'compose.yml',
        'compose.yaml',
    ]
}


def detect_stacks(root_path: Path | str) -> Set[str]:
    root = Path(root_path).resolve()
    if not root.is_dir():
        return set()

    detected = set()

    # Quick inspection of root and up to 3 directory levels deep
    for current, dirs, files in Path(root).walk():
        # filter out excluded dirs
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not (Path(current) / d).is_symlink()]
        
        file_set = set(files)
        
        # Check specific markers
        if 'artisan' in file_set:
            detected.add('laravel')
        if 'composer.json' in file_set:
            try:
                content = (Path(current) / 'composer.json').read_text(encoding='utf-8', errors='ignore')
                if 'laravel/framework' in content:
                    detected.add('laravel')
                else:
                    detected.add('php')
            except Exception:
                detected.add('php')

        if 'package.json' in file_set:
            detected.add('node')
            try:
                content = (Path(current) / 'package.json').read_text(encoding='utf-8', errors='ignore')
                if '"next"' in content:
                    detected.add('nextjs')
                if '"react"' in content:
                    detected.add('react')
                if '"express"' in content or '"@nestjs/' in content or '"koa"' in content or '"fastify"' in content:
                    detected.add('node_backend')
            except Exception:
                pass

        if any(f in file_set for f in ('next.config.js', 'next.config.mjs', 'next.config.ts')):
            detected.add('nextjs')

        if any(f in file_set for f in ('requirements.txt', 'pyproject.toml', 'manage.py', 'setup.py')):
            detected.add('python')

        if 'pubspec.yaml' in file_set:
            detected.add('flutter')

        if any(f in file_set for f in ('firestore.rules', 'firebase.json')):
            detected.add('firebase')

        if any(f in file_set for f in ('docker-compose.yml', 'docker-compose.yaml', 'compose.yml', 'compose.yaml', 'Dockerfile')):
            detected.add('docker')

        if any(f.endswith('.sql') for f in file_set) or 'migrations' in dirs:
            detected.add('database')

    return detected
