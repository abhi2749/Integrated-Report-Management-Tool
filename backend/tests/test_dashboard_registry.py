from dashboard_registry import DashboardRegistry

def u(i='u1', n='alice', r='user'): return {'id':i,'username':n,'role':r}
def test_crud_and_version(tmp_path):
    r=DashboardRegistry(tmp_path/'m.db'); a=r.save('d1','Sales',{'widgets':[1]},u()); assert a['version']==1
    b=r.save('d1','Sales 2',{'widgets':[2]},u()); assert b['version']==2 and r.get('d1',u())['name']=='Sales 2'
def test_ownership(tmp_path):
    r=DashboardRegistry(tmp_path/'m.db'); r.save('d1','Private',{},u()); assert r.get('d1',u('u2','bob')) is None
    try: r.delete('d1',u('u2','bob')); assert False
    except PermissionError: pass
def test_admin(tmp_path):
    r=DashboardRegistry(tmp_path/'m.db'); r.save('d1','Private',{},u()); assert r.get('d1',u('a','root','admin'))['name']=='Private'
