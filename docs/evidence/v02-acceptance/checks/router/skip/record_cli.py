from pathlib import Path
import subprocess,json,datetime,sys,re
out=Path(__file__).resolve().parent
label=sys.argv[1]
cmd=["node","/Users/ffq/.npm/_npx/31e32ef8478fbf80/node_modules/@playwright/cli/playwright-cli.js","--session","arc-v02-skip",*sys.argv[2:]]
p=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
with (out/(label+".log")).open("x") as f: f.write(p.stdout)
records=json.loads((out/"commands.json").read_text())
records.append({"argv":cmd,"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"exit_code":p.returncode,"log":label+".log"})
(out/"commands.json").write_text(json.dumps(records,indent=2))
print(p.stdout)
m=re.search(r"\[Snapshot\]\((\.playwright-cli/[^)]+\.yml)\)",p.stdout)
if m:
 text=Path(m.group(1)).read_text()
 with (out/(label+".yml")).open("x") as f: f.write(text)
 print(text)
sys.exit(p.returncode)
