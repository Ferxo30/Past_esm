# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PasteleriaDesecho(models.Model):
    _name = "pasteleria.desecho"
    _description = "Desecho (Pastelería)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "requested_date desc, id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )

    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Sucursal / Almacén",
        required=True,
        tracking=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación Origen",
        required=True,
        tracking=True,
        domain="[('usage','=','internal'), ('company_id','in',[False, company_id])]",
        help="Desde aquí se descuenta el inventario al confirmar.",
    )
    pos_config_id = fields.Many2one(
        "pos.config",
        string="Punto de Venta (POS)",
        tracking=True,
    )

    requested_by = fields.Many2one(
        "res.users",
        string="Solicitado por",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    requested_date = fields.Datetime(
        string="Fecha de solicitud",
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )

    approved_by = fields.Many2one(
        "res.users",
        string="Aprobado/Revisado por",
        readonly=True,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string="Fecha de aprobación",
        readonly=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("pending", "Pendiente"),
            ("confirmed", "Confirmado"),
            ("rejected", "Rechazado"),
        ],
        string="Estado",
        default="draft",
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        "pasteleria.desecho.line",
        "desecho_id",
        string="Líneas",
        copy=True,
    )
    total_qty = fields.Float(
        string="Total unidades",
        compute="_compute_total_qty",
        store=True,
    )

    picking_id = fields.Many2one(
        "stock.picking",
        string="Movimiento de inventario",
        readonly=True,
        copy=False,
    )

    def _post_desecho_message(self, subject, body=None):
        for rec in self:
            rec.message_post(
                subject=subject,
                body=body or subject,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pasteleria.desecho") or _("New")

        records = super(
            PasteleriaDesecho,
            self.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_notrack=True,
            ),
        ).create(vals_list)

        for rec in records:
            rec._post_desecho_message(
                subject="Orden de desecho creada",
                body=(
                    f"<b>Orden de desecho creada</b><br/>"
                    f"Referencia: {rec.name}<br/>"
                    f"Solicitado por: {rec.requested_by.name or '-'}<br/>"
                    f"Sucursal / Almacén: {rec.warehouse_id.display_name or '-'}<br/>"
                    f"Punto de Venta: {rec.pos_config_id.display_name or '-'}<br/>"
                    f"Total unidades: {rec.total_qty}"
                ),
            )

        return records

    @api.depends("line_ids.qty")
    def _compute_total_qty(self):
        for rec in self:
            rec.total_qty = sum(rec.line_ids.mapped("qty"))

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        for rec in self:
            if rec.warehouse_id:
                rec.location_id = rec.warehouse_id.lot_stock_id

    @api.constrains("line_ids")
    def _check_lines(self):
        for rec in self:
            if rec.state in ("pending", "confirmed") and not rec.line_ids:
                raise ValidationError(_("Debes agregar al menos una línea de desecho."))

    def _ensure_can_edit(self):
        for rec in self:
            if rec.state != "draft" and not self.env.user.has_group("pasteleria_desechos.group_pasteleria_admin"):
                raise UserError(_("Solo puedes editar un desecho cuando está en Borrador."))

    def write(self, vals):
        if not self.env.context.get("skip_desecho_edit_check"):
            protected_keys = {"message_follower_ids", "message_ids", "activity_ids"}
            if any(k not in protected_keys for k in vals.keys()):
                self._ensure_can_edit()
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state == "confirmed":
                raise UserError(_("No puedes borrar un desecho confirmado."))
        return super().unlink()

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.line_ids:
                raise UserError(_("Agrega al menos una línea antes de enviar."))

            rec.with_context(
                skip_desecho_edit_check=True,
                tracking_disable=True,
                mail_notrack=True,
            ).write({
                "state": "pending",
            })

            rec._post_desecho_message(
                subject="Orden de desecho enviada a revisión",
                body=(
                    f"<b>Orden de desecho enviada a revisión</b><br/>"
                    f"Referencia: {rec.name}<br/>"
                    f"Enviado por: {self.env.user.name}"
                ),
            )

    def _ensure_manager(self):
        if not (
            self.env.user.has_group("pasteleria_desechos.group_pasteleria_gerente")
            or self.env.user.has_group("pasteleria_desechos.group_pasteleria_admin")
        ):
            raise UserError(_("No tienes permisos para aprobar/rechazar desechos."))

    def action_reject(self):
        self._ensure_manager()
        for rec in self:
            if rec.state != "pending":
                continue

            rec.with_context(
                skip_desecho_edit_check=True,
                tracking_disable=True,
                mail_notrack=True,
            ).write({
                "state": "rejected",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            })

            rec._post_desecho_message(
                subject="Orden de desecho rechazada",
                body=(
                    f"<b>Orden de desecho rechazada</b><br/>"
                    f"Referencia: {rec.name}<br/>"
                    f"Revisado por: {self.env.user.name}<br/>"
                    f"Fecha: {fields.Datetime.now()}"
                ),
            )

    def action_set_draft(self):
        self._ensure_manager()
        for rec in self:
            if rec.state in ("pending", "rejected"):
                rec.with_context(
                    skip_desecho_edit_check=True,
                    tracking_disable=True,
                    mail_notrack=True,
                ).write({
                    "state": "draft",
                    "approved_by": False,
                    "approved_date": False,
                })

                rec._post_desecho_message(
                    subject="Orden de desecho devuelta a borrador",
                    body=(
                        f"<b>Orden de desecho devuelta a borrador</b><br/>"
                        f"Referencia: {rec.name}<br/>"
                        f"Acción realizada por: {self.env.user.name}"
                    ),
                )

    def _get_waste_location(self):
        self.ensure_one()

        loc = self.env["stock.location"].search([
            ("usage", "=", "inventory"),
            ("scrap_location", "=", True),
            ("company_id", "in", [self.company_id.id, False]),
            ("name", "ilike", "Desechos"),
        ], limit=1)

        if not loc:
            loc = self.env["stock.location"].search([
                ("usage", "=", "inventory"),
                ("company_id", "in", [self.company_id.id, False]),
            ], limit=1)

        if not loc:
            raise UserError(_("No se encontró una ubicación destino de tipo 'Inventory' para desechos."))

        return loc

    def action_confirm(self):
        self._ensure_manager()
        for rec in self:
            if rec.state != "pending":
                continue

            if not rec.line_ids:
                raise UserError(_("No hay líneas para confirmar."))

            if rec.picking_id:
                raise UserError(_("Este desecho ya tiene un movimiento asociado."))

            if not rec.warehouse_id:
                raise UserError(_("Debes seleccionar un almacén/sucursal."))
            if not rec.location_id:
                raise UserError(_("Debes seleccionar la ubicación origen."))

            picking_type = rec.warehouse_id.int_type_id
            if not picking_type:
                raise UserError(_("El almacén no tiene tipo de operación interna configurada."))

            dest_location = rec._get_waste_location()

            picking_vals = {
                "picking_type_id": picking_type.id,
                "location_id": rec.location_id.id,
                "location_dest_id": dest_location.id,
                "company_id": rec.company_id.id,
                "origin": rec.name,
            }
            picking = self.env["stock.picking"].sudo().create(picking_vals)

            move_vals_list = []
            for line in rec.line_ids:
                if line.qty <= 0:
                    raise UserError(_("La cantidad debe ser mayor a 0."))

                move_vals_list.append({
                    "name": rec.name,
                    "product_id": line.product_id.id,
                    "product_uom": line.product_uom_id.id,
                    "product_uom_qty": line.qty,
                    "location_id": rec.location_id.id,
                    "location_dest_id": dest_location.id,
                    "picking_id": picking.id,
                    "company_id": rec.company_id.id,
                })

            moves = self.env["stock.move"].sudo().create(move_vals_list)

            picking.sudo().action_confirm()
            picking.sudo().action_assign()

            for move in moves:
                if not move.move_line_ids:
                    continue

                remaining_qty = move.product_uom_qty
                for ml in move.move_line_ids:
                    qty_to_set = remaining_qty
                    if "qty_done" in ml._fields:
                        ml.qty_done = qty_to_set
                    elif "quantity" in ml._fields:
                        ml.quantity = qty_to_set

            picking.sudo().button_validate()

            rec.with_context(
                skip_desecho_edit_check=True,
                tracking_disable=True,
                mail_notrack=True,
            ).write({
                "state": "confirmed",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
                "picking_id": picking.id,
            })

            rec._post_desecho_message(
                subject="Orden de desecho confirmada",
                body=(
                    f"<b>Orden de desecho confirmada</b><br/>"
                    f"Referencia: {rec.name}<br/>"
                    f"Aprobado por: {self.env.user.name}<br/>"
                    f"Fecha: {fields.Datetime.now()}<br/>"
                    f"Movimiento generado: {picking.name or '-'}"
                ),
            )

    # ===== POS RPC =====
    @api.model
    def create_from_pos(self, payload):
        """
        payload esperado:
        {
            "pos_config_id": int,
            "lines": [
                {
                    "product_id": int,
                    "qty": float,
                    "reason": str|None,
                },
                ...
            ]
        }
        """
        pos = self.env["pos.config"].browse(int(payload.get("pos_config_id") or 0))
        if not pos.exists():
            raise UserError(_("POS inválido."))

        raw_lines = payload.get("lines") or []
        raw_lines = [l for l in raw_lines if l.get("product_id") and (l.get("qty") or 0) > 0]
        if not raw_lines:
            raise UserError(_("Debes enviar al menos una línea con cantidad mayor a 0."))

        picking_type = pos.picking_type_id
        warehouse = picking_type.warehouse_id if picking_type else False
        if not warehouse:
            raise UserError(_("El POS no tiene warehouse asociado. Revisa la configuración del punto de venta."))

        line_commands = []
        for l in raw_lines:
            product = self.env["product.product"].browse(int(l["product_id"]))
            if not product.exists():
                raise UserError(_("Uno de los productos enviados no existe."))

            if not product.uom_id:
                raise UserError(_("El producto %s no tiene unidad de medida configurada.") % (product.display_name,))

            line_commands.append((0, 0, {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "qty": float(l["qty"]),
                "reason": (l.get("reason") or "").strip(),
            }))

        desecho = self.create({
            "warehouse_id": warehouse.id,
            "location_id": warehouse.lot_stock_id.id,
            "pos_config_id": pos.id,
            "requested_by": self.env.user.id,
            "state": "pending",
            "line_ids": line_commands,
        })

        return {
            "id": desecho.id,
            "name": desecho.name,
        }


class PasteleriaDesechoLine(models.Model):
    _name = "pasteleria.desecho.line"
    _description = "Línea de Desecho (Pastelería)"

    desecho_id = fields.Many2one(
        "pasteleria.desecho",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto (Variante)",
        required=True,
        domain="[('type','in',['product','consu']), ('sale_ok','=',True)]",
    )
    product_uom_id = fields.Many2one(
        "uom.uom",
        string="UdM",
        required=True,
    )
    qty = fields.Float(
        string="Cantidad",
        required=True,
        default=1.0,
    )
    reason = fields.Char(string="Motivo")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_uom_id = rec.product_id.uom_id

    @api.constrains("qty")
    def _check_qty(self):
        for rec in self:
            if rec.qty <= 0:
                raise ValidationError(_("La cantidad debe ser mayor a 0."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("product_id") and not vals.get("product_uom_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                if product.exists() and product.uom_id:
                    vals["product_uom_id"] = product.uom_id.id
        return super().create(vals_list)