import json, io, time
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
meta=json.load(open('/opt/cb-dev/lidmeta.json'))
CANDS={"en":"en","uk":"uk","ru":"ru","pl":"pl","ro":"ro","ar":"ar","fr":"fr","de":"de","hi":"hi","ko":"ko","es":"es"}
base=WhisperModel('base',device='cpu',compute_type='int8',cpu_threads=2,download_root='/opt/carebridge/models/whisper')
small=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=2,download_root='/opt/carebridge/models/whisper')
out={}
for k in sorted(meta):
    a=decode_audio(f'/opt/cb-dev/lid/{k}.wav', sampling_rate=16000); t=time.time()
    res={}
    for name,m in (('base',base),('small',small)):
        _,_,probs=m.detect_language(a)
        p={l:v for l,v in probs if l in CANDS}; tot=sum(p.values()) or 1
        res[name]={l:round(v/tot,4) for l,v in sorted(p.items(), key=lambda x:-x[1])}
    out[k]=res; out[k]['secs']=round(time.time()-t,2)
json.dump(out, open('/opt/cb-dev/whisper_detect.json','w')); print('done', len(out))
