# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PasteleriaPosTransfer(models.Model):
    _name = "pasteleria.pos.transfer"
    _description = "Transferencia entre puntos de venta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Referencia",
        required=True,
        copy=False,
        default=lambda self: _("Nuevo"),
        tracking=True,
    )

    state = fields.Selection([
        ("draft", "Borrador"),
        ("confirmed", "Confirmado"),
        ("cancelled", "Cancelado"),
    ], string="Estado", default="draft", tracking=True)

    date = fields.Datetime(
        string="Fecha",
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )

    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )

    origin_pos_id = fields.Many2one(
        "pos.config",
        string="POS origen",
        required=True,
        tracking=True,
    )

    destination_pos_id = fields.Many2one(
        "pos.config",
        string="POS destino",
        required=True,
        tracking=True,
    )

    source_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación origen",
        required=True,
        tracking=True,
    )

    destination_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación destino",
        required=True,
        tracking=True,
    )

    picking_type_id = fields.Many2one(
        "stock.picking.type",
        string="Tipo de operación",
        required=True,
        domain="[('code', '=', 'internal')]",
    )

    picking_id = fields.Many2one(
        "stock.picking",
        string="Transferencia de inventario",
        copy=False,
    )

    note = fields.Text(string="Notas")

    line_ids = fields.One2many(
        "pasteleria.pos.transfer.line",
        "transfer_id",
        string="Líneas",
        copy=True,
    )

    total_lines = fields.Integer(
        string="Total líneas",
        compute="_compute_total_lines",
        store=True,
    )

    allowed_destination_pos_ids = fields.Many2many(
        "pos.config",
        compute="_compute_allowed_destination_pos_ids",
        string="POS destino permitidos",
    )

    @api.depends("line_ids")
    def _compute_total_lines(self):
        for rec in self:
            rec.total_lines = len(rec.line_ids)

    @api.depends("origin_pos_id")
    def _compute_allowed_destination_pos_ids(self):
        for rec in self:
            rec.allowed_destination_pos_ids = rec.origin_pos_id.allowed_destination_pos_ids

    def _prepare_auto_fields_from_vals(self, vals):
        origin_pos = self.env["pos.config"].browse(vals["origin_pos_id"]) if vals.get("origin_pos_id") else False
        destination_pos = self.env["pos.config"].browse(vals["destination_pos_id"]) if vals.get("destination_pos_id") else False

        if origin_pos:
            if not vals.get("source_location_id") and origin_pos.transfer_source_location_id:
                vals["source_location_id"] = origin_pos.transfer_source_location_id.id
            if not vals.get("picking_type_id") and origin_pos.transfer_operation_type_id:
                vals["picking_type_id"] = origin_pos.transfer_operation_type_id.id

        if destination_pos:
            if not vals.get("destination_location_id") and destination_pos.transfer_source_location_id:
                vals["destination_location_id"] = destination_pos.transfer_source_location_id.id

        return vals

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code("pasteleria.pos.transfer") or _("Nuevo")
            vals = self._prepare_auto_fields_from_vals(vals)
            new_vals_list.append(vals)
        return super().create(new_vals_list)

    def write(self, vals):
        vals = dict(vals)
        vals = self._prepare_auto_fields_from_vals(vals)
        return super().write(vals)

    @api.onchange("origin_pos_id")
    def _onchange_origin_pos_id(self):
        self.destination_pos_id = False

        if self.origin_pos_id:
            self.source_location_id = self.origin_pos_id.transfer_source_location_id.id or False
            self.picking_type_id = self.origin_pos_id.transfer_operation_type_id.id or False
        else:
            self.source_location_id = False
            self.picking_type_id = False

        return {
            "domain": {
                "destination_pos_id": [("id", "in", self.origin_pos_id.allowed_destination_pos_ids.ids)],
            }
        }

    @api.onchange("destination_pos_id")
    def _onchange_destination_pos_id(self):
        if self.destination_pos_id:
            self.destination_location_id = self.destination_pos_id.transfer_source_location_id.id or False
        else:
            self.destination_location_id = False

    @api.constrains("origin_pos_id", "destination_pos_id")
    def _check_different_pos(self):
        for rec in self:
            if rec.origin_pos_id and rec.destination_pos_id and rec.origin_pos_id == rec.destination_pos_id:
                raise ValidationError(_("El POS origen y el POS destino deben ser distintos."))

    @api.constrains("source_location_id", "destination_location_id")
    def _check_different_locations(self):
        for rec in self:
            if rec.source_location_id and rec.destination_location_id and rec.source_location_id == rec.destination_location_id:
                raise ValidationError(_("La ubicación origen y destino deben ser distintas."))

    @api.constrains("origin_pos_id", "destination_pos_id")
    def _check_allowed_destination(self):
        for rec in self:
            if rec.origin_pos_id and rec.destination_pos_id:
                if rec.destination_pos_id not in rec.origin_pos_id.allowed_destination_pos_ids:
                    raise ValidationError(_("El POS destino no está permitido para este POS origen."))

    def _get_available_qty_for_lot(self, product, lot, location):
        self.ensure_one()
        Quant = self.env["stock.quant"].sudo()

        groups = Quant.read_group(
            [
                ("location_id", "child_of", location.id),
                ("product_id", "=", product.id),
                ("lot_id", "=", lot.id),
            ],
            ["quantity:sum", "reserved_quantity:sum"],
            [],
            lazy=False,
        )

        if not groups:
            return 0.0

        qty = groups[0].get("quantity", 0.0) or 0.0
        reserved = groups[0].get("reserved_quantity", 0.0) or 0.0
        return qty - reserved

    def _validate_line_lot(self, line):
        self.ensure_one()

        if not line.lot_id:
            raise UserError(_("Debes seleccionar un lote para el producto '%s'.") % line.product_id.display_name)

        if line.lot_id.product_id != line.product_id:
            raise UserError(_("El lote '%s' no pertenece al producto '%s'.") % (
                line.lot_id.name,
                line.product_id.display_name,
            ))

        invalid_lots = self.env["stock.lot"].pos_validate_sellable_lots(
            self.origin_pos_id.id,
            [line.lot_id.id],
        )
        if invalid_lots:
            first = invalid_lots[0]
            raise UserError(_(
                "No se puede transferir el lote '%(lot)s' del producto '%(product)s' "
                "porque está vencido desde %(date)s."
            ) % {
                "lot": first["lot_name"],
                "product": first["product_name"],
                "date": first["expiration_date"],
            })

        available_qty = self._get_available_qty_for_lot(
            line.product_id,
            line.lot_id,
            self.source_location_id,
        )

        if line.qty > available_qty:
            raise UserError(_(
                "No hay suficiente stock en el lote '%(lot)s' del producto '%(product)s'.\n"
                "Disponible en origen: %(available)s\n"
                "Solicitado: %(requested)s"
            ) % {
                "lot": line.lot_id.name,
                "product": line.product_id.display_name,
                "available": available_qty,
                "requested": line.qty,
            })

    def _validate_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debes agregar al menos una línea a la transferencia."))

            for line in rec.line_ids:
                if line.qty <= 0:
                    raise UserError(_("La cantidad debe ser mayor que cero en todas las líneas."))

                if not line.product_id:
                    raise UserError(_("Todas las líneas deben tener producto."))

                rec._validate_line_lot(line)

    def _prepare_picking_vals(self):
        self.ensure_one()
        return {
            "picking_type_id": self.picking_type_id.id,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "origin": self.name,
            "note": self.note or "",
            "company_id": self.company_id.id,
            "pasteleria_pos_transfer_id": self.id,
        }

    def _prepare_move_vals(self, line, picking):
        self.ensure_one()
        return {
            "name": "%s [%s]" % (line.product_id.display_name, line.lot_id.name),
            "product_id": line.product_id.id,
            "product_uom_qty": line.qty,
            "product_uom": line.uom_id.id,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "picking_id": picking.id,
            "company_id": self.company_id.id,
        }

    @api.model
    def pos_get_transfer_popup_data(self, pos_config_id):
        pos_config = self.env["pos.config"].browse(pos_config_id).exists()
        if not pos_config:
            raise UserError(_("No se encontró la configuración del POS."))

        destinations = []
        for dest in pos_config.allowed_destination_pos_ids:
            destinations.append({
                "id": dest.id,
                "name": dest.name,
            })

        products = self.env["product.product"].search([
            ("available_in_pos", "=", True),
            ("active", "=", True),
        ])

        product_list = [{
            "id": product.id,
            "name": product.display_name,
            "uom_name": product.uom_id.name,
        } for product in products]

        return {
            "origin_pos_id": pos_config.id,
            "origin_pos_name": pos_config.name,
            "destinations": destinations,
            "products": product_list,
        }

    @api.model
    def pos_get_product_lots_for_transfer(self, pos_config_id, product_id):
        pos_config = self.env["pos.config"].browse(pos_config_id).exists()
        product = self.env["product.product"].browse(product_id).exists()

        if not pos_config:
            raise UserError(_("No se encontró la configuración del POS."))
        if not product:
            raise UserError(_("No se encontró el producto."))

        snapshot = self.env["stock.lot"].pos_build_product_expiry_snapshot(
            pos_config.id,
            [product.id],
        )

        product_data = snapshot.get("products", {}).get(product.id, {})
        lots = product_data.get("lots", [])

        result = []
        for lot in lots:
            result.append({
                "lot_id": lot.get("lot_id"),
                "lot_name": lot.get("lot_name"),
                "qty_available": lot.get("qty_available", 0.0),
                "expiration_date": lot.get("expiration_date"),
                "state": lot.get("state"),
                "sellable": lot.get("sellable"),
                "expired": lot.get("expired"),
                "days_left": lot.get("days_left"),
                "selectable": bool(lot.get("sellable")) and lot.get("state") != "black" and (lot.get("qty_available", 0.0) > 0),
            })

        return {
            "product_id": product.id,
            "product_name": product.display_name,
            "summary_state": product_data.get("summary_state"),
            "preferred_lot_id": product_data.get("preferred_lot_id"),
            "preferred_lot_name": product_data.get("preferred_lot_name"),
            "lots": result,
        }

    @api.model
    def pos_create_transfer_from_ui(self, payload):
        origin_pos_id = payload.get("origin_pos_id")
        destination_pos_id = payload.get("destination_pos_id")
        lines = payload.get("lines", [])

        if not origin_pos_id:
            raise UserError(_("No se recibió el POS origen."))
        if not destination_pos_id:
            raise UserError(_("Debes seleccionar un POS destino."))
        if not lines:
            raise UserError(_("Debes agregar al menos una línea."))

        transfer = self.create({
            "origin_pos_id": origin_pos_id,
            "destination_pos_id": destination_pos_id,
            "line_ids": [
                (0, 0, {
                    "product_id": line["product_id"],
                    "lot_id": line["lot_id"],
                    "qty": line["qty"],
                })
                for line in lines
            ],
        })

        transfer.action_confirm()

        return {
            "transfer_id": transfer.id,
            "transfer_name": transfer.name,
            "picking_id": transfer.picking_id.id if transfer.picking_id else False,
        }

    def action_confirm(self):
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]
        StockMoveLine = self.env["stock.move.line"]

        for rec in self:
            if rec.state != "draft":
                continue

            rec._validate_lines()

            if not rec.picking_type_id:
                raise UserError(_("No hay tipo de operación configurado en el POS origen."))
            if not rec.source_location_id:
                raise UserError(_("No hay ubicación origen configurada en el POS origen."))
            if not rec.destination_location_id:
                raise UserError(_("No hay ubicación destino configurada en el POS destino."))

            picking = StockPicking.create(rec._prepare_picking_vals())
            line_move_pairs = []

            for line in rec.line_ids:
                move = StockMove.create(rec._prepare_move_vals(line, picking))
                line_move_pairs.append((line, move))

            picking.action_confirm()
            picking.action_assign()

            for line, move in line_move_pairs:
                if move.move_line_ids:
                    move.move_line_ids.unlink()

                StockMoveLine.create({
                    "move_id": move.id,
                    "picking_id": picking.id,
                    "product_id": line.product_id.id,
                    "product_uom_id": line.uom_id.id,
                    "quantity": line.qty,
                    "location_id": rec.source_location_id.id,
                    "location_dest_id": rec.destination_location_id.id,
                    "lot_id": line.lot_id.id,
                    "company_id": rec.company_id.id,
                })

            picking.button_validate()

            rec.write({
                "state": "confirmed",
                "picking_id": picking.id,
            })

        return True

    def action_cancel(self):
        for rec in self:
            if rec.state == "confirmed" and rec.picking_id and rec.picking_id.state not in ("cancel",):
                raise UserError(_("No puedes cancelar una transferencia que ya generó un picking validado."))
            rec.state = "cancelled"
        return True


