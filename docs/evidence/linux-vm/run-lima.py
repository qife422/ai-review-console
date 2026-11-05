from guardlib import *
import argparse

parser=argparse.ArgumentParser();parser.add_argument('--wall-seconds',type=int,default=180);parser.add_argument('--stdin-file');parser.add_argument('args',nargs=argparse.REMAINDER);opts=parser.parse_args()
assert opts.args and opts.args[0] in ['validate','create','start','stop','shell','list','copy','show-ssh','template'],opts.args
assert '--name=default' not in opts.args and 'default' not in opts.args
if opts.args[0]=='create':assert '--name=probe' in opts.args
if opts.args[0] in ['start','stop','shell','copy']:assert 'probe' in opts.args or any(arg.startswith('probe:') for arg in opts.args)
before=check_active_guard();command=[CLI]+opts.args
logpath=ROOT/'results'/('producer-'+opts.args[0]+'.log')
source=open(opts.stdin_file,'rb') if opts.stdin_file else subprocess.DEVNULL
started=time.monotonic();last=started
p=None;identity=None;problem=None;local_cancel=None

def cancel_direct_child():
    # A non-reaped Popen child cannot have its PID reused. start_new_session
    # makes its initial group ID equal to its PID; recheck before signalling.
    if p is None or p.poll() is not None:return {'cancelled':False,'reason':'no live direct child'}
    assert os.getpgid(p.pid)==p.pid
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:
        assert os.getpgid(p.pid)==p.pid
        os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
    return {'cancelled':True,'pid':p.pid,'group':p.pid,'basis':'direct non-reaped Popen child, start_new_session, checked group ID'}

with logpath.open('ab') as log:
    try:
        p=subprocess.Popen(command,env=ENV,cwd=ROOT,stdin=source,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        identity=process_info(p.pid)
        if p.poll() is None:
            assert identity and identity['pgid']==p.pid and identity['uid']==os.getuid() and identity['command'].startswith(CLI+' ')
            write_json(ROOT/'results/active-producer.json',{**identity,'active':True,'argv':command})
        while p.poll() is None:
            check_active_guard()
            assert time.monotonic()-started<opts.wall_seconds,'producer wall time'
            assert logpath.stat().st_size<2*2**20,'producer log cap'
            if time.monotonic()-last>=15:
                print(json.dumps({'running':opts.args[0],'seconds':round(time.monotonic()-started),'capacity':inventory()}),flush=True);last=time.monotonic()
            time.sleep(1)
    except BaseException as error:
        problem=type(error).__name__+': '+str(error)
        try:
            local_cancel=cancel_direct_child()
        finally:
            trip('producer startup/guard: '+problem)
    finally:
        if p is not None and p.poll() is None:
            local_cancel=cancel_direct_child();trip('producer unexpectedly live in finalizer')
code=p.wait() if p is not None else 125
record={'argv':command,'producer_identity':identity,'exit_code':code,'problem':problem,'direct_child_cancel':local_cancel,'seconds':round(time.monotonic()-started,3),'before':before,'after':inventory(),'guard_tripped':(ROOT/'results/guard-trip.json').exists()}
write_json(ROOT/'results/active-producer.json',{'active':False,'last_exit_code':code})
history=ROOT/'results/producer-results.json';items=json.loads(history.read_text()) if history.exists() else [];items.append(record);write_json(history,items)
print(json.dumps(record),flush=True)
print(logpath.read_text(errors='replace')[-12000:],flush=True)
if opts.stdin_file:source.close()
raise SystemExit(code if not (record['guard_tripped'] or problem) else 125)
