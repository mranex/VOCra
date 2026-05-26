import sys
import os


def _configure_qt_multimedia() -> None:
    # VoCRA targets subtitle-heavy videos, including AV1 sources. Keep Qt on the
    # FFmpeg backend for codec coverage, but force software decoding to avoid
    # broken d3d11 AV1 hardware init on some Windows machines.
    os.environ["QT_FFMPEG_DECODING_HW_DEVICE_TYPES"] = ","
    os.environ["QT_DISABLE_HW_TEXTURES_CONVERSION"] = "1"
    os.environ["QT_MEDIA_BACKEND"] = "ffmpeg"


def main() -> int:
    _configure_qt_multimedia()
    from vocra_gui.main_window import run_app

    return run_app(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
