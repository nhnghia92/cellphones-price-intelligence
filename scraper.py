import os,re,json
from datetime import datetime,timezone
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
URL=os.getenv('CELLPHONES_URL','https://cellphones.com.vn/phu-kien/sac-dien-thoai/sac.html?order=filter_price&dir=asc&sac_cong_suat=45w-duoi-67w')
def price(s):
    vals=[]
    for x in re.findall(r'\d[\d.,]{3,}',s or ''):
        try:
            n=int(x.replace('.','').replace(',',''))
            if 10000<=n<=50000000: vals.append(n)
        except: pass
    return min(vals) if vals else None
def pid(url): return url.split('?')[0].rstrip('/').split('/')[-1].lower()
def clean(s): return re.sub(r'\s+',' ',s or '').strip()
def scrape():
    now=datetime.now(timezone.utc).isoformat(); out={}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        page=b.new_page(locale='vi-VN',user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131 Safari/537.36')
        page.goto(URL,wait_until='domcontentloaded',timeout=90000); page.wait_for_timeout(5000)
        for _ in range(6): page.mouse.wheel(0,1800); page.wait_for_timeout(1000)
        for a in page.locator('a[href*=".html"]').all():
            try:
                href=a.get_attribute('href') or ''; text=clean(a.inner_text(timeout=1000))
            except: continue
            u=urljoin(URL,href)
            if 'cellphones.com.vn' not in u or not text: continue
            low=text.lower()
            if not any(x in low for x in ['belkin','esr','anker','ugreen','baseus','sạc','charger','củ sạc']): continue
            pval=price(text)
            if not pval:
                try: pval=price(a.locator('xpath=ancestor::*[self::div or self::li][1]').inner_text(timeout=1000))
                except: pass
            if not pval: continue
            k=pid(u); brand=next((x.title() for x in ['belkin','esr','anker','ugreen','baseus','apple','samsung','xiaomi'] if x in low),'')
            out[k]={'product_id':k,'brand':brand,'product_name':text.split('\n')[0][:250],'category':'Charger','wattage':'','current_price':pval,'original_price':'','stock_status':'','url':u,'scraped_at':now}
        b.close()
    return list(out.values())
if __name__=='__main__': print(json.dumps(scrape(),ensure_ascii=False))
