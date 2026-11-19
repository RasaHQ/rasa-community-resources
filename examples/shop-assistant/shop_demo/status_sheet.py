"""Read Sheet metadata in its locked server runtime, without printing data."""
from __future__ import annotations

from .google_runtime import google_service
from .setup_sheet import SheetSettings, Spreadsheet, content


def check(settings, service):
    # No prepare(), values, append, update, seed, model or Telegram call.
    Spreadsheet.model_validate(content(service.get_spreadsheet(settings.spreadsheet_id)))


def main():
    service = None
    try:
        settings = SheetSettings.environment()
        service = google_service(settings.token)
        check(settings, service)
        return 0
    except Exception:
        return 1
    finally:
        if service is not None:
            connection = getattr(service, 'sheets_service', None)
            if connection is not None:
                connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
