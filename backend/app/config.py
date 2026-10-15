import json
import os
from pathlib import Path


def _load_env_file():
    # Process managers (PM2, systemd) often start without the deployment .env.
    # Load it once; values already present in the environment take priority.
    for folder in Path(__file__).resolve().parents:
        candidate = folder / '.env'
        if candidate.is_file():
            for raw in candidate.read_text(encoding='utf-8').splitlines():
                line = raw.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key, value = key.strip(), value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                    value = value[1:-1]
                os.environ.setdefault(key, value)
            return


_load_env_file()


import urllib.parse


def database_url():
    if 'POSTGRES_PASSWORD' in os.environ and '@db' in os.environ.get('DATABASE_URL', ''):
        pwd = urllib.parse.quote_plus(os.environ['POSTGRES_PASSWORD'])
        return f"postgresql+psycopg://dynaguard:{pwd}@db:5432/dynaguard"
    raw = os.environ.get('DATABASE_URL', 'sqlite:///./dynaguard.db')
    if raw.startswith('postgresql') and '@' in raw:
        try:
            proto, rest = raw.split('://', 1)
            up, host_part = rest.rsplit('@', 1)
            if ':' in up:
                user, p = up.split(':', 1)
                return f"{proto}://{user}:{urllib.parse.quote_plus(urllib.parse.unquote_plus(p))}@{host_part}"
        except Exception:
            pass
    return raw


def targets():
    # Deployment-owned registry. Dashboard input can select, never extend it.
    return json.loads(os.environ.get('TARGETS_JSON', '{"http://127.0.0.1:8101":["127.0.0.1"],"http://127.0.0.1:8102":["127.0.0.1"]}'))


TEST_ID = 'ownership.designated-record'
TEST_VERSION = '1.0.0'
TERMINAL = {'completed', 'incomplete', 'cancelled'}
