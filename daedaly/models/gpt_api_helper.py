from odoo import models
from odoo.exceptions import UserError
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None
try:
    import requests  # type: ignore
except Exception:
    requests = None


class GPTAPIHelper(models.AbstractModel):
    _name = 'daedaly.gpt_api_helper'
    _description = 'GPT API Helper for Daedaly'

    def get_config(self):
        icp = self.env['ir.config_parameter'].sudo()
        return {
            'model': icp.get_param('daedaly.what_gpt_use', 'openai'),
            'openai_key': icp.get_param('daedaly.openai_key', ''),
            'gemini_key': icp.get_param('daedaly.gemini_key', ''),
            'gemini_model': icp.get_param('daedaly.gemini_model', 'models/gemini-flash-latest'),
            'deepseek_key': icp.get_param('daedaly.deepseek_key', ''),
            'deepseek_model': icp.get_param('daedaly.deepseek_model', 'deepseek-chat'),
            'local_gateway_url': icp.get_param('daedaly.local_gateway_url', 'http://localhost:11434/api/generate'),
            'local_model_name': icp.get_param('daedaly.local_model_name', 'llama3'),
            'local_extra_headers': icp.get_param('daedaly.local_extra_headers', ''),
        }

    def chat(self, prompt):
        config = self.get_config()
        model = config['model']

        if model == 'openai':
            return self._chat_openai(prompt, config['openai_key'])
        elif model == 'gemini':
            return self._chat_gemini(prompt, config['gemini_key'], config['gemini_model'])
        elif model == 'deepseek':
            return self._chat_deepseek(prompt, config['deepseek_key'], config['deepseek_model'])
        elif model == 'local':
            return self._chat_local(prompt, config['local_gateway_url'], config['local_model_name'], config['local_extra_headers'])
        else:
            raise UserError("Nessun modello GPT configurato nelle impostazioni Daedaly.")

    def _chat_openai(self, prompt, key):
        default_model = "gpt-4o-mini"
        try:
            try:
                from openai import OpenAI  # SDK >= 1.0
                client = OpenAI(api_key=key)
                resp = client.chat.completions.create(
                    model=default_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return str(resp.choices[0].message.content)
            except ImportError:
                import openai  # type: ignore
                openai.api_key = key
                resp = openai.ChatCompletion.create(
                    model=default_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                return resp['choices'][0]['message']['content']
        except Exception as e:
            raise UserError(f"OpenAI Error: {str(e)}")

    def _chat_gemini(self, prompt, key, model_name):
        try:
            if genai is None:
                raise ImportError("google-generativeai not installed")
            if not key:
                raise UserError("Gemini API key non configurata.")
            genai.configure(api_key=key)
            model_name = model_name or 'models/gemini-flash-latest'
            if not model_name.startswith('models/'):
                model_name = f"models/{model_name}"
            model = genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(prompt)
            if hasattr(response, 'text') and response.text:
                return response.text
            # Some SDK versions return candidates instead of text
            candidates = getattr(response, 'candidates', []) or []
            for candidate in candidates:
                content = getattr(candidate, 'content', None)
                if not content:
                    continue
                parts = getattr(content, 'parts', []) or []
                texts = [getattr(part, 'text', '') for part in parts if getattr(part, 'text', '')]
                if texts:
                    return "\n".join(texts)
            raise UserError("Gemini non ha restituito contenuti testuali.")
        except Exception as e:
            raise UserError(f"Gemini Error: {str(e)}")

    def _chat_deepseek(self, prompt, key, model_name):
        if not key:
            raise UserError("DeepSeek API key non configurata.")
        if requests is None:
            raise UserError("La libreria 'requests' non è disponibile per le chiamate DeepSeek.")
        model_name = (model_name or 'deepseek-chat').strip() or 'deepseek-chat'
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            choices = data.get('choices') or []
            if not choices:
                raise UserError(f"DeepSeek Error: risposta senza scelte valide ({data})")
            message = choices[0].get('message', {})
            content = message.get('content')
            if not content:
                raise UserError(f"DeepSeek Error: nessun contenuto nella risposta ({message})")
            return content
        except Exception as e:
            raise UserError(f"DeepSeek Error: {str(e)}")

    def _chat_local(self, prompt, url, model_name, extra_headers_json):
        if requests is None:
            raise UserError("La libreria 'requests' non è disponibile per le chiamate al gateway locale.")
        url = (url or '').strip()
        if not url:
            raise UserError("URL del gateway locale non configurato.")
        model_name = (model_name or '').strip()
        if not model_name:
            raise UserError("Nome del modello locale non configurato.")
        headers = {"Content-Type": "application/json"}
        if extra_headers_json:
            import json
            try:
                extra = json.loads(extra_headers_json)
                if not isinstance(extra, dict):
                    raise ValueError("Il valore non è un oggetto JSON.")
                headers.update({str(k): str(v) for k, v in extra.items()})
            except Exception as e:
                raise UserError(f"Local Gateway headers non validi: {str(e)}")

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                # Ollama format: {"response": "...", "done": true}
                if data.get('response'):
                    return data['response']
                # text-generation-inference format: {"output": {"text": "..."}}
                output = data.get('output')
                if isinstance(output, dict) and output.get('text'):
                    return output['text']
                if data.get('choices'):
                    # openai-compatible local endpoints
                    message = data['choices'][0].get('message', {})
                    content = message.get('content')
                    if content:
                        return content
            raise UserError(f"Risposta non riconosciuta dal gateway locale: {data}")
        except Exception as e:
            raise UserError(f"Local Gateway Error: {str(e)}")
