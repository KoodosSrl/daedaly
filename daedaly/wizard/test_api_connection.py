from odoo import models, fields, api
try:
    import google.generativeai as genai  # type: ignore
except Exception:
    genai = None  # Loaded lazily; handle absence in method
try:
    import requests  # type: ignore
except Exception:
    requests = None


class TestAPIConnection(models.TransientModel):
    _name = 'daedaly.test_api_connection'
    _description = 'Test API Connection Wizard'

    test_result = fields.Text(string="Test Result", readonly=True)

    def _run_test(self):
        config = self.env['ir.config_parameter'].sudo()
        model_used = config.get_param('daedaly.what_gpt_use')
        result = ""

        if model_used == 'openai':
            key = config.get_param('daedaly.openai_key')
            try:
                try:
                    from openai import OpenAI  # type: ignore
                    client = OpenAI(api_key=key)
                    _ = client.models.list()
                    result = "✅ OpenAI API connection successful (SDK >= 1.0)."
                except ImportError:
                    import openai  # type: ignore
                    openai.api_key = key
                    openai.Model.list()
                    result = "✅ OpenAI API connection successful (legacy SDK)."
            except Exception as e:
                result = f"❌ OpenAI connection failed: {str(e)}"
        elif model_used == 'gemini':
            key = config.get_param('daedaly.gemini_key')
            try:
                if genai is None:
                    raise ImportError("google-generativeai not installed")
                genai.configure(api_key=key)
                _ = list(genai.list_models())
                result = "✅ Gemini API connection successful."
            except Exception as e:
                result = f"❌ Gemini connection failed: {str(e)}"
        elif model_used == 'deepseek':
            key = config.get_param('daedaly.deepseek_key')
            model_name = config.get_param('daedaly.deepseek_model', 'deepseek-chat')
            if not key:
                result = "❌ DeepSeek connection failed: chiave API mancante."
            elif requests is None:
                result = "❌ DeepSeek connection failed: libreria requests non disponibile."
            else:
                try:
                    response = requests.post(
                        "https://api.deepseek.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name or 'deepseek-chat',
                            "messages": [{"role": "user", "content": "ping"}],
                            "max_tokens": 4,
                            "temperature": 0,
                            "stream": False,
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    result = "✅ DeepSeek API connection successful."
                except Exception as e:
                    result = f"❌ DeepSeek connection failed: {str(e)}"
        elif model_used == 'local':
            url = config.get_param('daedaly.local_gateway_url', 'http://localhost:11434/api/generate')
            model_name = config.get_param('daedaly.local_model_name', 'llama3')
            headers_json = config.get_param('daedaly.local_extra_headers', '')
            if requests is None:
                result = "❌ Local gateway connection failed: libreria requests non disponibile."
            else:
                headers = {"Content-Type": "application/json"}
                if headers_json:
                    import json
                    try:
                        extra = json.loads(headers_json)
                        if not isinstance(extra, dict):
                            raise ValueError("Il valore non è un oggetto JSON.")
                        headers.update({str(k): str(v) for k, v in extra.items()})
                    except Exception as e:
                        result = f"❌ Local gateway headers non validi: {str(e)}"
                try:
                    response = requests.post(
                        (url or '').strip(),
                        headers=headers,
                        json={
                            "model": (model_name or '').strip() or 'llama3',
                            "prompt": "ping",
                            "stream": False,
                        },
                        timeout=30,
                    )
                    response.raise_for_status()
                    result = "✅ Local gateway connection successful."
                except Exception as e:
                    result = f"❌ Local gateway connection failed: {str(e)}"
        else:
            result = "⚠ No GPT model configured."

        return result

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'test_result' in fields_list:
            res['test_result'] = self._run_test()
        else:
            res['test_result'] = self._run_test()
        return res

    def test_connection(self):
        self.test_result = self._run_test()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'daedaly.test_api_connection',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
