import os
import subprocess
import sys
import pytest
from mediaharvester.processes import attach_job,release_job


@pytest.mark.skipif(os.name!='nt',reason='Windows Job Object lifecycle')
def test_already_exited_child_does_not_fail_verification():
    proc=subprocess.Popen([sys.executable,'-c','pass'])
    proc.wait(timeout=5)
    attach_job(proc)
    release_job(proc)
    assert proc.returncode==0
