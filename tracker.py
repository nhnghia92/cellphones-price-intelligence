import os,json,time
from datetime import datetime,timezone,timedelta
import gspread
from google.oauth2.service_account import Credentials
from google import genai
HEAD={'PRODUCTS':['product_id','brand','product_name','category','wattage','url','active'],'PRICE_RAW':['timestamp','product_id','retailer','brand','product_name','price','original_price','stock_status','url'],'PRICE_DAILY':['date','product_id','brand','product_name','price','change_1d_pct','change_7d_pct','change_30d_pct','min_30d','avg_30d'],'PRICE_EVENTS':['event_time','product_id','brand','product_name','event','change_pct','severity','details'],'AI_INSIGHTS':['event_time','product_id','brand','product_name','trend','impact','possible_cause','recommended_action','confidence','raw_ai'],'DASHBOARD':['metric','value']}
def gc():
 i=json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']); return gspread.authorize(Credentials.from_service_account_info(i,scopes=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/drive']))
def ws(sh,n):
 try: x=sh.worksheet(n)
 except gspread.WorksheetNotFound: x=sh.add_worksheet(n,rows=2000,cols=20); x.append_row(HEAD[n])
 if not x.row_values(1): x.append_row(HEAD[n])
 return x
def num(x):
 try:return float(str(x).replace(',','').replace('.',''))
 except:return None
def pct(a,b): return None if b in (None,0) or a is None else round((a-b)/b*100,2)
def ai(e):
 if not os.getenv('GEMINI_API_KEY'): return None
 c=genai.Client(api_key=os.environ['GEMINI_API_KEY']); model=os.getenv('GEMINI_MODEL','gemini-2.5-flash-lite')
 prompt='''Analyze this retail price event using ONLY supplied data. Do not state an unproven cause as fact. Return JSON keys: trend, impact, possible_cause, recommended_action, confidence. Data:\n'''+json.dumps(e,ensure_ascii=False)
 try:
  r=c.models.generate_content(model=model,contents=prompt); t=(r.text or '').strip(); a,b=t.find('{'),t.rfind('}')
  return (json.loads(t[a:b+1]),t) if a>=0 and b>a else None
 except Exception as ex: print('Gemini error',ex); return None
def main(products):
 sh=gc().open_by_key(os.environ['GOOGLE_SHEET_ID']); P,R,D,E,A,DB=[ws(sh,n) for n in ['PRODUCTS','PRICE_RAW','PRICE_DAILY','PRICE_EVENTS','AI_INSIGHTS','DASHBOARD']]
 known={r[0] for r in P.get_all_values()[1:] if r}
 for p in products:
  if p['product_id'] not in known:P.append_row([p['product_id'],p['brand'],p['product_name'],p['category'],p['wattage'],p['url'],'TRUE'])
 R.append_rows([[p['scraped_at'],p['product_id'],'CellphoneS',p['brand'],p['product_name'],p['current_price'],p['original_price'],p['stock_status'],p['url']] for p in products],value_input_option='USER_ENTERED')
 raw=R.get_all_values(); now=datetime.now(timezone.utc); events=[]; daily=[]
 for p in products:
  h=[]
  for r in raw[1:]:
   if len(r)>=6 and r[1]==p['product_id'] and num(r[5]) is not None:
    try:h.append((datetime.fromisoformat(r[0].replace('Z','+00:00')),num(r[5])))
    except:pass
  h.sort(); cur=p['current_price']; prev=h[-2][1] if len(h)>=2 else None
  def old(days):
   z=[v for d,v in h if d<=now-timedelta(days=days)]; return z[-1] if z else None
  h30=[v for d,v in h if d>=now-timedelta(days=30)]+[cur]
  c1,c7,c30=pct(cur,old(1)),pct(cur,old(7)),pct(cur,old(30))
  daily.append([now.date().isoformat(),p['product_id'],p['brand'],p['product_name'],cur,c1,c7,c30,min(h30),round(sum(h30)/len(h30),0)])
  if c1 is not None and abs(c1)>=float(os.getenv('MIN_CHANGE_PCT','5')):
   events.append({'event_time':now.isoformat(),'product_id':p['product_id'],'brand':p['brand'],'product_name':p['product_name'],'event':'PRICE_DROP' if c1<0 else 'PRICE_INCREASE','change_pct':c1,'severity':'HIGH' if abs(c1)>=10 else 'MEDIUM','details':f'{prev:,.0f} -> {cur:,.0f}'})
 D.append_rows(daily,value_input_option='USER_ENTERED')
 if events:
  E.append_rows([[e['event_time'],e['product_id'],e['brand'],e['product_name'],e['event'],e['change_pct'],e['severity'],e['details']] for e in events],value_input_option='USER_ENTERED')
  for e in events:
   r=ai(e)
   if r:
    d,t=r; A.append_row([e['event_time'],e['product_id'],e['brand'],e['product_name'],d.get('trend',''),d.get('impact',''),d.get('possible_cause',''),d.get('recommended_action',''),d.get('confidence',''),t]); time.sleep(1)
 DB.clear(); DB.append_rows([['metric','value'],['Last scrape UTC',now.isoformat()],['Tracked products',len(products)],['Events this run',len(events)],['Price drops',sum(e['change_pct']<0 for e in events)],['Price increases',sum(e['change_pct']>0 for e in events)]])
if __name__=='__main__':
 from scraper import scrape
 p=scrape(); print('SCRAPED',len(p)); main(p) if p else exit(1)
