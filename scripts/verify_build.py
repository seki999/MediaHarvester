"""Verify packaged production bytecode matches the current working-tree source."""
import argparse
import hashlib
import json
import marshal
import types
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader
ROOT=Path(__file__).resolve().parents[1]


def normalize(code):
    constants=tuple(normalize(c) if isinstance(c,types.CodeType) else c for c in code.co_consts)
    return code.replace(co_filename='',co_consts=constants)


def fingerprint(code):
    return hashlib.sha256(marshal.dumps(normalize(code),0)).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    reader=CArchiveReader(str(args.exe.resolve()));archive=reader.open_embedded_archive('PYZ.pyz')
    rows=[]
    for source in sorted((ROOT/'mediaharvester').glob('*.py')):
        name='mediaharvester' if source.stem=='__init__' else 'mediaharvester.'+source.stem
        original=compile(source.read_bytes(),str(source),'exec',optimize=0)
        packaged=archive.extract(name)
        expected=fingerprint(original);actual=fingerprint(packaged)
        rows.append({'module':name,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                     'bytecode_sha256':actual,'status':'PASS' if expected==actual else 'FAIL'})
    result={'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',
            'exe':str(args.exe.resolve()),'exe_sha256':hashlib.sha256(args.exe.read_bytes()).hexdigest(),'modules':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Packaged source comparison: '+result['status'])
    return int(result['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
