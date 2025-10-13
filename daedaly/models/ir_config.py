from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    what_gpt_use = fields.Selection([
        ('openai', 'OpenAI'),
        ('gemini', 'Gemini'),
        ('deepseek', 'DeepSeek'),
        ('local', 'Local Gateway'),
    ],  default='gemini', string="What GPT to use", config_parameter="daedaly.what_gpt_use")

    openai_key = fields.Char(string="OpenAI Key", config_parameter="daedaly.openai_key")
    gemini_key = fields.Char(string="Gemini Key", config_parameter="daedaly.gemini_key")
    gemini_model = fields.Char(
        string="Gemini Model",
        config_parameter="daedaly.gemini_model",
        default='models/gemini-flash-latest',
        help="Identificativo del modello Gemini, es. models/gemini-flash-latest."
    )
    deepseek_key = fields.Char(string="DeepSeek Key", config_parameter="daedaly.deepseek_key")
    deepseek_model = fields.Char(
        string="DeepSeek Model",
        config_parameter="daedaly.deepseek_model",
        default='deepseek-chat',
        help="Identificativo del modello DeepSeek, es. deepseek-chat o deepseek-coder."
    )
    local_gateway_url = fields.Char(
        string="Local Gateway URL",
        config_parameter="daedaly.local_gateway_url",
        default='http://localhost:11434/api/generate',
        help="Endpoint REST del gateway locale (es. Ollama: http://localhost:11434/api/generate)."
    )
    local_model_name = fields.Char(
        string="Local Model Name",
        config_parameter="daedaly.local_model_name",
        default='llama3',
        help="Nome del modello servito dal gateway locale (es. ollama run llama3)."
    )
    local_extra_headers = fields.Char(
        string="Local Gateway Headers (JSON)",
        config_parameter="daedaly.local_extra_headers",
        help="Intestazioni extra in formato JSON da includere nella chiamata al gateway locale."
    )

    def action_open_test_api_connection(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'daedaly.test_api_connection',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_check_api_credit(self):
        config = self.env['ir.config_parameter'].sudo()
        model_used = config.get_param('daedaly.what_gpt_use')
        msg = ""
        if model_used == 'openai':
            key = config.get_param('daedaly.openai_key')
            if not key:
                msg = "❌ Nessuna chiave OpenAI configurata."
            else:
                try:
                    try:
                        from openai import OpenAI  # type: ignore
                        client = OpenAI(api_key=key)
                        resp = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": "ping"}],
                            max_tokens=1,
                            temperature=0,
                        )
                        _ = resp.id
                        msg = "✅ Credito API OpenAI attivo (chiamata minima riuscita)."
                    except ImportError:
                        import openai  # type: ignore
                        openai.api_key = key
                        resp = openai.ChatCompletion.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": "ping"}],
                            max_tokens=1,
                            temperature=0,
                        )
                        _ = resp.get('id')
                        msg = "✅ Credito API OpenAI attivo (SDK legacy)."
                except Exception as e:
                    text = str(e)
                    if 'insufficient_quota' in text or 'quota' in text or 'RateLimitError' in text:
                        msg = f"❌ Nessun credito API OpenAI: {text}"
                    else:
                        msg = f"❌ Errore chiamando OpenAI: {text}"
        elif model_used == 'gemini':
            key = config.get_param('daedaly.gemini_key')
            if not key:
                msg = "❌ Nessuna chiave Gemini configurata."
            else:
                try:
                    try:
                        import google.generativeai as genai  # type: ignore
                    except Exception:
                        raise ImportError("google-generativeai non installato")
                    genai.configure(api_key=key)
                    model_name = config.get_param('daedaly.gemini_model', 'models/gemini-flash-latest') or 'models/gemini-flash-latest'
                    if not model_name.startswith('models/'):
                        model_name = f"models/{model_name}"
                    model = genai.GenerativeModel(model_name)
                    resp = model.generate_content("ping")
                    _ = getattr(resp, 'text', None)
                    msg = "✅ Credito API Gemini attivo (chiamata minima riuscita)."
                except Exception as e:
                    text = str(e)
                    if 'quota' in text.lower() or 'Resource has been exhausted' in text:
                        msg = f"❌ Nessun credito API Gemini: {text}"
                    else:
                        msg = f"❌ Errore chiamando Gemini: {text}"
        elif model_used == 'deepseek':
            key = config.get_param('daedaly.deepseek_key')
            model_name = config.get_param('daedaly.deepseek_model', 'deepseek-chat')
            if not key:
                msg = "❌ Nessuna chiave DeepSeek configurata."
            else:
                try:
                    import requests  # type: ignore
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
                    data = response.json()
                    if not data.get('choices'):
                        raise ValueError(f"Risposta senza choices: {data}")
                    msg = "✅ Credito API DeepSeek attivo (chiamata minima riuscita)."
                except Exception as e:
                    text = str(e)
                    if 'quota' in text.lower():
                        msg = f"❌ Nessun credito API DeepSeek: {text}"
                    else:
                        msg = f"❌ Errore chiamando DeepSeek: {text}"
        elif model_used == 'local':
            url = (config.get_param('daedaly.local_gateway_url', 'http://localhost:11434/api/generate') or '').strip()
            model_name = (config.get_param('daedaly.local_model_name', 'llama3') or '').strip()
            headers_json = config.get_param('daedaly.local_extra_headers', '')
            if requests is None:
                msg = "❌ Gateway locale non raggiungibile: libreria requests mancante."
            elif not url:
                msg = "❌ Gateway locale non configurato."
            elif not model_name:
                msg = "❌ Nome del modello locale non configurato."
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
                        msg = f"❌ Intestazioni aggiuntive non valide: {str(e)}"
                    else:
                        msg = ""
                if msg == "":
                    try:
                        response = requests.post(
                            url,
                            headers=headers,
                            json={
                                "model": model_name,
                                "prompt": "ping",
                                "stream": False,
                            },
                            timeout=30,
                        )
                        response.raise_for_status()
                        msg = "✅ Gateway locale raggiungibile."
                    except Exception as e:
                        msg = f"❌ Errore chiamando il gateway locale: {str(e)}"
        else:
            msg = "⚠ Nessun modello selezionato nelle impostazioni."

        wiz = self.env['daedaly.test_api_connection'].create({'test_result': msg})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'daedaly.test_api_connection',
            'view_mode': 'form',
            'res_id': wiz.id,
            'target': 'new',
        }
