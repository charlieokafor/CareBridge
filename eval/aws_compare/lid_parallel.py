import sys, time, wave, json
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,'/opt/cb-dev')
from aws_transcribe import transcribe_pcm
meta=json.load(open('/opt/cb-dev/lidmeta.json'))
OPTS={"en":"en-IE","uk":"uk-UA","ru":"ru-RU","pl":"pl-PL","ro":"ro-RO","ar":"ar-SA","fr":"fr-FR","de":"de-DE","hi":"hi-IN","ko":"ko-KR","es":"es-ES"}
out={}
def tx(pcm, c):
    for a in range(6):
        try: return transcribe_pcm(pcm, language_code=OPTS[c])
        except Exception as e:
            if "Limit" not in str(e) or a == 5: raise
            time.sleep(2 + a * 2)

def one(k):
    pcm=wave.open(f'/opt/cb-dev/lid/{k}.wav').readframes(10**8); t=time.time()
    with ThreadPoolExecutor(len(OPTS)) as ex:
        res=dict(zip(OPTS, ex.map(lambda c: tx(pcm, c), OPTS)))
    secs=time.time()-t
    return k, {c:{'conf':r['confidence'],'n':len(r['words']),'text':r['text']} for c,r in res.items()}, secs
with ThreadPoolExecutor(1) as ex:
    for k,res,secs in ex.map(one, sorted(meta)):
        out[k]={'res':res,'secs':round(secs,2)}
        best=max(res, key=lambda c:(res[c]['conf'] or 0))
        print(k, meta[k]['lang'], '->', best, round(res[best]['conf'] or 0,3), f'{secs:.1f}s', flush=True)
json.dump(out, open('/opt/cb-dev/lid_parallel.json','w'), ensure_ascii=False)
