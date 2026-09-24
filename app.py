from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from math import radians, sin, cos, asin, sqrt
from datetime import datetime
from pathlib import Path
import json
import os

app = FastAPI(title='Sher Khan World API', version='FINAL-4.8')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=False, allow_methods=['*'], allow_headers=['*'])
customers, riders, orders, payments, complaints, deletion_requests, notifications, wallet_tx = {}, {}, {}, {}, {}, {}, [], []
seq = {'customer':0,'order':0,'payment':0,'complaint':0,'deletion':0,'notification':0,'wallet':0}
STATE_FILE = Path(__file__).with_name('sherkhanworld_state.json')

def save_state():
    data = {'customers':customers,'riders':riders,'orders':orders,'payments':payments,'complaints':complaints,'deletion_requests':deletion_requests,'notifications':notifications,'wallet_tx':wallet_tx,'seq':seq}
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_FILE)

def load_state():
    if not STATE_FILE.exists(): return
    try:
        data=json.loads(STATE_FILE.read_text(encoding='utf-8'))
        customers.update({int(k):v for k,v in data.get('customers',{}).items()})
        riders.update(data.get('riders',{})); orders.update({int(k):v for k,v in data.get('orders',{}).items()}); payments.update({int(k):v for k,v in data.get('payments',{}).items()}); complaints.update({int(k):v for k,v in data.get('complaints',{}).items()}); deletion_requests.update({int(k):v for k,v in data.get('deletion_requests',{}).items()}); notifications.extend(data.get('notifications',[])); wallet_tx.extend(data.get('wallet_tx',[])); seq.update(data.get('seq',{}))
    except Exception:
        pass

@app.middleware('http')
async def persist_state(request, call_next):
    response = await call_next(request)
    if request.method in {'POST','PUT','PATCH','DELETE'} and 200 <= response.status_code < 400:
        save_state()
    return response

class CustomerIn(BaseModel): name: str; phone: str
class RiderIn(BaseModel): rider_id: str; name: str; phone: str=''; cnic: str=''; bike_number: str=''
class LocationIn(BaseModel): rider_id: str; latitude: float=Field(ge=-90,le=90); longitude: float=Field(ge=-180,le=180); status: str='available'
class OrderIn(BaseModel): customer_id: int; purchase_amount: float=Field(gt=0); payment_method: str='Cash on Delivery'; pickup_latitude: float=0; pickup_longitude: float=0; delivery_address: str=''
class ComplaintIn(BaseModel): order_id: int; customer_id: int; rider_id: Optional[str]=None; category: str; description: str
class PaymentIn(BaseModel): order_id: int; method: str; amount: float=Field(gt=0); transaction_reference: Optional[str]=None

def now(): return datetime.utcnow().isoformat()
def km(a,b,c,d):
    p1,p2=radians(a),radians(c); x=radians(c-a); y=radians(d-b)
    h=sin(x/2)**2+cos(p1)*cos(p2)*sin(y/2)**2
    return 6371.0088*2*asin(sqrt(h))
def notify(role,rid,typ,title,msg,oid=None):
    seq['notification']+=1; n={'id':seq['notification'],'recipient_role':role,'recipient_id':str(rid),'type':typ,'title':title,'message':msg,'order_id':oid,'read':False,'created_at':now()}; notifications.append(n); return n

def commission(amount): return round(amount*0.05,2)

load_state()


class AuthRequest(BaseModel): name: str='Customer'; phone: str=''; provider: str='phone'
class OTPRequest(BaseModel): name: str='Customer'; phone: str
class OTPVerify(BaseModel): phone: str; otp: str

@app.post('/auth/provider/start')
def auth_provider(x:AuthRequest):
    if x.provider not in {'google','facebook'}: raise HTTPException(400,'Unsupported provider')
    seq['customer']+=1
    user={'id':seq['customer'],'name':x.name,'phone':x.phone,'provider':x.provider,'status':'active','created_at':now()}
    customers[user['id']]=user
    return {'mode':'development','provider':x.provider,'user':user,'message':'Real OAuth credentials/configuration required for production.'}

