from guardlib import *
assert not (ROOT/'results/guard-trip.json').exists()
epoch=json.loads((ROOT/'config/watch-control.json').read_text())['epoch']
start=time.monotonic();peak={'logical_bytes':0,'allocated_bytes':0,'entries':0}
summary={'watch_pid':os.getpid(),'epoch':epoch,'guard_version':2,'sample_interval_seconds':1,'max_seconds':7200,'triggered':False}
identity=process_info(os.getpid());assert identity
write_json(ROOT/'results/watch-owner.json',{**identity,'epoch':epoch,'VM_namespace':str(ROOT/'lima/probe')})
print(json.dumps({'capacity_watch_started':os.getpid(),'epoch':epoch,'root':str(ROOT)}),flush=True)
try:
    with (ROOT/'results/capacity-watch.jsonl').open('a') as log:
        while json.loads((ROOT/'config/watch-control.json').read_text())['run']:
            row={**inventory(),'epoch':epoch,'elapsed_seconds':round(time.monotonic()-start,2)}
            for key in peak:peak[key]=max(peak[key],row[key])
            log.write(json.dumps(row)+'\n');log.flush()
            assert log.tell()<8*2**20,'capacity log cap'
            reason=None
            if row['logical_bytes']>=PLAN['logical_limit_bytes']:reason='logical cap reached'
            elif row['allocated_bytes']>=PLAN['allocated_warning_bytes']:reason='2.5GiB allocation pre-stop'
            elif row['entries']>=PLAN['files_limit']:reason='file-count cap'
            elif row['host_free_bytes']<PLAN['free_floor_bytes']:reason='host free floor'
            elif time.monotonic()-start>7200:reason='watch time cap'
            if reason:
                summary['triggered']=True;summary['stop_result']=trip(reason);break
            time.sleep(1)
except BaseException as error:
    summary['watch_error']=str(error);summary['triggered']=True;summary['stop_result']=trip('watch exception')
finally:
    summary['peak']=peak;summary['elapsed_seconds']=round(time.monotonic()-start,2)
    summary['final']=inventory()
    write_json(ROOT/'results/capacity-summary.json',summary)
    history=ROOT/'results/capacity-epochs.json';epochs=json.loads(history.read_text()) if history.exists() else []
    epochs.append(summary);write_json(history,epochs)
    print(json.dumps(summary),flush=True)
