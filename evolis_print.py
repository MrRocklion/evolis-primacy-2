import evolis
from evolis import State, RibbonType, ReturnCode, CardFace, InputTray, OutputTray
from pathlib import Path


def print_card(
    printer_name: str,
    front_bmp_path: str,
) -> tuple[bool, str]:
    """
    Print the front face of a card on an Evolis Primacy 2.

    Parameters
    ----------
    printer_name : str
        Exact printer name as registered in the OS (e.g. "Evolis Primacy 2").
    front_bmp_path : str
        Path to the front face BMP file (1016x648 px, 300 dpi).

    Returns
    -------
    tuple[bool, str]
        (success, message) — True if print succeeded, False otherwise.
    """

    # ── Validate file ──────────────────────────────────────────────
    bmp = Path(front_bmp_path)
    if not bmp.exists():
        return False, f"BMP file not found: {bmp.resolve()}"

    # ── Open connection ────────────────────────────────────────────
    co = evolis.Connection(printer_name)

    try:
        # ── Check printer state ────────────────────────────────────
        state = co.get_state()
        if state.major != State.Major.READY:
            return False, f"Printer not ready — state: {state.major} / {state.minor}"

        # ── Tray configuration ─────────────────────────────────────
        co.set_input_tray(InputTray.FEEDER)
        co.set_output_tray(OutputTray.STANDARD)
        co.set_error_tray(OutputTray.ERROR)

        # ── Print session (front only) ─────────────────────────────
        ps = evolis.PrintSession(co, RibbonType.YMCKO)

        if not ps.set_image(CardFace.FRONT, str(bmp)):
            return False, f"Failed to load BMP: {bmp}"

        # ── Execute print ──────────────────────────────────────────
        result = ps.print()

        if result != ReturnCode.OK:
            state = co.get_state()
            return False, f"Print failed [{result}] — state: {state.major} / {state.minor}"

        return True, "Card printed successfully."

    finally:
        co.close()