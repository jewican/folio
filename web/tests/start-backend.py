"""Real FastAPI/W2/model app with temporary storage for browser checks."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import uvicorn

backend = Path(__file__).resolve().parents[2] / 'backend'
sys.path.insert(0, str(backend))

with TemporaryDirectory(prefix='folio-browser-') as directory:
    os.environ['FOLIO_DATA_DIR'] = directory
    os.environ['FOLIO_DATABASE_PATH'] = str(Path(directory) / 'folio.sqlite3')
    os.environ['FOLIO_CORS_ORIGINS'] = 'http://localhost:3000'
    os.environ.pop('FOLIO_MAX_UPLOAD_BYTES', None)
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, log_level='warning')