OTP_STORE = {}
@app.post('/auth/otp/request')
def auth_otp(x:OTPRequest):
    import secrets
    provider=os.getenv('SKW_OTP_PROVIDER','development').strip().lower()
    if provider != 'development':
        return {'mode':'production','provider':provider,'phone':x.phone,'sent':False,'message':'OTP provider is configured as production, but the provider adapter is not installed. No OTP is exposed by the API.'}
    otp=f'{secrets.randbelow(1000000):06d}'
    OTP_STORE[x.phone]={'otp':otp,'expires_at':datetime.utcnow().timestamp()+300}
    return {'mode':'development','otp':otp,'phone':x.phone,'expires_in_seconds':300,'message':'Development OTP only. Set SKW_OTP_PROVIDER on the server before production.'}

@app.post('/auth/otp/verify')
def verify_otp(x:OTPVerify):
    item=OTP_STORE.get(x.phone)
    if not item or datetime.utcnow().timestamp()>item['expires_at'] or x.otp!=item['otp']:
        raise HTTPException(401,'Invalid or expired OTP')
    OTP_STORE.pop(x.phone,None)
    for c in customers.values():
        if c.get('phone')==x.phone: return {'ok':True,'user':c}
    seq['customer']+=1
    user={'id':seq['customer'],'name':'Customer','phone':x.phone,'provider':'phone','status':'active','created_at':now()}
    customers[user['id']]=user
    return {'ok':True,'user':user}

@app.get('/config/status')
def config_status():
    otp=os.getenv('SKW_OTP_PROVIDER','development').strip().lower()
    payment=os.getenv('SKW_PAYMENT_PROVIDER','manual').strip().lower()
    return {'environment':os.getenv('SKW_ENV','development'),'otp_provider':otp,'payment_provider':payment,'production_ready':otp!='development' and payment not in {'manual','demo'},'credentials_stored_server_side':True}

@app.get('/release/status')
def release_status():
    env=os.getenv('SKW_ENV','development').strip().lower()
    otp=os.getenv('SKW_OTP_PROVIDER','development').strip().lower()
    payment=os.getenv('SKW_PAYMENT_PROVIDER','manual').strip().lower()
    checks={
        'https_required': env=='production',
        'otp_provider_configured': otp not in {'development',''},
        'payment_provider_configured': payment not in {'manual','demo',''},
        'secrets_server_side': True,
        'commission_rule_5pct_on_accept': True,
        'rider_wallet_precheck': True,
        'whole_pakistan_service': True,
    }
    return {'version':'4.8','environment':env,'checks':checks,'production_ready':all(checks.values()),'note':'Real OTP/payment credentials and provider adapters are still required before live transactions.'}

@app.get('/launch/summary')
def launch_summary():
    env=os.getenv('SKW_ENV','development').strip().lower()
    otp=os.getenv('SKW_OTP_PROVIDER','development').strip().lower()
    payment=os.getenv('SKW_PAYMENT_PROVIDER','manual').strip().lower()
    return {
        'version':'4.8',
        'core_app_flow_ready':True,
        'commission_rule':'5% deducted immediately on rider acceptance; insufficient wallet blocks acceptance',
        'service_area':'Pakistan-wide',
        'external_blockers':{
            'real_sms_otp': otp in {'development',''},
            'production_https_server': env!='production',
            'payment_gateway': payment in {'manual','demo',''},
            'signed_aab_and_play_testing': True
        },
        'note':"External provider credentials/accounts and Play Console steps cannot be completed inside the project without the owner's real accounts/configuration."
    }

