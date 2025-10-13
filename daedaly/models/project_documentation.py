from odoo import models, fields
from odoo.exceptions import UserError
import base64
import logging
import html as _html
import unicodedata
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None
import json
try:
    import requests
except Exception:
    requests = None


class ProjectDocumentation(models.Model):
    _name = 'project.documentation'
    _description = 'Project Documentation'

    name = fields.Char(string='Document Description', required=True)
    filename = fields.Char(string='File Name')
    file = fields.Binary(string='File', required=True)
    doc_date = fields.Date(string='Date', required=True)
    project_id = fields.Many2one('project.project', string='Project', ondelete='cascade')


class ResCompany(models.Model):
    _inherit = 'res.company'

    progett_ai_description_file = fields.Binary(
        string='Company Profile (PDF)',
        attachment=True,
        help='Upload a PDF that describes the company for AI-generated analyses.'
    )
    progett_ai_description_filename = fields.Char(string='Company Profile Filename')


class HREmployee(models.Model):
    _inherit = 'hr.employee'

    progett_ai_description = fields.Text(
        string='AI Profile',
        help='Descrizione testuale delle competenze del dipendente usata per suggerire assegnazioni.'
    )


class Project(models.Model):
    _inherit = 'project.project'

    documentation_ids = fields.One2many('project.documentation', 'project_id', string='Documentations')
    pm_framework = fields.Selection([
        ('prince2', 'PRINCE2'),
        ('agile', 'Agile'),
        ('scrum', 'Agile-Scrum'),
        ('lean', 'Lean'),
    ], string='PM Framework')
    economic_notes = fields.Html(string='Note Economiche', sanitize=True)
    criticita = fields.Html(string='Criticità', sanitize=True)
    team_employee_ids = fields.Many2many(
        'hr.employee',
        'project_project_team_employee_rel',
        'project_id',
        'employee_id',
        string='Team',
        help='Dipendenti considerati per l assegnazione automatica delle task.'
    )
    allow_milestones = fields.Boolean(default=True)

    def _extract_text_from_pdf(self, binary_data):
        try:
            if fitz is None:
                return "PyMuPDF (fitz) non installato: impossibile leggere PDF"
            pdf_content = base64.b64decode(binary_data)
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            return f"Error reading PDF: {str(e)}"

    def _to_html(self, value):
        # Normalize any AI value to a safe, simple HTML string
        if value is None:
            return ''
        # If value is already a string, escape to avoid invalid tags
        if isinstance(value, str):
            # strip to avoid huge whitespace, but keep content
            text = value.strip()
            # Avoid trusting arbitrary HTML from AI; escape then wrap
            return f"<p>{_html.escape(text)}</p>" if text else ''
        # If list, render as bullet list
        if isinstance(value, (list, tuple)):
            items = []
            for v in value:
                s = '' if v is None else str(v)
                s = _html.escape(s.strip())
                if s:
                    items.append(f"<li>{s}</li>")
            return f"<ul>{''.join(items)}</ul>" if items else ''
        # Fallback: stringify dict/others safely
        try:
            s = str(value)
        except Exception:
            s = ''
        s = _html.escape(s.strip())
        return f"<p>{s}</p>" if s else ''

    def _get_company_profile_text(self):
        self.ensure_one()
        company = self.company_id
        if company and company.progett_ai_description_file:
            return self._extract_text_from_pdf(company.progett_ai_description_file)
        return ''

    def _get_team_profiles(self):
        self.ensure_one()
        employees = self.team_employee_ids
        if self.user_id and self.user_id.employee_id:
            employees |= self.user_id.employee_id
        profiles = []
        seen = set()
        for employee in employees:
            if employee.id in seen:
                continue
            seen.add(employee.id)
            profile_text = (employee.progett_ai_description or '').strip()
            profiles.append((employee, profile_text))
        return profiles

    def _format_description(self, desc):
        """Render a rich, human friendly project description from AI output."""
        if not desc:
            return ''
        if isinstance(desc, str):
            return desc.strip()
        if isinstance(desc, (list, tuple)):
            lines = []
            for item in desc:
                line = self._format_description(item)
                if line:
                    for sub_line in line.splitlines():
                        lines.append(f"- {sub_line}" if not sub_line.startswith("-") else sub_line)
            return "\n".join(lines)
        if not isinstance(desc, dict):
            return str(desc)

        parts = []
        get = desc.get

        if get('nome_progetto'):
            parts.append(f"Nome progetto: {get('nome_progetto')}")
        if get('obiettivi_prodotto'):
            parts.append(f"Obiettivi del prodotto:\n  {get('obiettivi_prodotto')}")
        if get('framework'):
            parts.append(f"Framework di lavoro: {get('framework')}")

        milestones = get('fasi_milestone') or []
        if milestones:
            lines = ["Fasi e milestone principali:"]
            for milestone in milestones:
                fase = milestone.get('fase')
                target = milestone.get('data_target')
                if fase:
                    label = f"- {fase}"
                    if target:
                        label += f" (target: {target})"
                    lines.append(label)
            parts.append("\n".join(lines))

        struttura_scrum = get('struttura_scrum') or {}
        if struttura_scrum:
            scrum_lines = ["Struttura Scrum:"]
            ruoli = struttura_scrum.get('ruoli') or {}
            if ruoli:
                scrum_lines.append("  Ruoli:")
                label_map = {
                    'product_owner': 'Product Owner',
                    'scrum_master': 'Scrum Master',
                    'team_di_sviluppo': 'Team di sviluppo',
                }
                for key, value in ruoli.items():
                    if value:
                        scrum_lines.append(f"    - {label_map.get(key, key.replace('_', ' ').title())}: {value}")
            backlog = struttura_scrum.get('backlog_e_priorita') or {}
            if backlog:
                scrum_lines.append("  Backlog e priorità:")
                for key, value in backlog.items():
                    if value:
                        scrum_lines.append(f"    - {value}")
            obiettivi = struttura_scrum.get('obiettivi_sprint') or []
            if obiettivi:
                scrum_lines.append("  Obiettivi di sprint:")
                for ob in obiettivi:
                    if ob:
                        scrum_lines.append(f"    - {ob}")
            cerimonie = struttura_scrum.get('cerimonie_chiave') or []
            if cerimonie:
                scrum_lines.append("  Cerimonie chiave:")
                for ce in cerimonie:
                    if ce:
                        scrum_lines.append(f"    - {ce}")
            if struttura_scrum.get('definition_of_done'):
                scrum_lines.append(f"  Definition of Done: {struttura_scrum.get('definition_of_done')}")
            parts.append("\n".join(scrum_lines))

        dipendenze = get('dipendenze_interne_esterne') or {}
        if dipendenze:
            dip_lines = ["Dipendenze e integrazioni:"]
            if dipendenze.get('dipendenze_critiche'):
                dip_lines.append("  Dipendenze critiche:")
                for item in dipendenze['dipendenze_critiche']:
                    if item:
                        dip_lines.append(f"    - {item}")
            if dipendenze.get('integrazioni_esterne'):
                dip_lines.append("  Integrazioni esterne:")
                for item in dipendenze['integrazioni_esterne']:
                    if item:
                        dip_lines.append(f"    - {item}")
            parts.append("\n".join(dip_lines))

        rischi = get('rischi_tecnici_operativi') or []
        if rischi:
            risk_lines = ["Rischi principali:"]
            for risk in rischi:
                if risk:
                    risk_lines.append(f"- {risk}")
            parts.append("\n".join(risk_lines))

        # Include any leftover keys not explicitly handled
        handled_keys = {
            'nome_progetto', 'obiettivi_prodotto', 'framework',
            'fasi_milestone', 'struttura_scrum', 'dipendenze_interne_esterne',
            'rischi_tecnici_operativi'
        }
        for key, value in desc.items():
            if key in handled_keys or value in (None, '', [], {}):
                continue
            formatted = self._format_description(value)
            if formatted:
                parts.append(f"{key.replace('_', ' ').title()}:\n{formatted}")

        formatted = "\n\n".join(part.strip() for part in parts if part)
        if not formatted:
            return ''
        # Ensure the description has at least five non-empty lines; if not, ask AI to elaborate more next time.
        lines = [line for line in formatted.splitlines() if line.strip() and not line.strip().startswith("Nota:")]
        if len(lines) < 5:
            formatted = f"{formatted}\n\nNota: arricchisci i prossimi resoconti con maggiori dettagli narrativi (minimo 5 righe)."
        return formatted

    def _build_meeting_prompt(self):
        prompt = (
            "Sei un project manager senior. In base ai documenti forniti, produci un'analisi completa del progetto.\n"
            "Adatta il taglio al framework di project management selezionato.\n\n"
        )
        # Istruzioni dinamiche per framework
        fw = (self.pm_framework or '').lower()
        if fw == 'prince2':
            prompt += (
                "Framework: PRINCE2. Evidenzia business case, prodotti/risultati, organizzazione, piani per fasi, tolleranze,"
                " gestione rischi e cambiamenti, lezioni apprese.\n\n"
            )
        elif fw == 'scrum':
            prompt += (
                "Framework: Agile-Scrum. Evidenzia ruoli (PO/SM/Team), backlog e priorità, obiettivi di sprint,"
                " cerimonie chiave, Definition of Done, dipendenze e rischi.\n\n"
            )
        elif fw == 'lean':
            prompt += (
                "Framework: Lean. Evidenzia catena del valore, eliminazione degli sprechi (muda), flusso, pull, kaizen,"
                " metriche di efficienza e rischi operativi.\n\n"
            )
        else:
            prompt += (
                "Framework: Agile. Evidenzia valore per l'utente, MVP, backlog tematico/epic, accettazione,"
                " roadmap iterativa e rischi.\n\n"
            )

        company_profile = self._get_company_profile_text()
        if company_profile:
            prompt += (
                f"Informazioni sulla azienda '{self.company_id.display_name}' coinvolta nel progetto (estratte dal profilo allegato):\n"
                f"{company_profile}\n\n"
            )

        prompt += (
            "RESTITUISCI SOLO JSON VALIDO, senza backticks e senza testo extra, con struttura ESATTA:\n"
            "{\n"
            "  \"description\": \"analisi completa del progetto\",\n"
            "  \"economic_notes\": \"note economiche e considerazioni di costo/beneficio, budget, OPEX/CAPEX, rischi economici\",\n"
            "  \"criticita\": \"criticità evidenti e rischi chiave\",\n"
            "  \"tags\": [\"dominio/settore\", \"modulo odoo\", \"tecnologia\", \"altro\"]\n"
            "}\n\n"
            "Se un'informazione non è esplicita, inferiscila in modo prudente o omettila.\n"
            "Scrivi tutto in testo semplice, senza markdown o formattazioni (niente **grassetto**, *corsivo*, intestazioni o link).\n\n"
        )
        for doc in self.documentation_ids:
            content = self._extract_text_from_pdf(doc.file)
            prompt += f"\nDocumento data: {doc.doc_date}, chiamato: {doc.name}\nContenuto:\n{content}\n"
        return prompt

    def _build_task_prompt(self):
        company_profile = self._get_company_profile_text()
        team_profiles = self._get_team_profiles()
        team_section = ""
        if team_profiles:
            team_section += "Membri del team disponibili per l'assegnazione delle task:\n"
            for employee, profile in team_profiles:
                contact_bits = []
                if employee.work_email:
                    contact_bits.append(f"email: {employee.work_email}")
                if employee.work_phone:
                    contact_bits.append(f"tel: {employee.work_phone}")
                if employee.mobile_phone:
                    contact_bits.append(f"mobile: {employee.mobile_phone}")
                if employee.user_id:
                    if employee.user_id.login:
                        contact_bits.append(f"login: {employee.user_id.login}")
                contact_info = f" ({', '.join(contact_bits)})" if contact_bits else ""
                team_section += f"- {employee.display_name}{contact_info}\n"
                if profile:
                    team_section += f"  Profilo professionale:\n{profile}\n"
                else:
                    team_section += "  Profilo professionale: nessuna descrizione fornita.\n"
            team_section += (
                "Quando restituisci le attività, utilizza il campo \"assignee\" con il nome esatto del membro più adatto tra quelli sopra indicati. "
                "Non inventare nomi o ruoli: scegli sempre tra i nomi elencati, a meno che nessuno sia adeguato.\n"
                "La profondità della descrizione della task deve riflettere quanto è dettagliato il profilo dell'utente assegnato: "
                "profonda e articolata per profili ricchi di dettagli, più sintetica per profili essenziali.\n\n"
            )
        else:
            team_section += (
                "Non è stato fornito alcun profilo team; usa il campo \"assignee\" vuoto oppure il project manager se opportuno.\n\n"
            )

        fw = (self.pm_framework or '').lower()
        if fw == 'prince2':
            prompt = (
                "Agisci come un project manager che utilizza PRINCE2.  \n"
                "Dato il contenuto delle riunioni, ritorna un JSON con una lista \"tasks\" che contenga le attività prioritarie.  \n"
                "Ogni attività deve includere titolo, descrizione, 1-3 parole chiave sull'ambito principale e il campo 'assignee' "
                "con il nome esatto del membro del team più adatto in base ai profili forniti.  \n"
                "Adatta la profondità della descrizione alla seniority e al dettaglio presente nel profilo dell'assegnatario.\n\n"
                "Formato:\n"
                "{\n"
                "  \"tasks\": [\n"
                "    {\"title\": \"\", \"description\": \"\", \"keywords\": [\"\", \"\"], \"assignee\": \"\"}\n"
                "  ]\n"
                "}\n\n"
            )
        elif fw == 'scrum':
            prompt = (
                "Agisci come uno Scrum Master.  \n"
                "Dato il contenuto delle riunioni, ritorna un JSON con le task suddivise per sprint.  \n"
                "Ogni task deve avere titolo, descrizione, parole chiave (1-3) coerenti con la logica Scrum (user story, attività tecniche, bugfix, ecc.) e il campo 'assignee' "
                "con il nome esatto del membro del team più adatto.  \n"
                "Adatta la profondità della descrizione alla seniority e ai dettagli presenti nel profilo dell'assegnatario.  \n\n"
                "Formato:\n"
                "{\n"
                "  \"sprints\": [\n"
                "    {\n"
                "      \"sprint\": 1,\n"
                "      \"tasks\": [\n"
                "        {\"title\": \"\", \"description\": \"\", \"keywords\": [\"\", \"\"], \"assignee\": \"\"}\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
            )
        elif fw == 'lean':
            prompt = (
                "Agisci come un project manager che utilizza Lean Project Management.  \n"
                "Dato il contenuto delle riunioni, ritorna un JSON con le attività suddivise per flusso di valore (value stream).  \n"
                "Le attività devono riflettere principi lean: eliminazione sprechi, riduzione tempi di attesa, ottimizzazione delle risorse, includere 1-3 parole chiave sull'argomento "
                "e specificare nel campo 'assignee' il membro del team più adeguato.  \n"
                "La profondità della descrizione deve adattarsi alla specializzazione del profilo assegnato.  \n\n"
                "Formato:\n"
                "{\n"
                "  \"value_streams\": [\n"
                "    {\n"
                "      \"stream\": \"Nome flusso di valore\",\n"
                "      \"tasks\": [\n"
                "        {\"title\": \"\", \"description\": \"\", \"keywords\": [\"\", \"\"], \"assignee\": \"\"}\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
            )
        else:
            prompt = (
                "Agisci come un project manager che utilizza Agile.  \n"
                "Dato il contenuto delle riunioni, ritorna un JSON con le attività suddivise per iterazioni.  \n"
                "Ogni iterazione rappresenta un ciclo di sviluppo incrementale e ogni task deve riportare 1-3 parole chiave sull'argomento "
                "e il campo 'assignee' con il nome del membro del team più idoneo. \n"
                "Modula la profondità della descrizione in base al profilo del membro assegnato.  \n\n"
                "Formato:\n"
                "{\n"
                "  \"iterations\": [\n"
                "    {\n"
                "      \"iteration\": 1,\n"
                "      \"tasks\": [\n"
                "        {\"title\": \"\", \"description\": \"\", \"keywords\": [\"\", \"\"], \"assignee\": \"\"}\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
            )

        prompt += (
            "Per ogni task assegna il membro del team più idoneo utilizzando esclusivamente i nomi elencati. "
            "Se nessun profilo è pertinente lascia l'assignee vuoto.\n"
            "Scrivi titoli e descrizioni in testo semplice, senza markdown o formattazioni (niente **grassetto**, *corsivo*, codice o simboli speciali).\n\n"
        )

        if company_profile:
            prompt += (
                f"Profilo aziendale fornito per contestualizzare il progetto:\n{company_profile}\n\n"
            )
        prompt += team_section

        for doc in self.documentation_ids:
            content = self._extract_text_from_pdf(doc.file)
            prompt += f"\nDocumento data: {doc.doc_date}, chiamato: {doc.name}\nContenuto:\n{content}\n"
        return prompt

    def _extract_json(self, text):
        import re
        if not text:
            return None
        fence = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
        if fence:
            return fence.group(1)
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
        return None

    def _call_ai(self, prompt):
        log = logging.getLogger(__name__)
        try:
            text = self.env['daedaly.gpt_api_helper'].chat(prompt)
            raw = self._extract_json(text)
            if raw:
                try:
                    return json.loads(raw)
                except Exception as e:
                    log.warning("JSON parse fallita, uso testo grezzo: %s", e)
            return {"description": (text or ""), "tags": []}
        except Exception as e:
            log.warning("Helper centrale fallito: %s", e)
            icp = self.env['ir.config_parameter'].sudo()
            agent_url = icp.get_param('daedaly.agent_url', '').rstrip('/')
            if not agent_url:
                return {"description": "", "tags": []}
            if requests is None:
                raise UserError("La libreria 'requests' non è installata nell'ambiente Python.")
            response = requests.post(
                url=f'{agent_url}/ask',
                json={'question': prompt},
                timeout=60
            )
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return {"description": response.text, "tags": []}

    def action_smart_description(self):
        for project in self:
            prompt = project._build_meeting_prompt()
            result = project._call_ai(prompt)

            # Coerce values to strings/HTML to avoid sanitizer issues
            desc = result.get("description", "")
            project.description = project._format_description(desc)
            project.economic_notes = self._to_html(result.get("economic_notes"))
            project.criticita = self._to_html(result.get("criticita"))
            tag_ids = []
            for tag_name in result.get("tags", []):
                tag = self.env['project.tags'].search([('name', '=', tag_name)], limit=1)
                if not tag:
                    tag = self.env['project.tags'].create({'name': tag_name})
                tag_ids.append(tag.id)
            project.tag_ids = [(6, 0, tag_ids)]

    def action_generate_tasks(self):
        for project in self:
            prompt = project._build_task_prompt()
            result = project._call_ai(prompt)

            milestone_model = self.env['project.milestone']
            tag_model = self.env['project.tags']

            def _get_or_create_milestone(name):
                name = (name or '').strip()
                if not name:
                    return None
                milestone = milestone_model.search([
                    ('project_id', '=', project.id),
                    ('name', '=', name)
                ], limit=1)
                if not milestone:
                    milestone = milestone_model.create({
                        'name': name,
                        'project_id': project.id,
                    })
                return milestone

            def _prepare_tag_ids(keywords):
                if not keywords:
                    return []
                if isinstance(keywords, str):
                    keywords_iterable = [keywords]
                else:
                    keywords_iterable = keywords
                tag_ids = []
                for keyword in keywords_iterable:
                    kw = (keyword or '').strip()
                    if not kw:
                        continue
                    tag = tag_model.search([('name', '=', kw)], limit=1)
                    if not tag:
                        tag = tag_model.create({'name': kw})
                    tag_ids.append(tag.id)
                return tag_ids

            def _normalize_assignee_key(value):
                if not value:
                    return ''
                value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode('ascii')
                return value.strip().lower()

            employee_candidates = project.team_employee_ids
            if project.user_id and project.user_id.employee_id:
                employee_candidates |= project.user_id.employee_id
            assignee_lookup = {}
            for employee in employee_candidates:
                user = employee.user_id
                keys = {employee.name, employee.display_name, employee.work_email, employee.work_phone, employee.mobile_phone}
                if user:
                    keys |= {user.name, user.display_name, user.login, user.email}
                for key in keys:
                    norm = _normalize_assignee_key(key)
                    if norm:
                        assignee_lookup.setdefault(norm, (employee, user))

            def _match_assignee(name):
                norm = _normalize_assignee_key(name)
                return assignee_lookup.get(norm)

            def _create_task(task, milestone=None):
                tag_ids = _prepare_tag_ids(task.get('keywords'))
                assignee_entry = _match_assignee(task.get('assignee'))
                assignee_user = assignee_entry[1] if assignee_entry else None
                task_vals = {
                    'name': task.get('title', 'Task'),
                    'description': task.get('description', ''),
                    'project_id': project.id,
                }
                if milestone:
                    task_vals['milestone_id'] = milestone.id
                if tag_ids:
                    task_vals['tag_ids'] = [(6, 0, tag_ids)]
                if assignee_user:
                    task_vals['user_ids'] = [(6, 0, [assignee_user.id])]
                self.env['project.task'].create(task_vals)

            fw = (project.pm_framework or '').lower()
            if fw == 'prince2':
                tasks = list(result.get('tasks') or [])
                if not tasks:
                    for phase in result.get('phases', []):
                        tasks.extend(phase.get('tasks', []) or [])
                for task in tasks:
                    _create_task(task)
            elif fw == 'scrum' and result.get('sprints'):
                for sprint_data in result.get("sprints", []):
                    sprint_number = sprint_data.get("sprint")
                    tasks = sprint_data.get('tasks', []) or []
                    milestone = _get_or_create_milestone(f"Sprint {sprint_number}" if sprint_number else "Sprint")
                    for task in tasks:
                        _create_task(task, milestone)
            elif fw == 'lean' and result.get('value_streams'):
                for stream in result['value_streams']:
                    stream_name = stream.get('stream') or 'Value Stream'
                    tasks = stream.get('tasks', []) or []
                    milestone = _get_or_create_milestone(f"Value Stream - {stream_name}")
                    for task in tasks:
                        _create_task(task, milestone)
            else:
                # Default Agile (iterazioni) o fallback se non riconosciuto
                for it in result.get('iterations', []):
                    it_number = it.get('iteration')
                    tasks = it.get('tasks', []) or []
                    milestone = _get_or_create_milestone(f"Iteration {it_number}" if it_number else "Iteration")
                    for task in tasks:
                        _create_task(task, milestone)
        if len(self) == 1:
            return self.action_view_tasks()
        return True

    def action_open_project_form(self):
        self.ensure_one()
        view = self.env.ref('project.edit_project', raise_if_not_found=False)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'view_mode': 'form',
            'views': [(view.id, 'form')] if view else [(False, 'form')],
            'res_id': self.id,
            'target': 'current',
            'context': dict(self.env.context),
        }

    def init(self):
        super().init()
        # ensure milestones remain enabled on existing projects after module updates
        self.env.cr.execute(
            "UPDATE project_project SET allow_milestones = TRUE WHERE allow_milestones IS NOT TRUE"
        )
