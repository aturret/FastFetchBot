from . import pdf_export


class DocumentExport(object):
    def __init__(self, document):
        self.document = document

    def export(self):
        if self.document["type"] == "pdf":
            return pdf_export.PdfExport(self.document["content"]).export()
