{
    "name": "Daedaly",
    "version": "1.0",
    "author": "Koodos",
    "category": "Project",
    "summary": "Project and task AI helpers with unified configuration",
    "depends": ["project", "hr"],
    "external_dependencies": {
        "python": ["fitz", "requests"]
    },
    "data": [
        "security/ir.model.access.csv",
        "security/project_security.xml",
        "data/project_defaults.xml",
        "views/ir_config.xml",
        "views/test_api_connection.xml",
        "views/res_config_settings_view.xml",
        "views/project_views.xml",
        "views/company_user_views.xml",
        "views/task_views.xml"
    ],
    "icon": "/daedaly/static/description/icon.png",
    "images": [
        "static/description/icon.png"
    ],
    "assets": {
        "web.assets_backend": [
            "daedaly/static/src/css/daedaly_buttons.css",
        ],
    },
    "installable": True,
    "application": False,
}
