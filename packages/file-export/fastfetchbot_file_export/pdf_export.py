import os

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

CSS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_export.css")


def convert_html_to_pdf(
    output_filename: str,
    html_string: str = None,
    html_file: str = None,
) -> None:
    """Convert HTML content to PDF using WeasyPrint."""
    font_config = FontConfiguration()
    css_item = CSS(filename=CSS_FILE, font_config=font_config)
    if html_file:
        html_item = HTML(filename=html_file, encoding="utf-8")
    elif html_string:
        html_item = HTML(string=html_string)
    else:
        raise ValueError("Either html_string or html_file must be provided")
    html_item.write_pdf(output_filename, stylesheets=[css_item])


def export_pdf(
    html_string: str = None,
    html_file: str = None,
    output_filename: str = "output.pdf",
    download_dir: str = "/tmp",
) -> str:
    """Export HTML to PDF and return the output file path."""
    output_path = os.path.join(download_dir, output_filename)
    convert_html_to_pdf(
        output_filename=output_path,
        html_string=html_string,
        html_file=html_file,
    )
    return output_path
