from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    daedaly_agent_url = fields.Char(
        string="AI Agent URL",
        help="Endpoint esterno per l'analisi documenti (es. http://localhost:8001)",
        config_parameter='daedaly.agent_url',
    )
