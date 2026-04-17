import subprocess
from .spinner import Spinner
from ..utils import colors

import time
import subprocess

def run_command_output(cmd, ignore_errors=False):

    try:
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stdout.strip()  # restituisce solo l'output, senza spazi finali
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
            spinner.stop("DONE", color="yellow")
            return True

        except subprocess.CalledProcessError as e:
            # Exit code ignorato
            if ignore_exit_codes and e.returncode in ignore_exit_codes:
                spinner.stop("WARNING", color="yellow", width=80)
                return True

            # Se non è l'ultimo tentativo → retry
            if attempt < retries:
                spinner.stop("RETRY", color="yellow", width=80)
                time.sleep(delay)
                attempt += 1
                continue

            if ignore_errors:
                spinner.stop("WARNING", color="green")
                print(f"{colors.GREEN}A command failed but was ignored as non-critical{colors.RESET}\n")
            else:
                spinner.stop("ERROR", color="red")
                print(f"{colors.RED}Execution of '{' '.join(cmd)}' returned {e.returncode}{colors.RESET}")
                if e.stdout:
                    print(f"Output:\n{e.stdout}")
                if e.stderr:
                    print(f"Error:\n{e.stderr}")

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