import os
import requests
from typing import Optional, Dict, Any

class DeepSeekAPI:
    def __init__(self):
        self.base_url = os.getenv("DEEPSEEK_API_BASE_URL")
        self.api_key = os.getenv("DEEPSEEK_API_KEY")

    def get_analysis(self, prompt: str, model: str = "deepseek-ai/DeepSeek-V3", stop=None, top_k=50, frequency_penalty=0.5, n=1, tools=None) -> Dict[str, Any]:
        """
        获取AI对当前局势的分析
        :param prompt: 分析提示词
        :param model: 使用的模型
        """
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 2048,
            "stop": stop,
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": top_k,
            "frequency_penalty": frequency_penalty,
            "n": n,
            "response_format": {"type": "text"},
            "tools": tools
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API请求失败: {str(e)}")
            return {"error": str(e)}

    def format_response(self, response: Dict[str, Any]) -> str:
        """
        格式化API响应结果
        """
        if "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0]["message"]["content"]
        return "未收到有效响应"