# Explicitly import all task modules so @app.task decorators run on worker startup
from . import video, pdf, transcribe
