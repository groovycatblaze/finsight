import os, math
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client

SUPABASE_URL=os.getenv('SUPABASE_URL','https://rrixdoasnqwkbruicvmo.supabase.co')
SUPABASE_KEY=os.getenv('SUPABASE_KEY','')
supabase: Client = create_client(SUPABASE_URL,SUPABASE_KEY) if SUPABASE_KEY else None

app=FastAPI(title='FinSight API', version='1.0.0')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['*'], allow_headers=['*'])

class SimulationIn(BaseModel):
    credit_limit_change_pct: float = Field(..., ge=-50, le=100)


def db():
    if not supabase: raise HTTPException(503,'SUPABASE_KEY is not configured')
    return supabase

def risk_label(score):
    return 'LOW' if score < 35 else ('MEDIUM' if score < 65 else 'HIGH')

def get_client(client_id):
    r=db().table('clients').select('*').eq('id',client_id).single().execute()
    if not r.data: raise HTTPException(404,'Client not found')
    return r.data

@app.get('/health')
def health(): return {'status':'ok','service':'finsight-api'}

@app.get('/api/clients')
def clients(search: Optional[str]=None, risk: Optional[str]=None, segment: Optional[str]=None, limit:int=100):
    q=db().table('clients').select('*').order('risk_score', desc=True).limit(limit)
    if risk: q=q.eq('risk_level',risk)
    if segment: q=q.eq('segment',segment)
    if search: q=q.or_(f'name.ilike.%{search}%,client_code.ilike.%{search}%,industry.ilike.%{search}%')
    return q.execute().data

@app.get('/api/clients/{client_id}')
def client(client_id:str):
    c=get_client(client_id)
    factors=db().table('risk_factors').select('*').eq('client_id',client_id).order('contribution',desc=True).execute().data
    simulations=db().table('simulations').select('*').eq('client_id',client_id).order('created_at',desc=True).limit(10).execute().data
    return {'client':c,'risk_factors':factors,'simulations':simulations}

@app.get('/api/dashboard')
def dashboard():
    data=db().table('clients').select('annual_revenue,annual_cost,profitability_score,risk_score,risk_level,segment,industry').execute().data
    n=len(data)
    revenue=sum(float(x['annual_revenue']) for x in data); cost=sum(float(x['annual_cost']) for x in data)
    profit=revenue-cost
    high=sum(x['risk_level']=='HIGH' for x in data); medium=sum(x['risk_level']=='MEDIUM' for x in data); low=n-high-medium
    seg={}
    for x in data: seg[x['segment']]=seg.get(x['segment'],0)+1
    industries={}
    for x in data: industries[x['industry']]=industries.get(x['industry'],0)+1
    return {'total_clients':n,'total_revenue':revenue,'total_cost':cost,'total_profit':profit,'avg_risk':sum(float(x['risk_score']) for x in data)/n if n else 0,'high_risk':high,'medium_risk':medium,'low_risk':low,'segments':seg,'industries':industries}

@app.post('/api/clients/{client_id}/simulate')
def simulate(client_id:str, payload:SimulationIn):
    c=get_client(client_id); change=payload.credit_limit_change_pct/100
    revenue=float(c['annual_revenue']); cost=float(c['annual_cost']); exposure=float(c['credit_exposure']); risk=float(c['risk_score'])
    # Decision-support scenario model: higher exposure can increase revenue, cost and risk.
    revenue2=revenue*(1+0.18*change); cost2=cost*(1+0.10*abs(change)+0.06*max(change,0)); exposure2=exposure*(1+change)
    risk2=min(100,max(0,risk + 28*change + 12*max(change,0)**2))
    profit2=revenue2-cost2
    if risk2>=75: rec='DECLINE — projected risk exceeds the high-risk threshold.'
    elif risk2>=55: rec='MANUAL REVIEW — attractive economics but elevated risk.'
    elif profit2 > revenue2*0.25: rec='APPROVE — strong projected profitability with controlled risk.'
    else: rec='APPROVE WITH MONITORING — acceptable trade-off; monitor exposure.'
    row={'client_id':client_id,'credit_limit_change_pct':payload.credit_limit_change_pct,'projected_revenue':round(revenue2,2),'projected_cost':round(cost2,2),'projected_profit':round(profit2,2),'projected_risk_score':round(risk2,2),'recommendation':rec}
    inserted=db().table('simulations').insert(row).execute().data
    db().table('audit_logs').insert({'action':'CREATE_SIMULATION','entity_type':'client','entity_id':client_id,'details':{'change_pct':payload.credit_limit_change_pct,'projected_risk':round(risk2,2)}}).execute()
    return inserted[0] if inserted else row

@app.post('/api/clients')
def create_client(payload:dict):
    required=['client_code','name','industry','annual_revenue','annual_cost','credit_exposure']
    missing=[x for x in required if x not in payload]
    if missing: raise HTTPException(400,f'Missing fields: {missing}')
    revenue=float(payload['annual_revenue']); cost=float(payload['annual_cost']); exposure=float(payload['credit_exposure'])
    profitability=min(100,max(0,(revenue-cost)/25000))
    risk=min(100,max(0,20+exposure/max(revenue,1)*100+float(payload.get('late_payments',0))*8))
    row={**payload,'profitability_score':round(profitability,2),'risk_score':round(risk,2),'risk_level':risk_label(risk),'segment':'PREMIUM' if profitability>60 and risk<35 else ('HIGH_RISK' if risk>=65 else 'STANDARD'),'status':'ACTIVE'}
    inserted=db().table('clients').insert(row).execute().data
    return inserted[0] if inserted else row
