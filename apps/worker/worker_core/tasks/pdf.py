from worker_core.main import app
from worker_core.config import DOWNLOAD_DIR
from fastfetchbot_file_export.pdf_export import export_pdf
from fastfetchbot_shared.utils.logger import logger


@app.task(name="file_export.pdf_export")
def pdf_export_task(html_string: str, output_filename: str) -> dict:
    logger.info(
        f"pdf_export_task started: output_filename={output_filename}, "
        f"html_string length={len(html_string)}, DOWNLOAD_DIR={DOWNLOAD_DIR}"
    )
    try:
        output_path = export_pdf(
            html_string=html_string,
            output_filename=output_filename,
            download_dir=DOWNLOAD_DIR,
        )
    except Exception:
        logger.exception(f"pdf_export_task failed: output_filename={output_filename}")
        raise
    logger.info(f"pdf_export_task completed: output_path={output_path}")
    return {"status": "success", "output_filename": output_path}
