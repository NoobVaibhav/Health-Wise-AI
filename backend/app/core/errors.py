"""Typed errors for the report pipeline. Each one carries an HTTP status and a
user-friendly message, so the frontend can show something useful (never a bare 'Failed to fetch')."""


class ReportError(Exception):
    status_code = 422
    code = "REPORT_ERROR"
    message = "The report could not be processed."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message


class UnsupportedFileError(ReportError):
    status_code = 415
    code = "UNSUPPORTED_FILE"
    message = "Wrong file uploaded. This file type is not accepted. Please upload a medical report as a PDF, JPG, JPEG, PNG or WEBP file."


class FileTooLargeError(ReportError):
    status_code = 413
    code = "FILE_TOO_LARGE"
    message = "The file is too large."


class UnreadableReportError(ReportError):
    code = "UNREADABLE_REPORT"
    message = "Unable to reliably analyze this report. Please upload a clearer report."


class InvalidHealthReportError(ReportError):
    code = "NOT_A_HEALTH_REPORT"
    message = ("Wrong file uploaded. This file does not appear to contain recognizable laboratory health parameters. "
               "It also does not look like a medical report (scan, ECG, summary, prescription). "
               "Please upload a medical report file.")


class OCRUnavailableError(ReportError):
    status_code = 503
    code = "OCR_UNAVAILABLE"
    message = "OCR is not configured. Please use a text-based PDF or configure the OCR engine."