class PasteleriaPosTransferLine(models.Model):
    _name = "pasteleria.pos.transfer.line"
    _description = "Línea de transferencia POS"
    _order = "id"

    transfer_id = fields.Many2one(
        "pasteleria.pos.transfer",
        string="Transferencia",
        required=True,
        ondelete="cascade",
    )

    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain="[('available_in_pos', '=', True)]",
    )

    lot_id = fields.Many2one(
        "stock.lot",
        string="Lote",
        required=True,
        domain="[('product_id', '=', product_id)]",
    )

    qty = fields.Float(
        string="Cantidad",
        required=True,
        digits="Product Unit of Measure",
        default=1.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unidad de medida",
        related="product_id.uom_id",
        store=True,
        readonly=True,
    )

    available_qty = fields.Float(
        string="Disponible en lote",
        compute="_compute_available_qty",
        digits="Product Unit of Measure",
    )

    lot_expiration_date = fields.Date(
        string="Fecha vencimiento",
        compute="_compute_lot_meta",
    )

    lot_expiry_state = fields.Selection([
        ("green", "Verde"),
        ("yellow", "Amarillo"),
        ("red", "Rojo"),
        ("black", "Negro"),
    ], string="Semáforo", compute="_compute_lot_meta")

    lot_selectable = fields.Boolean(
        string="Lote seleccionable",
        compute="_compute_lot_meta",
    )

    @api.depends("product_id", "lot_id", "transfer_id.source_location_id")
    def _compute_available_qty(self):
        Quant = self.env["stock.quant"].sudo()

        for line in self:
            available = 0.0
            if line.product_id and line.lot_id and line.transfer_id.source_location_id:
                groups = Quant.read_group(
                    [
                        ("location_id", "child_of", line.transfer_id.source_location_id.id),
                        ("product_id", "=", line.product_id.id),
                        ("lot_id", "=", line.lot_id.id),
                    ],
                    ["quantity:sum", "reserved_quantity:sum"],
                    [],
                    lazy=False,
                )
                if groups:
                    qty = groups[0].get("quantity", 0.0) or 0.0
                    reserved = groups[0].get("reserved_quantity", 0.0) or 0.0
                    available = qty - reserved
            line.available_qty = available

    @api.depends("lot_id")
    def _compute_lot_meta(self):
        StockLot = self.env["stock.lot"]
        today = StockLot._pos_today()

        for line in self:
            line.lot_expiration_date = False
            line.lot_expiry_state = False
            line.lot_selectable = False

            if not line.lot_id:
                continue

            expiry_info = line.lot_id._get_effective_expiration_value(line.lot_id)
            expiration_date = expiry_info["local_date"]
            warning_days = getattr(line.product_id, "x_pos_expiry_warning_days", 2) or 2
            state, sellable, expired, days_left = line.lot_id._compute_expiry_state(
                line.lot_id,
                today=today,
                warning_days=warning_days,
            )

            line.lot_expiration_date = expiration_date
            line.lot_expiry_state = state
            line.lot_selectable = bool(sellable) and state != "black"