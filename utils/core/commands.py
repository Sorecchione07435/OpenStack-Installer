import subprocess
from .spinner import Spinner
from ..core import colors

import time
import subprocess

def run_command_output(cmd, ignore_errors=False):

    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if ignore_errors:
            return e.stdout.strip() if e.stdout else ""
        else:
            raise

def run_command_sync(command):
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def run_command(
    cmd,
    message="",
    ignore_errors=False,
    ignore_exit_codes=None,
    retries=0,
    delay=1
):

    attempt = 0

    while attempt <= retries:
        spinner = Spinner(f"{message}")
        spinner.start()

        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            spinner.stop("DONE", color="yellow", width=60)
            return True

        except subprocess.CalledProcessError as e:
            # Exit code ignorato
            if ignore_exit_codes and e.returncode in ignore_exit_codes:
                spinner.stop("WARNING", color="yellow", width=60)
                return True

            # Se non è l'ultimo tentativo → retry
            if attempt < retries:
                spinner.stop("RETRY", color="yellow", width=60)
                time.sleep(delay)
                attempt += 1
                continue

            if ignore_errors:
                spinner.stop("WARNING", color="green", width=60)
                print(f"{colors.GREEN}A command failed but was ignored as non-critical{colors.RESET}")
            else:

                combined_output = ""
                if e.stdout:
                    combined_output += e.stdout
                if e.stderr:
                    combined_output += ("\n" + e.stderr if combined_output else e.stderr)

                spinner.stop("ERROR", color="red", width=60)
                print(f"\n{colors.RED}Execution of command '{' '.join(cmd)}' failed with non-zero exit code: {e.returncode}{colors.RESET}")
                if combined_output:
                    print("\nCommand Last Output:")
                    print(combined_output)
                return False

            return False

    return False

def run_sync_command_with_retry(
    command,
    max_retries=3,
    interval=1
):
    for attempt in range(max_retries):
        success = run_command_sync(
            command
        )

        if success:
            return True

        if attempt < max_retries - 1:
            time.sleep(interval)

    return False