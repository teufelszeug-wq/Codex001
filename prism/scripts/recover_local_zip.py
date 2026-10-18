"""Recover verified local ZIP entries without asserting archive completeness."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zlib

def recover(source, output, max_entry=64*1024*1024, max_total=1024*1024*1024):
    source=Path(source); output=Path(output)
    data=source.read_bytes(); offset=0; entries=[]; seen=set(); total=0
    output.mkdir(parents=True,exist_ok=True)
    stop=None
    while offset<len(data):
        if data[offset:offset+4]!=b'PK\x03\x04':
            stop='NON_LOCAL_RECORD';break
        if len(data)-offset<30:
            stop='TRUNCATED_HEADER';break
        h=struct.unpack_from('<IHHHHHIIIHH',data,offset)
        flags,method,crc,packed,size,nlen,elen=h[2],h[3],h[6],h[7],h[8],h[9],h[10]
        begin=offset+30+nlen+elen; end=begin+packed
        if end>len(data):stop='TRUNCATED_ENTRY';break
        if flags&9 or method not in (0,8):stop='UNSUPPORTED_ENTRY';break
        name=data[offset+30:offset+30+nlen].decode('utf-8' if flags&0x800 else 'cp437')
        parts=PurePosixPath(name)
        if not name or parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
            raise ValueError('unsafe member path')
        target=output/name
        if not target.resolve().is_relative_to(output.resolve()):raise ValueError('path escape')
        if name in seen:raise ValueError('duplicate member')
        seen.add(name)
        if size>max_entry or total+size>max_total:raise ValueError('recovery size limit')
        payload=data[begin:end]
        if method==8:
            dec=zlib.decompressobj(-15); raw=dec.decompress(payload,size+1)
            if not dec.eof or dec.unused_data or dec.unconsumed_tail:raise ValueError('invalid deflate member')
        else:raw=payload
        if len(raw)!=size or zlib.crc32(raw)&0xffffffff!=crc:raise ValueError('member integrity failure')
        if name.endswith('/'):
            target.mkdir(parents=True,exist_ok=True)
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=raw:raise ValueError('refuse overwrite')
            if not target.exists():target.write_bytes(raw)
        entries.append({'path':name,'size':size,'sha256':hashlib.sha256(raw).hexdigest()})
        total+=size;offset=end
    return {'source_sha256':hashlib.sha256(data).hexdigest(),'source_bytes':len(data),
            'verified_entries':len(entries),'verified_bytes':total,'consumed_bytes':offset,
            'stop':stop or 'EOF_AFTER_LOCAL_ENTRY','archive_complete':False,
            'verification':'Local CRC32 and length only; no central-directory completeness claim',
            'entries':entries}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--report',required=True)
    args=p.parse_args();report=recover(args.source,args.output)
    Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='entries'},ensure_ascii=False))
