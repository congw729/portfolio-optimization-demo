# Deploying to Streamlit Community Cloud

> How to serve this app in the cloud — open it in any browser without running
> `streamlit run` locally.

## Why not GitHub Pages?

GitHub Pages only serves **static files** (HTML/CSS/JS); it cannot run a Python
server. Streamlit is a **server-side** app (every interaction talks to a running
`streamlit run` process over WebSocket), so it cannot be hosted on Pages.

Use **Streamlit Community Cloud** instead: it is free, connects directly to this
GitHub repo, installs dependencies, runs `streamlit run app/Home.py`, and
auto-redeploys on every push to `main`.

## Dependency files — how the cloud knows what to install

Streamlit Community Cloud **only reads the root `requirements.txt`** (or a
`Pipfile` / `environment.yml` / `pyproject.toml`). It does **not** look for a custom
name like `requirements-deploy.txt`.

To make the cloud install a minimal set of packages, this repo keeps three files:

| File | Purpose |
|---|---|
| `requirements.txt` | **minimal cloud deps** (`streamlit` / `numpy` / `pandas` / `scipy` / `plotly`) — **this is what the cloud installs** |
| `requirements-deploy.txt` | the same minimal list, kept as a clearly-named deployment manifest |
| `docs/requirements-full.txt` | full dev freeze (jupyter, yfinance, matplotlib, seaborn, akshare, sklearn…) for reproducing the local environment |

Why minimal: the full freeze includes the entire Jupyter stack plus packages the web
app never imports (`yfinance`, `matplotlib`, `seaborn`, `akshare`, `scikit-learn`).
Installing all of that in the cloud is slow and can time out. The app only reads
`data/` and `output/` artifacts, so those five packages are sufficient.

## Deploy steps

1. Push this repo to GitHub (already done).
2. Go to <https://share.streamlit.io> and sign in with GitHub.
3. Click **New app → From existing repo**.
4. Fill in:
   - **Repository**: `congw729/portfolio-optimization-demo`
   - **Branch**: `main`
   - **Main file path**: `app/Home.py`
5. Click **Deploy**.

Streamlit Cloud will then:

- run `pip install -r requirements.txt` (the minimal list),
- launch `streamlit run app/Home.py`,
- give you a public URL like `https://<your-app>.streamlit.app`.

## Notes

- **Offline data**: `data/*.csv` and `output/*.csv` are committed, and the app only
  reads them — no network fetch (`yfinance`) is needed in the cloud.
- **Every push to `main` redeploys automatically.**
- **When changing dependencies**: update `requirements.txt` (this is what the cloud
  reads) and keep `requirements-deploy.txt` and `docs/requirements-full.txt` in sync.
