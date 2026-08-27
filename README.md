# FinSight

Enterprise client profitability, credit-risk and segmentation decision-support platform evolved from the `client-profitability-risk-engine` and `credit-risk-modeling` projects.

## Architecture
- Frontend: static HTML/CSS/JavaScript + Chart.js, deployed to Vercel
- Backend: FastAPI, deployed to Render
- Database: PostgreSQL via Supabase
- Analytical layer: profitability/risk/segmentation logic inspired by the original Python projects

## Backend environment variables
`SUPABASE_URL` and `SUPABASE_KEY` (use the Supabase publishable/anon key for this demo; keep privileged keys server-side only).

## Local backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Frontend
Set `window.FINSIGHT_API` before the app script if you want live API calls, or deploy in demo mode.
