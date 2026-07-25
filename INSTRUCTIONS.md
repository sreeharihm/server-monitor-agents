# Monitor-Agent Instructions

## 1. Purpose
This project runs a local A2A-based monitoring stack:
- Dashboard UI server (port 8000)
- CloudWatch mock sub-agent (port 8001)
- Prometheus mock sub-agent (port 8002)
- Master agent polling loop (writes incident JSON files)

## 2. Prerequisites
- Python 3.11+ (tested on Python 3.13)
- Windows PowerShell (or any shell)

## 3. Install dependencies
Recommended:

```powershell
pip install fastapi "uvicorn[standard]" httpx "pydantic>=2.0" APScheduler python-dotenv PyYAML boto3 requests anthropic aiofiles
```

If `pip install -r requirements.txt` fails on Windows with a long-path OSError:
1. Enable Windows Long Paths in Group Policy/Registry.
2. Re-run `pip install -r requirements.txt`.
3. Or continue with the direct install command above.

## 4. Start the full application
From the project root:

```powershell
python run_all.py
```

Expected startup:
- dashboard ready on port 8000
- cloudwatch-agent ready on port 8001
- prometheus-agent ready on port 8002
- master agent starts polling

## 5. Open the dashboard
- URL: http://localhost:8000
- Health: http://localhost:8000/health
- Stats API: http://localhost:8000/api/stats
- Incidents API: http://localhost:8000/api/incidents

## 6. Verify data flow quickly
1. Open dashboard and confirm incident cards are visible.
2. Confirm master logs include fetch counts for `cloudwatch-a2a` and `prometheus-a2a`.
3. Confirm files are created in `output/incidents/`.

## 7. Run components individually (optional)
In separate terminals:

```powershell
python -m dashboard.server
python -m agents.cloudwatch_agent.server
python -m agents.prometheus_agent.server
python main.py
```

## 8. Stop the app
Press `Ctrl+C` in the terminal running `run_all.py`.

## 9. Common issues
### Port already in use
- Symptom: startup fails or health checks never pass.
- Fix: stop existing processes on 8000/8001/8002, then run again.

### Dashboard shows no incidents
- Check `output/incidents/` has JSON files.
- Wait for next poll interval.
- Ensure sub-agents are healthy at `/health` endpoints.

### `run_all.py` exits early
- Review terminal logs for first stack trace.
- Validate dependency installation.
- Confirm the current directory is project root before running.
