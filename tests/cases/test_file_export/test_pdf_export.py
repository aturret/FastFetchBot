import os
import tempfile

import pytest

try:
    from fastfetchbot_file_export.pdf_export import convert_html_to_pdf
    HAS_WEASYPRINT = True
except OSError:
    HAS_WEASYPRINT = False


@pytest.mark.skipif(not HAS_WEASYPRINT, reason="WeasyPrint requires native pango/gobject libraries")
def test_convert_html_string_to_pdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        output = os.path.join(tmpdir, "test.pdf")
        convert_html_to_pdf(
            output_filename=output,
            html_string="<html><body><h1>Test</h1></body></html>",
        )
        assert os.path.exists(output)
        assert os.path.getsize(output) > 0
