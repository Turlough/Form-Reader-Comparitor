import sys
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox

from .ui.main_window import MainWindow


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
    _install_exception_hook()
    app = QApplication(sys.argv)
    app.setApplicationName("Form Reader Comparator")
    app.setOrganizationName("Digidoocs")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
