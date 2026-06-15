import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

class LocalLlamaInference:
    def __init__(self, model_id: str = "meta-llama/Llama-3.3-70B-Instruct"):
        self.model_id = model_id
        self.hf_token = os.environ.get("HF_TOKEN")
        
        self.quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        )

        gpu_count = torch.cuda.device_count()
        self.max_memory = {i: "28GiB" for i in range(gpu_count)}
        if 0 in self.max_memory:
            self.max_memory[0] = "18GiB"

        print(f"Loading model {model_id} on {gpu_count} GPUs...")
        
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id, token=self.hf_token, use_fast=True
        )
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            quantization_config=self.quant_config,
            torch_dtype=torch.float16,
            token=self.hf_token,
            max_memory=self.max_memory,
            attn_implementation="sdpa"
        )

    def generate_json(self, system_msg: str, user_msg: str) -> str:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
        
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        if inputs.input_ids.shape[1] > 15000:
            inputs.input_ids = inputs.input_ids[:, -15000:]

        with torch.inference_mode():
            output = self.model.generate(
                **inputs,
                max_new_tokens=2500,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id
            )

        new_tokens = output[0, inputs.input_ids.shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()