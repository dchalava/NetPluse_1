# NetPulse API

Install dependencies with `pip install -r requirements.txt`, then start the API from the project root:

```bash
uvicorn app.main:app --reload
```

The interactive API docs are available at `http://127.0.0.1:8000/docs`. Device data is held in memory and resets when the process restarts.