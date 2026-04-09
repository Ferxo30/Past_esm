{
    "name": "POS Button Configuration",
    "version": "18.0.1.0.1",
    "summary": "Enable or disable key buttons in Point of Sale",
    "category": "Point Of Sale",
    "author": "WebVeer / Migrated for Odoo 18",
    "website": "",
    "license": "LGPL-3",
    "depends": ["point_of_sale"],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_button_config/static/src/app/overrides/product_screen_patch.js",
            "pos_button_config/static/src/app/overrides/product_screen_templates.xml",
        ],
    },
    "images": ["static/description/pos_screen.jpg"],
    "installable": True,
    "application": False,
}
