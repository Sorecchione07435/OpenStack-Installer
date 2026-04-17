import subprocess
from ..core.spinner import Spinner
from ..utils import colors

def run_command(command, message="Processing", width=60):

    spinner = Spinner(message)
    spinner.start()

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,  # cattura stdout
            stderr=subprocess.PIPE,  # cattura stderr
            text=True                # output in stringa
        )
    except subprocess.CalledProcessError as e:
        spinner.stop("ERROR", color="red", width=width)
        combined_output = ""
        if e.stdout:
            combined_output += e.stdout
        if e.stderr:
            combined_output += ("\n" + e.stderr if combined_output else e.stderr)

        print(f"\n{colors.RED}Execution of command '{' '.join(command)}' failed with non-zero exit code: {e.returncode}{colors.RESET}")
        if combined_output:
            print("\nCommand Last Output:\n")
            print(combined_output)
        return False

    spinner.stop("DONE", color="yellow", width=80)
    return True


def apt_update():
    return run_command(["sudo", "apt", "update"], "Updating the system repos...")


def apt_install(packages, ux_text=None):
    # Assicuriamoci di avere sempre una lista
    if isinstance(packages, str):
        packages = [packages]

    if ux_text is None:
        message = f"Installing packages: {', '.join(packages)}"
    else:
        message = ux_text

    cmd = ["sudo", "apt", "install", "-y"] + packages

    success = run_command(cmd, message)
    return success