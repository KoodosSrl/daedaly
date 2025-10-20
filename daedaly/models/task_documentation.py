from odoo import models, fields
from odoo.exceptions import UserError
import base64

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


class TaskDocumentation(models.Model):
    _name = 'task.documentation'
    _description = 'Task Documentation'

    name = fields.Char(string='Document Description', required=True)
    filename = fields.Char(string='File Name')
    file = fields.Binary(string='File', required=True)
    doc_date = fields.Date(string='Date', required=True)
    task_id = fields.Many2one('project.task', string='Task', ondelete='cascade')


class ProjectTask(models.Model):
    _inherit = 'project.task'

    documentation_ids = fields.One2many('task.documentation', 'task_id', string='Documentations')
    todo_html = fields.Html(string='To Do', sanitize=True)

    def _extract_text_from_pdf(self, binary_data):
        try:
            if fitz is None:
                return "PyMuPDF (fitz) non installato: impossibile leggere PDF"
            pdf_content = base64.b64decode(binary_data)
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    def _build_task_docs_context(self):
        text = ""
        for doc in self.documentation_ids:
            content = self._extract_text_from_pdf(doc.file)
            text += f"\nDocumento task data: {doc.doc_date}, chiamato: {doc.name}\nContenuto:\n{content}\n"
        return text

    def _render_assignee_profiles(self):
        """Return a textual summary of the assignee profiles to guide AI prompts."""
        self.ensure_one()
        users = self.user_ids
        if self.user_id:
            users |= self.user_id
        employees = users.mapped('employee_id')
        lines = []
        seen = set()
        for employee in employees:
            if not employee or employee.id in seen:
                continue
            seen.add(employee.id)
            contact_bits = []
            if employee.work_email:
                contact_bits.append(f"email: {employee.work_email}")
            if employee.work_phone:
                contact_bits.append(f"tel: {employee.work_phone}")
            if employee.mobile_phone:
                contact_bits.append(f"mobile: {employee.mobile_phone}")
            if employee.user_id and employee.user_id.login:
                contact_bits.append(f"login: {employee.user_id.login}")
            contact_info = f" ({', '.join(contact_bits)})" if contact_bits else ""
            lines.append(f"- {employee.display_name}{contact_info}")
            profile_text = (employee.progett_ai_description or '').strip()
            if profile_text:
                lines.append(f"  Profilo professionale:\n{profile_text}")
            else:
                lines.append("  Profilo professionale: nessuna descrizione fornita.")
        return "\n".join(lines)

    def action_task_smart_description(self):
        for task in self:
            context_docs = task._build_task_docs_context()
            assignee_profiles = task._render_assignee_profiles()
            prompt = (
                "Sei un project manager senior. In base alla descrizione attuale della task e ai documenti allegati, "
                "scrivi una DESCRIZIONE SOMMARIA e generale della task (non un verbale). La descrizione deve chiarire obiettivo, contesto, criteri di accettazione, dipendenze e rischi. "
                "Tono chiaro e sintetico (5–8 frasi).\n\n"
                "RESTITUISCI SOLO JSON VALIDO, senza backticks e senza testo extra, con struttura ESATTA:\n"
                "{\n"
                "  \"description\": \"testo descrittivo della task\"\n"
                "}\n\n"
            )
            if assignee_profiles:
                prompt += (
                    "Profilo dell'assegnatario (adatta tono, livello di dettaglio e focus tecnico a queste competenze):\n"
                    f"{assignee_profiles}\n\n"
                )
            else:
                prompt += (
                    "Non è disponibile un profilo dell'assegnatario; fornisci indicazioni comprensibili anche a un team multidisciplinare.\n\n"
                )
            prompt += f"Descrizione attuale task:\n{task.description or ''}\n\nDocumenti:\n{context_docs}"
            text = self.env['daedaly.gpt_api_helper'].chat(prompt)
            try:
                import json, re
                block = re.search(r"\{[\s\S]*\}$", (text or '').strip())
                data = json.loads(block.group(0)) if block else {"description": text or ''}
            except Exception:
                data = {"description": text or ''}
            task.description = data.get('description', task.description)

    def action_task_smart_todo(self):
        for task in self:
            context_docs = task._build_task_docs_context()
            assignee_profiles = task._render_assignee_profiles()
            prompt = (
                "Agisci come un team lead. Genera una lista di passi operativi (breve, azionabile, in ordine logico) per completare la task. "
                "Restituisci SOLO JSON valido con struttura esatta: {\"items\": [\"step 1\", \"step 2\"]}. Nessun testo extra.\n\n"
            )
            if assignee_profiles:
                prompt += (
                    "Adatta il livello di dettaglio e l'ordine delle azioni alle competenze dell'assegnatario indicato di seguito:\n"
                    f"{assignee_profiles}\n\n"
                )
            else:
                prompt += (
                    "Non è disponibile un profilo dell'assegnatario; proponi passi chiari e autoconclusivi adatti a un team eterogeneo.\n\n"
                )
            prompt += f"Descrizione task:\n{task.description or ''}\n\nDocumenti:\n{context_docs}\n\n"
            text = self.env['daedaly.gpt_api_helper'].chat(prompt) or ''
            import json, re
            items = []
            raw_json = None
            fenced = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
            if fenced:
                raw_json = fenced.group(1)
            else:
                start = text.find('{')
                end = text.rfind('}')
                if start != -1 and end != -1 and end > start:
                    raw_json = text[start:end+1]
            try:
                if raw_json:
                    data = json.loads(raw_json)
                else:
                    data = json.loads(text)
                if isinstance(data, dict):
                    items = data.get('items', []) or []
            except Exception:
                items = [i.strip('- •\u2022 ') for i in text.splitlines() if i.strip() and not i.strip().startswith('```')]
            if items:
                lis = []
                for i in items:
                    lis.append(f'<li>{i}</li>')
                task.todo_html = '<ul class="o_todo_list">' + ''.join(lis) + '</ul>'
            else:
                task.todo_html = ''
