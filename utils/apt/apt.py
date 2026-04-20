import subprocess
from ..core.spinner import Spinner
from ..core import colors

def run_command(command, message="Processing", width=50):

    spinner = Spinner(message)
    spinner.start()

    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True 
        )
    except subprocess.CalledProcessError as e:
        spinner.stop("ERROR", color="red", width=60)
        combined_output = ""
        if e.stdout:
            combined_output += e.stdout
        if e.stderr:
            combined_output += ("\n" + e.stderr if combined_output else e.stderr)

        print(f"\n{colors.RED}Execution of command '{' '.join(command)}' failed with non-zero exit code: {e.returncode}{colors.RESET}")
        if combined_output:
            print("\nCommand Last Output:")
            print(combined_output)
        return False

    spinner.stop("DONE", color="yellow", width=60)
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

    cmd = ["apt", "install", "-y"] + packages

    success = run_command(cmd, message)
    return success