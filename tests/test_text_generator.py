import types
import torch
import src.text_generator as tg


# ---- Test Doubles (Fakes) ----

class _FakeBatch(dict):
    """Mimics a Hugging Face BatchEncoding object returned by a tokenizer.
    Provides a `.to(device)` method so it behaves like real HF batches.
    """
    def to(self, device):
        return self


class FakeTokenizer:
    """Fake tokenizer to avoid loading a real pretrained tokenizer."""

    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        # Pretend we "loaded" a tokenizer from disk
        return cls()

    def __call__(self, prompt, return_tensors="pt"):
        # Simulates turning text into token IDs
        assert return_tensors == "pt"
        return _FakeBatch({"input_ids": torch.tensor([[1, 2, 3]])})

    def decode(self, ids, skip_special_tokens=True):
        # Simulates converting generated tokens back into text
        return "hello world"


class FakeModel:
    """Fake language model to capture `generate()` calls."""

    def __init__(self):
        self.device = torch.device("cpu")
        self.last_generate_kwargs = None  # stores arguments for assertions

    @classmethod
    def from_pretrained(cls, *_args, **_kwargs):
        # Pretend we "loaded" a model from disk
        return cls()

    def generate(self, **kwargs):
        # Save call arguments so tests can check them later
        self.last_generate_kwargs = kwargs
        inp = kwargs["input_ids"]
        # Pretend the model generated 2 extra tokens
        return torch.tensor([[1, 2, 3, 4, 5]])


# ---- Tests ----

def test_init_sets_seed_and_loads(monkeypatch):
    """Test that TextGenerator:
    - sets the random seed,
    - loads the model and tokenizer correctly.
    """

    recorded = {}

    # Replace torch.manual_seed with our fake version that records the seed
    def fake_manual_seed(s):
        recorded["cpu_seed"] = s

    # Monkeypatch HuggingFace classes to use our fakes
    monkeypatch.setattr(tg, "AutoModelForCausalLM",
                        types.SimpleNamespace(from_pretrained=FakeModel.from_pretrained))
    monkeypatch.setattr(tg, "AutoTokenizer",
                        types.SimpleNamespace(from_pretrained=FakeTokenizer.from_pretrained))
    monkeypatch.setattr(torch, "manual_seed", fake_manual_seed)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    # Instantiate generator (this should call our fakes)
    gen = tg.TextGenerator("dummy/path", seed=123)

    # Verify that the seed was set
    assert recorded["cpu_seed"] == 123
    # Verify that model and tokenizer were loaded correctly
    assert isinstance(gen.model, FakeModel)
    assert isinstance(gen.tokenizer, FakeTokenizer)


def test_generate_uses_sampling(monkeypatch):
    """Test that TextGenerator.generate_text():
    - calls the model with correct sampling parameters,
    - returns decoded text.
    """

    # Replace HuggingFace classes with fakes again
    monkeypatch.setattr(tg, "AutoModelForCausalLM",
                        types.SimpleNamespace(from_pretrained=FakeModel.from_pretrained))
    monkeypatch.setattr(tg, "AutoTokenizer",
                        types.SimpleNamespace(from_pretrained=FakeTokenizer.from_pretrained))
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)

    # Create generator with specific sampling settings
    gen = tg.TextGenerator("dummy/path",
                           temperature=0.7,
                           top_p=0.9,
                           max_new_tokens=10)

    # Call text generation
    text = gen.generate_text("hi")

    # The fake tokenizer always decodes to "hello world"
    assert text == "hello world"

    # Inspect arguments passed to FakeModel.generate()
    kwargs = gen.model.last_generate_kwargs
    assert kwargs["max_new_tokens"] == 10
    assert kwargs["do_sample"] is True       # ensures sampling mode is used
    assert kwargs["temperature"] == 0.7
    assert kwargs["top_p"] == 0.9

def test_real_model_generation():
    """Integration test:
    Load the real model and check that generated text is valid.
    """

    # ⚠️ This will be slow and require a lot of RAM/VRAM
    model_path = r"C:\Users\nicol\Documents\01_Code\models\dolphin-2.6-mistral-7b"

    # Create generator with a small token limit so the test is fast
    gen = tg.TextGenerator(model_path, max_new_tokens=20)

    # Generate text from a simple prompt
    prompt = "Once upon a time"
    output = gen.generate_text(prompt)

    # Basic sanity checks
    assert isinstance(output, str)            # must be a string
    assert len(output.strip()) > 0            # must not be empty
    assert len(output.split()) <= 25          # crude check: <= max tokens + prompt length