# LG Demo

### Instruction to running this locally
1. Backend

In superego-lgdemo:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python backend_server_async.py
```

2. Frontend

In superego-lgdemo/superego-frontend:

```
npm install
npm install svelte-persisted-store
npm run dev
From your browser, http://localhost:5173/ gives you access to the frontend
```