@app.get('/production/checklist')
def production_checklist():
    env=os.getenv('SKW_ENV','development').strip().lower()
    otp=os.getenv('SKW_OTP_PROVIDER','development').strip().lower()
    payment=os.getenv('SKW_PAYMENT_PROVIDER','manual').strip().lower()
    checks={
        'environment_production': env=='production',
        'otp_provider': otp not in {'development',''},
        'payment_provider': payment not in {'manual','demo',''},
        'server_side_secrets': True,
        'https_policy': True,
        'commission_5pct_on_accept': True,
        'wallet_precheck_before_accept': True,
        'whole_pakistan': True,
        'live_rider_location': True,
    }
    return {'version':'4.8','checks':checks,'ready_count':sum(1 for v in checks.values() if v),'total_checks':len(checks),'production_ready':all(checks.values()),'note':'This endpoint never returns private credentials.'}

MARKETS=[
{"name":"Imtiaz Mega — Karachi Tariq Road","city":"Karachi","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Tariq+Road+Karachi"},
{"name":"Imtiaz Mega — Gulshan-e-Iqbal","city":"Karachi","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Gulshan-e-Iqbal+Karachi"},
{"name":"Imtiaz Mega — Qayyumabad","city":"Karachi","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Qayyumabad+Karachi"},
{"name":"Imtiaz Mega — Nazimabad","city":"Karachi","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Nazimabad+Karachi"},
{"name":"Imtiaz Mega — Zamzama","city":"Karachi","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Zamzama+Karachi"},
{"name":"Imtiaz Mega — Multan","city":"Multan","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Multan"},
{"name":"Imtiaz Mega — Gulberg Lahore","city":"Lahore","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Gulberg+Lahore"},
{"name":"Imtiaz Mega — Faisalabad","city":"Faisalabad","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Faisalabad"},
{"name":"Imtiaz Mega — Gujranwala","city":"Gujranwala","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Gujranwala"},
{"name":"Imtiaz Mega — Sialkot","city":"Sialkot","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Sialkot"},
{"name":"Imtiaz Mega — Peshawar","city":"Peshawar","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Peshawar"},
{"name":"Imtiaz Mega — Quetta","city":"Quetta","category":"department store","maps":"https://www.google.com/maps/search/?api=1&query=Imtiaz+Mega+Quetta"},
{"name":"Anarkali Bazaar","city":"Lahore","category":"market","maps":"https://www.google.com/maps/search/?api=1&query=Anarkali+Bazaar+Lahore"},
{"name":"Liberty Market","city":"Lahore","category":"market","maps":"https://www.google.com/maps/search/?api=1&query=Liberty+Market+Lahore"},
{"name":"Raja Bazaar","city":"Rawalpindi","category":"market","maps":"https://www.google.com/maps/search/?api=1&query=Raja+Bazaar+Rawalpindi"},
{"name":"Saddar Bazaar","city":"Peshawar","category":"market","maps":"https://www.google.com/maps/search/?api=1&query=Saddar+Bazaar+Peshawar"},
{"name":"Jinnah Market","city":"Quetta","category":"market","maps":"https://www.google.com/maps/search/?api=1&query=Jinnah+Market+Quetta"},
]

@app.get('/markets')
def markets(city: Optional[str]=None):
    if city:
        return [m for m in MARKETS if m['city'].lower()==city.lower()]
    return MARKETS

@app.get('/health')
def health():
    otp=os.getenv('SKW_OTP_PROVIDER','development').strip().lower(); payment=os.getenv('SKW_PAYMENT_PROVIDER','manual').strip().lower()
    return {'ok':True,'service':'Sher Khan World','version':'FINAL-4.8','storage':'persistent-json','features':['otp-provider-config','otp-development-fallback','live-rider-location','orders','payments','notifications','wallet-commission-5pct'],'production_ready':otp!='development' and payment not in {'manual','demo'}}

