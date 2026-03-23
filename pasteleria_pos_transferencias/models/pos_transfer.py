# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from urllib.parse import quote
import json


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
    
    @api.model
    def get_pos_transfer_backend_url(self, pos_config_id=False):
        action = self.env.ref("pasteleria_pos_transferencias.action_pasteleria_pos_transfer", raise_if_not_found=False)
        menu = self.env.ref("pasteleria_pos_transferencias.menu_pasteleria_pos_transfer", raise_if_not_found=False)

        context = {}
        if pos_config_id:
            context["default_origin_pos_id"] = pos_config_id

            pos_config = self.env["pos.config"].browse(pos_config_id)
            if pos_config.transfer_source_location_id:
                context["default_source_location_id"] = pos_config.transfer_source_location_id.id
            if pos_config.transfer_operation_type_id:
                context["default_picking_type_id"] = pos_config.transfer_operation_type_id.id

        url = "/web"
        params = []

        if action:
            params.append(f"action={action.id}")
        if menu:
            params.append(f"menu_id={menu.id}")
        params.append("model=pasteleria.pos.transfer")
        params.append("view_type=list")

        if context:
            params.append("context=" + quote(json.dumps(context)))

        if params:
            url += "#" + "&".join(params)

        return {
            "url": url,
            "action_id": action.id if action else False,
            "menu_id": menu.id if menu else False,
            "context": context,
        }

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

    def _validate_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debes agregar al menos una línea a la transferencia."))

            for line in rec.line_ids:
                if line.qty <= 0:
                    raise UserError(_("La cantidad debe ser mayor que cero en todas las líneas."))

                available_qty = line.product_id.with_context(
                    location=rec.source_location_id.id
                ).qty_available

                if line.qty > available_qty:
                    raise UserError(_(
                        "No hay suficiente stock para el producto %(product)s.\n"
                        "Disponible en origen: %(available)s\n"
                        "Solicitado: %(requested)s"
                    ) % {
                        "product": line.product_id.display_name,
                        "available": available_qty,
                        "requested": line.qty,
                    })

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
            "name": line.product_id.display_name,
            "product_id": line.product_id.id,
            "product_uom_qty": line.qty,
            "product_uom": line.uom_id.id,
            "location_id": self.source_location_id.id,
            "location_dest_id": self.destination_location_id.id,
            "picking_id": picking.id,
            "company_id": self.company_id.id,
        }

    def action_confirm(self):
        StockPicking = self.env["stock.picking"]
        StockMove = self.env["stock.move"]

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

            for line in rec.line_ids:
                StockMove.create(rec._prepare_move_vals(line, picking))

            picking.action_confirm()
            picking.action_assign()

            for move in picking.move_ids_without_package:
                for move_line in move.move_line_ids:
                    move_line.quantity = move.product_uom_qty

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
        string="Disponible en origen",
        compute="_compute_available_qty",
        digits="Product Unit of Measure",
    )

    @api.depends("product_id", "transfer_id.source_location_id")
    def _compute_available_qty(self):
        for line in self:
            available = 0.0
            if line.product_id and line.transfer_id.source_location_id:
                available = line.product_id.with_context(
                    location=line.transfer_id.source_location_id.id
                ).qty_available
            line.available_qty = available