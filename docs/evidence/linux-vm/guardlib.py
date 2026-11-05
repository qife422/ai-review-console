from pathlib import Path
import os, json, subprocess, signal, time, shutil, stat

ROOT=Path('/private/tmp/arc-linux-vm')
PLAN=json.loads((ROOT/'plan.json').read_text())
CLI=str(ROOT/'host/bin/limactl')
ENV=dict(os.environ)
ENV.update({'LIMA_HOME':str(ROOT/'lima'),'TMPDIR':str(ROOT/'tmp'),'PATH':str(ROOT/'host/bin')+':/usr/bin:/bin:/usr/sbin:/sbin'})
ENV.pop('SSH_AUTH_SOCK',None)

def write_json(path,obj):
    path=Path(path);temp=path.with_name(path.name+'.next.'+str(os.getpid()))
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n');os.replace(temp,path)

def process_info(pid):
    r=subprocess.run(['/bin/ps','-p',str(pid),'-o','uid=,pgid=,lstart=,command='],capture_output=True,text=True,timeout=3)
    if r.returncode or not r.stdout.strip():return None
    parts=r.stdout.strip().split(None,7)
    if len(parts)!=8:return None
    return {'pid':pid,'uid':int(parts[0]),'pgid':int(parts[1]),'birth':' '.join(parts[2:7]),'command':parts[7]}

def inventory():
    logical=allocated=entries=0
    assert ROOT.resolve()==ROOT and ROOT.lstat().st_uid==os.getuid()
    for folder,dirs,files in os.walk(ROOT,followlinks=False):
        for name in dirs+files:
            p=Path(folder)/name
            try:s=p.lstat()
            except FileNotFoundError:continue
            logical+=s.st_size;allocated+=s.st_blocks*512;entries+=1
            if stat.S_ISLNK(s.st_mode):assert p.resolve(strict=False).is_relative_to(ROOT),f'root escape: {p}'
    return {'logical_bytes':logical,'allocated_bytes':allocated,'entries':entries,'host_free_bytes':shutil.disk_usage(ROOT).free}

def cancel_owned_producer():
    path=ROOT/'results/active-producer.json'
    if not path.exists():return {'cancelled':False,'reason':'no registered producer'}
    record=json.loads(path.read_text())
    if not record.get('active'):return {'cancelled':False,'reason':'registered producer inactive'}
    actual=process_info(record['pid'])
    if actual is None:return {'cancelled':False,'reason':'producer already exited'}
    if not (actual['uid']==os.getuid() and actual['birth']==record['birth'] and actual['pgid']==record['pgid']==record['pid'] and actual['command'].startswith(CLI+' ')):
        return {'cancelled':False,'reason':'PID ownership/identity mismatch; no signal sent'}
    os.killpg(record['pgid'],signal.SIGTERM)
    time.sleep(1)
    again=process_info(record['pid'])
    if again and again['birth']==record['birth']:
        os.killpg(record['pgid'],signal.SIGKILL)
    return {'cancelled':True,'pid':record['pid'],'pgid':record['pgid'],'birth':record['birth']}

def stop_owned_vm():
    home=ROOT/'lima';instance=home/'probe'
    if not instance.exists():return {'result':'no owned instance exists'}
    assert home.resolve()==home and instance.resolve()==instance
    assert home.lstat().st_uid==os.getuid() and instance.lstat().st_uid==os.getuid()
    r=subprocess.run([CLI,'stop','--force','probe'],env=ENV,capture_output=True,text=True,timeout=30)
    return {'exit_code':r.returncode,'stdout':r.stdout[-4000:],'stderr':r.stderr[-4000:]}

def trip(reason):
    latch=ROOT/'results/guard-trip.json'
    try:
        with latch.open('x') as f:json.dump({'reason':reason,'time':time.time(),'controller_pid':os.getpid()},f)
    except FileExistsError:pass
    result={'reason':reason}
    try:result['producer']=cancel_owned_producer()
    except BaseException as error:result['producer']={'error':str(error),'unsafe_signal_not_sent':True}
    try:result['VM']=stop_owned_vm()
    except BaseException as error:result['VM']={'error':str(error)}
    write_json(ROOT/'results/guard-stop-result.json',result)
    return result

def check_active_guard():
    assert not (ROOT/'results/guard-trip.json').exists(),'persistent guard stop latch is set'
    control=json.loads((ROOT/'config/watch-control.json').read_text());assert control['run']
    owner=json.loads((ROOT/'results/watch-owner.json').read_text());actual=process_info(owner['pid'])
    assert actual and actual['uid']==os.getuid() and actual['birth']==owner['birth'] and str(ROOT/'config/capacity-watch.py') in actual['command'],'watcher not alive or identity mismatch'
    assert owner['epoch']==control['epoch']
    row=inventory()
    assert row['logical_bytes']<PLAN['logical_limit_bytes'] and row['allocated_bytes']<PLAN['allocated_warning_bytes'] and row['entries']<PLAN['files_limit'] and row['host_free_bytes']>=PLAN['free_floor_bytes'],row
    return row