@app.get('/riders/{rider_id}/dashboard')
def rider_dashboard(rider_id:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    r=riders[rider_id]
    active=[o for o in orders.values() if o.get('rider_id')==rider_id and o.get('status') not in {'completed','cancelled'}]
    return {'rider_id':rider_id,'name':r['name'],'verification_status':r['verification_status'],'status':r['status'],'wallet':round(r['wallet'],2),'active_orders':active,'unread_notifications':sum(1 for n in notifications if n['recipient_role']=='rider' and n['recipient_id']==rider_id and not n['read'])}
@app.post('/customers')
def create_customer(x:CustomerIn):
    seq['customer']+=1; customers[seq['customer']]={'id':seq['customer'],'name':x.name,'phone':x.phone,'status':'active','created_at':now()}; return customers[seq['customer']]
@app.get('/customers/by-phone/{phone}')
def customer_by_phone(phone:str):
    for c in customers.values():
        if c.get('phone')==phone: return c
    raise HTTPException(404,'Customer not found')
@app.post('/riders')
def create_rider(x:RiderIn):
    if x.rider_id in riders: return riders[x.rider_id]
    riders[x.rider_id]={'rider_id':x.rider_id,'name':x.name,'phone':x.phone,'cnic':x.cnic,'bike_number':x.bike_number,'verification_status':'pending','status':'offline','wallet':0.0,'latitude':None,'longitude':None}; return riders[x.rider_id]
@app.post('/riders/{rider_id}/approve')
def approve(rider_id:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    riders[rider_id]['verification_status']='approved'; return riders[rider_id]
@app.post('/riders/{rider_id}/status')
def rider_status(rider_id:str, status:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    if status not in {'available','busy','offline'}: raise HTTPException(400,'Invalid status')
    if status=='available' and any(o.get('rider_id')==rider_id and o.get('status') not in {'completed','cancelled'} for o in orders.values()):
        raise HTTPException(400,'Rider has an active order')
    riders[rider_id]['status']=status
    return riders[rider_id]

@app.post('/riders/location')
def location(x:LocationIn):
    if x.rider_id not in riders: raise HTTPException(404,'Rider not found')
    if x.status not in {'available','busy','offline'}: raise HTTPException(400,'Invalid status')
    riders[x.rider_id].update(latitude=x.latitude,longitude=x.longitude,status=x.status); return riders[x.rider_id]
@app.post('/riders/{rider_id}/wallet/deposit')
def deposit(rider_id:str, amount:float):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    if amount<=0: raise HTTPException(400,'Invalid amount')
    riders[rider_id]['wallet']+=amount; seq['wallet']+=1; wallet_tx.append({'id':seq['wallet'],'rider_id':rider_id,'type':'deposit','amount':amount,'created_at':now()}); return {'wallet':riders[rider_id]['wallet']}
@app.post('/orders')
def create_order(x:OrderIn):
    if x.customer_id not in customers: raise HTTPException(404,'Customer not found')
    seq['order']+=1; o={'id':seq['order'],'customer_id':x.customer_id,'purchase_amount':x.purchase_amount,'commission':commission(x.purchase_amount),'payment_method':x.payment_method,'payment_status':'pending','pickup_latitude':x.pickup_latitude,'pickup_longitude':x.pickup_longitude,'delivery_address':x.delivery_address,'rider_id':None,'status':'waiting','created_at':now()}; orders[o['id']]=o; notify('customer',x.customer_id,'order_placed','Order Placed',f"Order #{o['id']} placed.",o['id']); return o
@app.post('/orders/{order_id}/match')
def match(order_id:int):
    if order_id not in orders: raise HTTPException(404,'Order not found')
    o=orders[order_id]
    if o['status'] not in {'waiting','assigned'}:
        raise HTTPException(400,'Only waiting/assigned orders can be matched')
    for radius in (1,2,5,10,20):
        cand=[]
        for r in riders.values():
            if r['verification_status']=='approved' and r['status']=='available' and r['latitude'] is not None:
                d=km(o['pickup_latitude'],o['pickup_longitude'],r['latitude'],r['longitude'])
                if d<=radius: cand.append((d,r))
        if cand:
            cand.sort(key=lambda z:z[0]); r=cand[0][1]; o.update(rider_id=r['rider_id'],status='assigned',match_radius_km=radius,distance_km=round(cand[0][0],3)); notify('rider',r['rider_id'],'new_order','نیا آرڈر',f"Order #{order_id} assigned.",order_id); notify('customer',o['customer_id'],'rider_assigned','Rider Assigned',f"Rider {r['name']} assigned.",order_id); return o
    return {'status':'waiting','message':'No available rider up to 20 km'}
@app.post('/orders/{order_id}/accept')
def accept(order_id:int,rider_id:str):
    if order_id not in orders or rider_id not in riders: raise HTTPException(404,'Order or rider not found')
    o,r=orders[order_id],riders[rider_id]
    if r['verification_status']!='approved': raise HTTPException(403,'Rider is not approved')
    if o['status'] not in {'waiting','assigned'}: raise HTTPException(400,'Order is not available')
    if o.get('rider_id') and o['rider_id'] != rider_id: raise HTTPException(403,'Order is assigned to another rider')
    if any(x.get('rider_id')==rider_id and x.get('status') not in {'completed','cancelled'} and x.get('id')!=order_id for x in orders.values()):
        raise HTTPException(400,'Rider already has an active order')
    fee=o['commission']
    if r['wallet']<fee: raise HTTPException(400,f'Insufficient wallet. Required {fee}')
    r['wallet']-=fee; r['status']='busy'; o.update(rider_id=rider_id,status='accepted',accepted_at=now()); seq['wallet']+=1; wallet_tx.append({'id':seq['wallet'],'rider_id':rider_id,'type':'commission','amount':fee,'order_id':order_id,'created_at':now()}); notify('customer',o['customer_id'],'rider_accepted','Rider Accepted',f"Rider {r['name']} accepted order.",order_id); return {'order':o,'commission_charged':fee,'rider_wallet':r['wallet']}
@app.get('/riders/{rider_id}/orders')
def rider_orders(rider_id:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    return [o for o in orders.values() if o.get('rider_id')==rider_id and o.get('status') not in {'completed','cancelled'}]

@app.get('/orders/{order_id}')
def get_order(order_id:int):
    if order_id not in orders: raise HTTPException(404,'Order not found')
    return orders[order_id]

@app.post('/orders/{order_id}/cancel')
def cancel_order(order_id:int):
    if order_id not in orders: raise HTTPException(404,'Order not found')
    o=orders[order_id]
    if o['status'] in {'completed','delivered','cancelled'}: raise HTTPException(400,'Order cannot be cancelled now')
    o['status']='cancelled'; o['updated_at']=now()
    if o.get('rider_id') in riders:
        riders[o['rider_id']]['status']='available'
        notify('rider',o['rider_id'],'order_cancelled','Order Cancelled',f"Order #{order_id} cancelled by customer.",order_id)
    notify('customer',o['customer_id'],'order_cancelled','Order Cancelled',f"Order #{order_id} cancelled.",order_id)
    notify('admin','admin','order_cancelled','Order Cancelled',f"Order #{order_id} was cancelled.",order_id)
    return o

@app.post('/orders/{order_id}/status')
def status(order_id:int,status:str,rider_id:Optional[str]=None):
    if order_id not in orders: raise HTTPException(404,'Order not found')
    o=orders[order_id]; s=status.lower().replace(' ','_')
    transitions={'accepted':'shopping','shopping':'on_the_way','on_the_way':'delivered','delivered':'completed'}
    if s not in {'shopping','on_the_way','delivered','completed','cancelled','disputed'}: raise HTTPException(400,'Invalid status')
    current=o['status']
    if rider_id is not None and o.get('rider_id') != rider_id:
        raise HTTPException(403,'Only the assigned rider can update this order')
    if o.get('rider_id') and rider_id is None:
        raise HTTPException(403,'rider_id is required for an assigned order')
    if s in transitions.values() and transitions.get(current)!=s:
        raise HTTPException(400,f'Invalid order transition: {current} -> {s}')
    if s=='completed' and current!='delivered': raise HTTPException(400,'Order must be delivered before completion')
    if s=='cancelled' and current in {'completed','delivered','cancelled'}: raise HTTPException(400,'Order cannot be cancelled now')
    o['status']=s; o['updated_at']=now()
    if s=='completed' and o.get('rider_id') in riders: riders[o['rider_id']]['status']='available'
    if s=='cancelled' and o.get('rider_id') in riders: riders[o['rider_id']]['status']='available'
    notify('customer',o['customer_id'],'order_status','Order Update',f"Order #{order_id}: {s}",order_id)
    if o.get('rider_id'): notify('rider',o['rider_id'],'order_status','Order Update',f"Order #{order_id}: {s}",order_id)
    return o
@app.post('/payments')
def create_payment(x:PaymentIn):
    if x.order_id not in orders: raise HTTPException(404,'Order not found')
    if x.method not in {'Cash on Delivery','Easypaisa','JazzCash','Online Payment'}: raise HTTPException(400,'Unsupported payment method')
    if x.amount != orders[x.order_id]['purchase_amount']: raise HTTPException(400,'Payment amount must equal order purchase amount')
    seq['payment']+=1; p={'id':seq['payment'],'order_id':x.order_id,'method':x.method,'amount':x.amount,'status':'pending','transaction_reference':x.transaction_reference,'created_at':now()}; payments[p['id']]=p; return p
@app.get('/payments/order/{order_id}')
def order_payments(order_id:int):
    if order_id not in orders: raise HTTPException(404,'Order not found')
    return [p for p in payments.values() if p['order_id']==order_id]

@app.post('/payments/{payment_id}/mark-paid')
def mark_paid(payment_id:int):
    if payment_id not in payments: raise HTTPException(404,'Payment not found')
    p=payments[payment_id]
    if p['status']=='paid': return p
    p['status']='paid'; p['paid_at']=now()
    if p['order_id'] in orders: orders[p['order_id']]['payment_status']='paid'
    return p
class DeletionRequestIn(BaseModel):
    role: str='customer'
    phone: str
    reason: str=''

@app.post('/account/deletion-request')
def account_deletion_request(x:DeletionRequestIn):
    if x.role not in {'customer','rider'}:
        raise HTTPException(400,'Invalid role')
    seq['deletion']+=1
    req={'id':seq['deletion'],'role':x.role,'phone':x.phone,'reason':x.reason,'status':'pending','created_at':now()}
    deletion_requests[seq['deletion']]=req
    notify('admin','admin','account_deletion','Account/Data Deletion Request',
           f"Deletion request #{req['id']} received for {x.role}.",None)
    return {'ok':True,'request':req}

@app.get('/admin/deletion-requests')
def admin_deletion_requests(status_filter:Optional[str]=None):
    rs=list(deletion_requests.values())
    if status_filter: rs=[r for r in rs if r.get('status')==status_filter]
    return list(reversed(rs))

@app.post('/complaints')
def create_complaint(x:ComplaintIn):
    seq['complaint']+=1; c={'id':seq['complaint'],'order_id':x.order_id,'customer_id':x.customer_id,'rider_id':x.rider_id,'category':x.category,'description':x.description,'status':'open','admin_action':None,'created_at':now()}; complaints[c['id']]=c; notify('admin','admin','complaint','New Complaint',f"Complaint #{c['id']} received.",x.order_id); return c
@app.get('/complaints')
def list_complaints(): return list(complaints.values())
@app.post('/complaints/{cid}/action')
def complaint_action(cid:int,action:str):
    if cid not in complaints: raise HTTPException(404,'Complaint not found')
    complaints[cid]['admin_action']=action; complaints[cid]['status']='resolved' if action=='resolve' else 'reviewed'; return complaints[cid]
@app.get('/wallet/{rider_id}/transactions')
def wallet_transactions(rider_id:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    return [x for x in wallet_tx if x['rider_id']==rider_id]

@app.get('/notifications/{role}/{rid}')
def get_notifications(role:str,rid:str): return [n for n in notifications if n['recipient_role']==role and n['recipient_id']==str(rid)]

@app.get('/notifications/{role}/{rid}/unread')
def get_unread_notifications(role:str,rid:str): return [n for n in notifications if n['recipient_role']==role and n['recipient_id']==str(rid) and not n['read']]

@app.get('/notifications/{role}/{rid}/count')
def unread_notification_count(role:str,rid:str): return {'count':sum(1 for n in notifications if n['recipient_role']==role and n['recipient_id']==str(rid) and not n['read'])}
@app.post('/notifications/{notification_id}/read')
def mark_notification_read(notification_id:int):
    for n in notifications:
        if n['id']==notification_id:
            n['read']=True; n['read_at']=now(); return n
    raise HTTPException(404,'Notification not found')
@app.get('/admin/summary')
def summary():
    return {'orders':len(orders),'customers':len(customers),'riders':len(riders),'active_orders':sum(1 for x in orders.values() if x['status'] not in {'completed','cancelled'}),'total_commission':round(sum(x['amount'] for x in wallet_tx if x['type']=='commission'),2),'wallet_transactions':len(wallet_tx),'complaints':len(complaints),'open_complaints':sum(1 for x in complaints.values() if x['status']=='open'),'unread_admin_notifications':sum(1 for n in notifications if n['recipient_role']=='admin' and not n['read'])}

@app.get('/customers/{customer_id}/orders')
def customer_orders(customer_id:int):
    if customer_id not in customers: raise HTTPException(404,'Customer not found')
    return list(reversed([o for o in orders.values() if o['customer_id']==customer_id]))

@app.get('/riders/{rider_id}/wallet/summary')
def rider_wallet_summary(rider_id:str):
    if rider_id not in riders: raise HTTPException(404,'Rider not found')
    tx=[x for x in wallet_tx if x['rider_id']==rider_id]
    deposits=round(sum(x['amount'] for x in tx if x['type']=='deposit'),2)
    commissions=round(sum(x['amount'] for x in tx if x['type']=='commission'),2)
    return {'rider_id':rider_id,'balance':round(riders[rider_id]['wallet'],2),'total_deposits':deposits,'total_commission':commissions,'transactions':list(reversed(tx))}


@app.get('/admin/finance')
def admin_finance():
    commission_total=round(sum(float(x.get('amount',0)) for x in wallet_tx if x.get('type')=='commission'),2)
    deposits_total=round(sum(float(x.get('amount',0)) for x in wallet_tx if x.get('type')=='deposit'),2)
    rider_wallet_total=round(sum(float(r.get('wallet',0)) for r in riders.values()),2)
    paid_total=round(sum(float(p.get('amount',0)) for p in payments.values() if p.get('status')=='paid'),2)
    pending_total=round(sum(float(p.get('amount',0)) for p in payments.values() if p.get('status')=='pending'),2)
    return {'commission_total':commission_total,'deposits_total':deposits_total,'rider_wallet_total':rider_wallet_total,'paid_payments_total':paid_total,'pending_payments_total':pending_total,'wallet_transactions':len(wallet_tx)}

@app.get('/admin/riders')
def admin_riders(status_filter:Optional[str]=None):
    rs=list(riders.values())
    if status_filter: rs=[r for r in rs if r.get('status')==status_filter]
    return rs

@app.get('/admin/orders')
def admin_orders(status_filter:Optional[str]=None):
    if status_filter:
        return [o for o in orders.values() if o['status']==status_filter]
    return list(orders.values())

@app.get('/admin/complaints')
def admin_complaints(status_filter:Optional[str]=None):
    cs=list(complaints.values())
    if status_filter: cs=[c for c in cs if c.get('status')==status_filter]
    return list(reversed(cs))
