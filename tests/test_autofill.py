from story_builder.autofill import AutofillService

class DummyVar:
    def __init__(self, val): self._val = val
    def get(self): return self._val

def test_autofill_stub_mode():
    service = AutofillService(stub_mode_var=DummyVar(True))
    out = service.generate("test prompt")
    assert isinstance(out, str)
    assert len(out) == 4  # stub returns 4 chars
