import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtWidgets import QApplication, QMessageBox

from .ui.main_window import MainWindow


def _load_dotenv_near_package() -> None:
    here = Path(__file__).resolve().parent
    for d in [here, *here.parents]:
        candidate = d / ".env"
        if candidate.is_file():
            load_dotenv(candidate)
            return
    load_dotenv()


def _install_exception_hook() -> None:
    def hook(exc_type, exc, tb) -> None:
        message = "".join(traceback.format_exception(exc_type, exc, tb))
        print(message, file=sys.stderr)
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(None, "Unhandled error", message)
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> None:
    _load_dotenv_near_package()
    _install_exception_hook()
    app = QApplication(sys.argv)
    app.setApplicationName("Form Reader Comparator")
    app.setOrganizationName("Digidoocs")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
