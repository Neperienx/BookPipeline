import time
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


class TextGenerator:
    def __init__(
        self,
        model_path: str = r"C:\Users\nicol\Documents\01_Code\models\dolphin-2.6-mistral-7b",
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_new_tokens: int = 200,
        seed: int = 42,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_new_tokens = max_new_tokens
        self.seed = seed

        # Seed CPU (+ all GPUs if present)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            quantization_config=bnb_cfg,
            torch_dtype="auto",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    def _generate(self, prompt: str):
        enc = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        out = self.model.generate(
            **enc,
            max_new_tokens=self.max_new_tokens,
            do_sample=True,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        _elapsed = time.perf_counter() - t0
        return enc, out

    def generate_text(self, prompt: str) -> str:
        _enc, out = self._generate(prompt)
        text = self.tokenizer.decode(out[0], skip_special_tokens=True)
        return text.strip()

    def generate_response(self, prompt: str) -> str:
        enc, out = self._generate(prompt)
        prompt_len = enc["input_ids"].shape[-1]
        generated_ids = out[0, prompt_len:]
        if generated_ids.numel() == 0:
            return ""
        response_text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
        return response_text.strip()
