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
        StockMoveLine = self.env["stock.move.line"].sudo()

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

                if line._requires_lot() and not line.lot_id:
                    raise UserError(
                        _("El producto %s requiere lote y no se seleccionó ninguno.")
                        % (line.product_id.display_name,)
                    )

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

            # Confirmar SIN merge para no perder la correspondencia línea -> move
            moves._action_confirm(merge=False)

            for move, line in zip(moves, rec.line_ids):
                ml_vals = {
                    "picking_id": picking.id,
                    "move_id": move.id,
                    "company_id": rec.company_id.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.product_uom_id.id,
                    "location_id": rec.location_id.id,
                    "location_dest_id": dest_location.id,
                }

                if line.lot_id:
                    ml_vals["lot_id"] = line.lot_id.id

                if "qty_done" in StockMoveLine._fields:
                    ml_vals["qty_done"] = line.qty
                elif "quantity" in StockMoveLine._fields:
                    ml_vals["quantity"] = line.qty

                StockMoveLine.create(ml_vals)

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

    @api.model
    def pos_get_product_lots_for_waste(self, pos_config_id, product_id):
        pos_config = self.env["pos.config"].browse(int(pos_config_id)).exists()
        product = self.env["product.product"].browse(int(product_id)).exists()

        if not pos_config:
            raise UserError(_("No se encontró la configuración del POS."))
        if not product:
            raise UserError(_("No se encontró el producto."))

        # Tu módulo de lotes sí expone este método en product.product
        snapshot = self.env["product.product"].pos_get_expiry_snapshot(pos_config.id)

        products_map = snapshot.get("products", {}) if isinstance(snapshot, dict) else {}
        product_data = products_map.get(product.id) or products_map.get(str(product.id)) or {}
        lots = product_data.get("lots", []) if isinstance(product_data, dict) else []

        result = []
        for lot in lots:
            qty_available = float(lot.get("qty_available", 0.0) or 0.0)
            result.append({
                "lot_id": lot.get("lot_id"),
                "lot_name": lot.get("lot_name") or lot.get("name") or lot.get("display_name"),
                "qty_available": qty_available,
                "expiration_date": lot.get("expiration_date"),
                "state": lot.get("state"),
                "sellable": lot.get("sellable"),
                "expired": lot.get("expired"),
                "days_left": lot.get("days_left"),
                # En desechos sí se pueden seleccionar lotes negros/vencidos,
                # siempre que tengan disponible.
                "selectable": qty_available > 0,
            })

        preferred_lot_id = False
        selectable_lots = [l for l in result if l["selectable"]]
        if selectable_lots:
            selectable_lots = sorted(
                selectable_lots,
                key=lambda x: (
                    {"red": 0, "yellow": 1, "green": 2, "black": 3}.get((x.get("state") or "").lower(), 9),
                    x.get("days_left", 999999),
                    x.get("lot_name") or "",
                ),
            )
            preferred_lot_id = selectable_lots[0]["lot_id"]

        return {
            "product_id": product.id,
            "product_name": product.display_name,
            "tracking": product.tracking,
            "summary_state": product_data.get("summary_state") if isinstance(product_data, dict) else False,
            "preferred_lot_id": preferred_lot_id,
            "lots": result,
        }

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
                    "lot_id": int|False,
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

            lot_id = l.get("lot_id") or False
            lot = False
            if lot_id:
                lot = self.env["stock.lot"].browse(int(lot_id))
                if not lot.exists():
                    raise UserError(_("Uno de los lotes enviados no existe."))
                if lot.product_id.id != product.id:
                    raise UserError(
                        _("El lote %s no pertenece al producto %s.")
                        % (lot.display_name, product.display_name)
                    )

            if product.tracking != "none" and not lot:
                raise UserError(
                    _("El producto %s requiere seleccionar un lote.")
                    % (product.display_name,)
                )

            line_commands.append((0, 0, {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "lot_id": lot.id if lot else False,
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
    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote",
        domain="[('product_id', '=', product_id)]",
        help="Lote seleccionado para el desecho. Se permite incluso si está vencido.",
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

    def _requires_lot(self):
        self.ensure_one()
        return self.product_id.tracking != "none"

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_uom_id = rec.product_id.uom_id
                if rec.lot_id and rec.lot_id.product_id != rec.product_id:
                    rec.lot_id = False

    @api.constrains("qty")
    def _check_qty(self):
        for rec in self:
            if rec.qty <= 0:
                raise ValidationError(_("La cantidad debe ser mayor a 0."))

    @api.constrains("product_id", "lot_id")
    def _check_lot_consistency(self):
        for rec in self:
            if rec.lot_id and rec.lot_id.product_id != rec.product_id:
                raise ValidationError(_("El lote seleccionado no pertenece al producto indicado."))

            if rec.product_id and rec.product_id.tracking != "none" and not rec.lot_id:
                raise ValidationError(_("El producto %s requiere lote.") % (rec.product_id.display_name,))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("product_id") and not vals.get("product_uom_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                if product.exists() and product.uom_id:
                    vals["product_uom_id"] = product.uom_id.id
        return super().create(vals_list)