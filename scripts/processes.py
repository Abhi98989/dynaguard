"""Terminate only process trees launched by the local development/test supervisor."""
import os
import signal
import subprocess


def launch_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}


def stop_owned(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        # Windows virtualenv launchers and Next may create children. Terminating only
        # the wrapper leaks servers and keeps database/log files locked.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
