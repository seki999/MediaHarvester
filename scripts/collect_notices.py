"""Retain the exact installed runtime packages' license texts for distribution."""
from importlib.metadata import distribution,PackageNotFoundError
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
output=root/'licenses'; output.mkdir(exist_ok=True)
packages=['PySide6','PySide6_Essentials','PySide6_Addons','shiboken6','yt-dlp','httpx','httpcore',
          'beautifulsoup4','lxml','Pillow','certifi','idna','h11','anyio','soupsieve','typing_extensions','curl_cffi','cffi','pycparser',
          'playwright','greenlet','pyee']
versions=[]
for package in packages:
    try: dist=distribution(package)
    except PackageNotFoundError: continue
    versions.append(f'{package}=={dist.version}')
    count=0
    for entry in dist.files or []:
        if not any(word in entry.name.upper() for word in ('LICENSE','LICENCE','COPYING','NOTICE')) and 'licenses' not in str(entry).lower():
            continue
        source=Path(dist.locate_file(entry))
        if source.is_file():
            target=output/package/f'{count:02d}-{source.name}'
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(source,target); count+=1
(output/'versions.txt').write_text('\n'.join(versions)+'\n','utf-8')
print(f'Runtime license texts copied to {output}')
