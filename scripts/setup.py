"""Generate local secrets without printing them or storing the admin password."""
import getpass
import hashlib
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]


def main():
    destination = ROOT / '.env'
    if destination.exists():
        raise SystemExit('.env already exists; existing credentials were preserved.')
    print('Password input is hidden: no characters will appear while you type.')
    while True:
        password = getpass.getpass('Choose administrator password (at least 16 characters): ')
        if len(password) < 16:
            print('Password must contain at least 16 characters. Please try again.')
            continue
        if password != getpass.getpass('Repeat administrator password: '):
            print('Passwords did not match. Please try again.')
            continue
        break
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
    values = {'POSTGRES_PASSWORD': secrets.token_hex(24), 'ADMIN_PASSWORD_HASH': f'{salt.hex()}:{digest}', 'SESSION_SECRET': secrets.token_hex(32), 'FIXTURE_PASSWORD': secrets.token_hex(24)}
    with destination.open('x', encoding='utf-8') as file:
        file.write(''.join(f'{key}={value}\n' for key, value in values.items()))
    destination.chmod(0o600)
    print('Created .env. Sign in as admin using the password you chose. No password was printed.')


if __name__ == '__main__':
    main()
