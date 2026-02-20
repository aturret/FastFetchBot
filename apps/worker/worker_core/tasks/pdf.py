from worker_core.main import app
from worker_core.config import DOWNLOAD_DIR
from fastfetchbot_file_export.pdf_export import export_pdf


@app.task(name="file_export.pdf_export")
def pdf_export_task(html_string: str, output_filename: str) -> dict:
    output_path = export_pdf(
        html_string=html_string,
        output_filename=output_filename,
        download_dir=DOWNLOAD_DIR,
    )
    return {"status": "success", "output_filename": output_path}
