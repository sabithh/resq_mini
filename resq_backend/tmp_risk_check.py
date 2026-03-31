from risk import compute_risk
cases = [
    {'id':1,'area':20000,'confidence':0.95,'pose':'standing','pose_confidence':0.9,'aspect_ratio':0.8},
    {'id':2,'area':20000,'confidence':0.95,'pose':'standing','pose_confidence':0.9,'aspect_ratio':0.8,'bleeding':True},
    {'id':3,'area':20000,'confidence':0.95,'pose':'sitting','pose_confidence':0.9,'aspect_ratio':0.8},
    {'id':4,'area':20000,'confidence':0.95,'pose':'sitting','pose_confidence':0.9,'aspect_ratio':0.8,'bleeding':True},
    {'id':5,'area':20000,'confidence':0.95,'pose':'lying','pose_confidence':0.9,'aspect_ratio':1.4},
    {'id':6,'area':20000,'confidence':0.95,'pose':'WOUND','pose_confidence':1.0,'aspect_ratio':1.0},
]
for v in cases:
    out = compute_risk(v.copy(), drone_id='TEST', frame_width=1920, frame_height=1080)
    print(v['id'], v.get('pose'), v.get('bleeding',False), out['risk_score'], out['priority'])
