# backend 가상환경 생성

python 3.12.x 버전의 가상환경 생성

```bash
py -3.12 -m venv .venv
```

가상환경 활성화

```bash
.venv\Scripts\activate
```

python 패키지(pip, setuptools, wheel) 업데이트

```bash
python -m pip install --upgrade pip setuptools wheel
```

가상환경 내 requirements.txt 패키지 설치 (가상환경 활성화된 상태에서!)

```bash
python -m pip install -r requirements.txt
```

(.venv) D:\개발\1_ImageProcessingTool\ImageProcessingAPI\backend>python -m pytest -q

====================================================================== ERRORS ======================================================================
_______________________________________________ ERROR collecting tests/test_evaluation_job_queue.py ________________________________________________
ImportError while importing test module 'D:\개발\1_ImageProcessingTool\ImageProcessingAPI\backend\tests\test_evaluation_job_queue.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
C:\Users\10007166\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
D:\개발\1_ImageProcessingTool\ImageProcessingAPI\tests\test_evaluation_job_queue.py:9: in <module>
    ???
E   ImportError: cannot import name 'EvaluationActiveError' from 'src.evaluation' (D:\개발\1_ImageProcessingTool\ImageProcessingAPI\backend\src\evaluation\__init__.py)
================================================================= warnings summary =================================================================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\개발\1_ImageProcessingTool\ImageProcessingAPI\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv\Lib\site-packages\starlette\testclient.py:53
  D:\개발\1_ImageProcessingTool\ImageProcessingAPI\backend\.venv\Lib\site-packages\starlette\testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
============================================================= short test summary info ==============================================================
ERROR tests/test_evaluation_job_queue.py
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
2 warnings, 1 error in 2.50s