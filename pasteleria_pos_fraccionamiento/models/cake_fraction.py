# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PasteleriaCakeFraction(models.Model):
    _name = "pasteleria.cake.fraction"
    _description = "Fraccionamiento de pasteles"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(string="Referencia", required=True, copy=False, default="New", tracking=True)
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ("draft", "Borrador"),
        ("done", "Realizado"),
        ("reversed", "Revertido"),
        ("cancel", "Cancelado"),
    ], default="draft", tracking=True)

    date = fields.Datetime(string="Fecha", default=fields.Datetime.now, required=True, tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)
    user_id = fields.Many2one("res.users", string="Usuario", default=lambda self: self.env.user, required=True, tracking=True)

    source_origin = fields.Selection([
        ("backend", "Backend"),
        ("pos", "POS"),
        ("pasteleria_view", "Vista pastelerías"),
    ], string="Origen", default="backend", required=True, tracking=True)

    pos_config_id = fields.Many2one("pos.config", string="Punto de venta", tracking=True)
    pos_session_id = fields.Many2one("pos.session", string="Sesión POS", tracking=True)
    warehouse_id = fields.Many2one("stock.warehouse", string="Almacén", required=True, tracking=True)
    location_id = fields.Many2one("stock.location", string="Ubicación origen/destino", required=True, tracking=True)

    virtual_fraction_location_id = fields.Many2one(
        "stock.location",
        string="Ubicación puente",
        required=False,
        help="Ubicación virtual usada como puente técnico para convertir un pastel completo en porciones.",
    )

    full_product_id = fields.Many2one(
        "product.product",
        string="Pastel completo",
        required=True,
        domain=[("can_be_fraction_source", "=", True)],
        tracking=True,
    )

    slice_product_id = fields.Many2one(
        "product.product",
        string="Producto porción",
        required=True,
        domain=[("is_cake_slice", "=", True)],
        tracking=True,
    )

    qty_full = fields.Float(string="Cantidad de enteros", default=1.0, required=True, tracking=True)
    qty_slices_created = fields.Float(string="Porciones generadas", required=True, tracking=True)

    reason_id = fields.Many2one("pasteleria.cake.fraction.reason", string="Motivo", tracking=True)
    note = fields.Text(string="Observaciones")

    expected_slice_min = fields.Integer(related="full_product_id.expected_slice_min", string="Sugerido mín.")
    expected_slice_max = fields.Integer(related="full_product_id.expected_slice_max", string="Sugerido máx.")
    warning_message = fields.Char(string="Advertencia", compute="_compute_warning_message")

    consumption_move_id = fields.Many2one("stock.move", string="Movimiento salida", copy=False)
    production_move_id = fields.Many2one("stock.move", string="Movimiento entrada", copy=False)

    reverse_of_id = fields.Many2one("pasteleria.cake.fraction", string="Revierte a", copy=False)
    reversal_fraction_id = fields.Many2one("pasteleria.cake.fraction", string="Reversión generada", copy=False)

    full_available_qty = fields.Float(string="Disponibilidad entero", compute="_compute_full_available_qty")
    can_reverse = fields.Boolean(compute="_compute_can_reverse")

    move_count = fields.Integer(string="Movimientos", compute="_compute_move_count")

    @api.depends("consumption_move_id", "production_move_id")
    def _compute_move_count(self):
        for rec in self:
            rec.move_count = int(bool(rec.consumption_move_id)) + int(bool(rec.production_move_id))

    @api.model
    def _get_fraction_bridge_location(self):
        """
        Busca una ubicación virtual específica para fraccionamiento.
        Prioridad:
        1) nombre exacto 'Fraccionamiento pasteles (virtual)'
        2) locations inventory de la compañía
        3) cualquier inventory global
        """
        Location = self.env["stock.location"].sudo()
        company = self.env.company

        location = Location.search([
            ("name", "=", "Fraccionamiento pasteles (virtual)"),
            ("usage", "=", "inventory"),
            ("company_id", "in", [False, company.id]),
        ], limit=1)
        if location:
            return location

        location = Location.search([
            ("usage", "=", "inventory"),
            ("company_id", "=", company.id),
        ], order="id asc", limit=1)
        if location:
            return location

        location = Location.search([
            ("usage", "=", "inventory"),
            ("company_id", "=", False),
        ], order="id asc", limit=1)

        return location

    @api.model
    def _get_default_slice_product(self, full_product):
        return full_product.cake_slice_product_id if full_product and full_product.cake_slice_product_id else False

    def _is_location_in_warehouse(self, warehouse, location):
        self.ensure_one()
        if not warehouse or not warehouse.lot_stock_id or not location:
            return False
        return bool(
            self.env["stock.location"].sudo().search_count([
                ("id", "=", location.id),
                ("id", "child_of", warehouse.lot_stock_id.id),
            ])
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("pasteleria.cake.fraction") or "New"

            if vals.get("pos_config_id") and not vals.get("warehouse_id"):
                pos_config = self.env["pos.config"].browse(vals["pos_config_id"])
                warehouse = pos_config.picking_type_id.warehouse_id
                vals["warehouse_id"] = warehouse.id
                vals["location_id"] = warehouse.lot_stock_id.id

            if vals.get("full_product_id") and not vals.get("slice_product_id"):
                full_product = self.env["product.product"].browse(vals["full_product_id"])
                slice_product = self._get_default_slice_product(full_product)
                if slice_product:
                    vals["slice_product_id"] = slice_product.id

            if not vals.get("virtual_fraction_location_id"):
                bridge_location = self._get_fractionBridgeOrFallback()
                if bridge_location:
                    vals["virtual_fraction_location_id"] = bridge_location.id

        return super().create(vals_list)

    def write(self, vals):
        if vals.get("full_product_id") and not vals.get("slice_product_id"):
            full_product = self.env["product.product"].browse(vals["full_product_id"])
            slice_product = self._get_default_slice_product(full_product)
            if slice_product:
                vals["slice_product_id"] = slice_product.id

        if "virtual_fraction_location_id" not in vals or not vals.get("virtual_fraction_location_id"):
            bridge_location = self._get_fractionBridgeOrFallback()
            if bridge_location:
                vals["virtual_fraction_location_id"] = bridge_location.id

        return super().write(vals)

    def _get_fractionBridgeOrFallback(self):
        self.ensure_one() if self else None
        return self.env["pasteleria.cake.fraction"]._get_fraction_bridge_location()

    @api.depends("full_product_id", "location_id")
    def _compute_full_available_qty(self):
        Quant = self.env["stock.quant"].sudo()
        for rec in self:
            rec.full_available_qty = 0.0
            if rec.full_product_id and rec.location_id:
                rec.full_available_qty = Quant._get_available_quantity(
                    rec.full_product_id,
                    rec.location_id,
                    allow_negative=False,
                )

    @api.depends("state", "reversal_fraction_id")
    def _compute_can_reverse(self):
        for rec in self:
            rec.can_reverse = rec.state == "done" and not rec.reversal_fraction_id

    @api.depends("qty_slices_created", "expected_slice_min", "expected_slice_max")
    def _compute_warning_message(self):
        for rec in self:
            warning = False
            if rec.qty_slices_created and rec.expected_slice_min and rec.qty_slices_created < rec.expected_slice_min:
                warning = _("La cantidad de porciones es menor al mínimo sugerido (%s).") % rec.expected_slice_min
            elif rec.qty_slices_created and rec.expected_slice_max and rec.qty_slices_created > rec.expected_slice_max:
                warning = _("La cantidad de porciones es mayor al máximo sugerido (%s).") % rec.expected_slice_max
            rec.warning_message = warning

    @api.onchange("pos_config_id")
    def _onchange_pos_config_id(self):
        if self.pos_config_id:
            warehouse = self.pos_config_id.picking_type_id.warehouse_id
            self.warehouse_id = warehouse
            self.location_id = warehouse.lot_stock_id

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        for rec in self:
            if rec.warehouse_id and (
                not rec.location_id or not rec._is_location_in_warehouse(rec.warehouse_id, rec.location_id)
            ):
                rec.location_id = rec.warehouse_id.lot_stock_id

    @api.onchange("full_product_id")
    def _onchange_full_product_id(self):
        for rec in self:
            rec.slice_product_id = rec._get_default_slice_product(rec.full_product_id)

    @api.constrains("full_product_id", "slice_product_id")
    def _check_same_template(self):
        for rec in self:
            if (
                rec.full_product_id
                and rec.slice_product_id
                and rec.full_product_id.product_tmpl_id != rec.slice_product_id.product_tmpl_id
            ):
                raise ValidationError(_("El pastel completo y la porción deben pertenecer al mismo producto plantilla."))

    @api.constrains("qty_full", "qty_slices_created")
    def _check_quantities(self):
        for rec in self:
            if rec.qty_full <= 0:
                raise ValidationError(_("La cantidad de enteros debe ser mayor a cero."))
            if rec.qty_slices_created <= 0:
                raise ValidationError(_("La cantidad de porciones debe ser mayor a cero."))

    @api.constrains("full_product_id", "slice_product_id")
    def _check_product_flags(self):
        for rec in self:
            if rec.full_product_id and not rec.full_product_id.can_be_fraction_source:
                raise ValidationError(_("El producto origen debe estar marcado como fraccionable."))
            if rec.slice_product_id and not rec.slice_product_id.is_cake_slice:
                raise ValidationError(_("El producto destino debe estar marcado como porción."))

    @api.constrains("warehouse_id", "location_id")
    def _check_location_belongs_to_warehouse(self):
        for rec in self:
            if rec.warehouse_id and rec.location_id:
                if rec.location_id.usage != "internal":
                    raise ValidationError(_("La ubicación debe ser interna."))
                if not rec._is_location_in_warehouse(rec.warehouse_id, rec.location_id):
                    raise ValidationError(_("La ubicación seleccionada no pertenece al almacén indicado."))

    def _check_before_confirm(self):
        self.ensure_one()

        if self.state != "draft":
            raise UserError(_("Solo se pueden confirmar fraccionamientos en borrador."))

        if not self.location_id:
            raise UserError(_("Debe definir una ubicación interna."))

        if self.location_id.usage != "internal":
            raise UserError(_("La ubicación principal del fraccionamiento debe ser interna."))

        if self.warehouse_id and not self._is_location_in_warehouse(self.warehouse_id, self.location_id):
            raise UserError(_("La ubicación seleccionada no pertenece al almacén indicado."))

        if not self.slice_product_id:
            raise UserError(_("El producto porción no está configurado para este pastel completo."))

        if self.qty_slices_created <= 0:
            raise UserError(_("La cantidad de porciones generadas debe ser mayor a cero."))

        available = self.env["stock.quant"].sudo()._get_available_quantity(
            self.full_product_id,
            self.location_id,
            allow_negative=False,
        )
        if available < self.qty_full:
            raise UserError(_("No hay stock suficiente del pastel completo en la ubicación seleccionada."))

        if not self.virtual_fraction_location_id:
            raise UserError(_("Debe definir una ubicación puente para el fraccionamiento."))

        if self.virtual_fraction_location_id.usage != "inventory":
            raise UserError(_("La ubicación puente debe ser de tipo Inventario/Ajuste."))

    def _prepare_move_vals(self, product, quantity, location_id, location_dest_id, reference_name):
        self.ensure_one()
        return {
            "name": reference_name,
            "company_id": self.company_id.id,
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": quantity,
            "location_id": location_id.id,
            "location_dest_id": location_dest_id.id,
            "origin": self.name,
            "reference": self.name,
        }

    def _set_done_qty_on_move_line(self, move_line, qty):
        vals = {}

        if "quantity" in move_line._fields:
            vals["quantity"] = qty
        elif "qty_done" in move_line._fields:
            vals["qty_done"] = qty
        elif "quantity_product_uom" in move_line._fields:
            vals["quantity_product_uom"] = qty
        else:
            raise UserError(_("No se encontró un campo compatible para cantidad hecha en stock.move.line."))

        move_line.write(vals)

    def _create_done_move(self, vals):
        self.ensure_one()

        Move = self.env["stock.move"]
        MoveLine = self.env["stock.move.line"]

        move = Move.create(vals)
        move._action_confirm()
        move._action_assign()

        qty = vals["product_uom_qty"]
        move_line = move.move_line_ids[:1]

        if move_line:
            move_line = move_line[0]
            extra_lines = move.move_line_ids - move_line
            if extra_lines:
                extra_lines.unlink()

            move_line.write({
                "product_id": vals["product_id"],
                "product_uom_id": vals["product_uom"],
                "location_id": vals["location_id"],
                "location_dest_id": vals["location_dest_id"],
            })
        else:
            move_line = MoveLine.create({
                "move_id": move.id,
                "product_id": vals["product_id"],
                "product_uom_id": vals["product_uom"],
                "location_id": vals["location_id"],
                "location_dest_id": vals["location_dest_id"],
            })

        self._set_done_qty_on_move_line(move_line, qty)

        if "picked" in move._fields:
            move.picked = True

        move._action_done()

        if move.state != "done":
            raise UserError(_(
                "El movimiento de inventario %(move)s no se pudo completar.\n"
                "Estado final: %(state)s\n"
                "Producto: %(product)s\n"
                "Desde: %(source)s\n"
                "Hacia: %(dest)s"
            ) % {
                "move": move.display_name,
                "state": move.state,
                "product": move.product_id.display_name,
                "source": move.location_id.display_name,
                "dest": move.location_dest_id.display_name,
            })

        return move

    def _success_notification(self, title, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "success",
                "sticky": False,
            }
        }

    def action_confirm(self):
        for rec in self:
            if not rec.slice_product_id and rec.full_product_id.cake_slice_product_id:
                rec.slice_product_id = rec.full_product_id.cake_slice_product_id.id

            if not rec.virtual_fraction_location_id:
                rec.virtual_fraction_location_id = rec._get_fraction_bridge_location()

            rec._check_before_confirm()

            bridge_location = rec.virtual_fraction_location_id
            if not bridge_location:
                raise UserError(_("No se encontró una ubicación virtual para fraccionamiento."))

            if bridge_location.usage != "inventory":
                raise UserError(_("La ubicación puente '%s' no es de tipo inventario.") % bridge_location.display_name)

            consumption_vals = rec._prepare_move_vals(
                rec.full_product_id,
                rec.qty_full,
                rec.location_id,
                bridge_location,
                _("Salida por fraccionamiento %s") % rec.name,
            )

            production_vals = rec._prepare_move_vals(
                rec.slice_product_id,
                rec.qty_slices_created,
                bridge_location,
                rec.location_id,
                _("Entrada por fraccionamiento %s") % rec.name,
            )

            rec.consumption_move_id = rec._create_done_move(consumption_vals).id
            rec.production_move_id = rec._create_done_move(production_vals).id
            rec.state = "done"

            rec.message_post(body=_(
                "Fraccionamiento confirmado.<br/>"
                "Pastel completo: <b>%s</b> (-%s)<br/>"
                "Producto porción: <b>%s</b> (+%s)<br/>"
                "Ubicación: <b>%s</b>"
            ) % (
                rec.full_product_id.display_name,
                rec.qty_full,
                rec.slice_product_id.display_name,
                rec.qty_slices_created,
                rec.location_id.display_name,
            ))

        if len(self) == 1:
            rec = self[0]
            return rec._success_notification(
                _("Fraccionamiento aplicado"),
                _("%s: -%s entero(s) y +%s porción(es) en %s.")
                % (
                    rec.full_product_id.display_name,
                    rec.qty_full,
                    rec.qty_slices_created,
                    rec.location_id.display_name,
                ),
            )
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Solo se pueden cancelar registros en borrador."))
            rec.state = "cancel"
        return True

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != "cancel":
                raise UserError(_("Solo se puede restablecer a borrador un registro cancelado."))
            rec.state = "draft"
        return True

    def _execute_reversal_moves(self):
        self.ensure_one()

        bridge_location = self.virtual_fraction_location_id or self._get_fraction_bridge_location()
        if not bridge_location:
            raise UserError(_("No se encontró una ubicación virtual para fraccionamiento."))

        if bridge_location.usage != "inventory":
            raise UserError(_("La ubicación puente '%s' no es de tipo inventario.") % bridge_location.display_name)

        slice_out_vals = self._prepare_move_vals(
            self.slice_product_id,
            self.qty_slices_created,
            self.location_id,
            bridge_location,
            _("Salida por reversión %s") % self.name,
        )

        full_in_vals = self._prepare_move_vals(
            self.full_product_id,
            self.qty_full,
            bridge_location,
            self.location_id,
            _("Entrada por reversión %s") % self.name,
        )

        self.consumption_move_id = self._create_done_move(slice_out_vals).id
        self.production_move_id = self._create_done_move(full_in_vals).id
        self.state = "done"

        self.message_post(body=_(
            "Reversión confirmada.<br/>"
            "Producto porción: <b>%s</b> (-%s)<br/>"
            "Pastel completo: <b>%s</b> (+%s)<br/>"
            "Ubicación: <b>%s</b>"
        ) % (
            self.slice_product_id.display_name,
            self.qty_slices_created,
            self.full_product_id.display_name,
            self.qty_full,
            self.location_id.display_name,
        ))

    def action_reverse(self):
        reversed_records = self.env["pasteleria.cake.fraction"]

        for rec in self:
            if rec.state != "done":
                raise UserError(_("Solo se pueden revertir fraccionamientos realizados."))

            if rec.reversal_fraction_id:
                raise UserError(_("Este fraccionamiento ya cuenta con una reversión."))

            available_slice_qty = self.env["stock.quant"].sudo()._get_available_quantity(
                rec.slice_product_id,
                rec.location_id,
                allow_negative=False,
            )
            if available_slice_qty < rec.qty_slices_created:
                raise UserError(_("No hay suficientes porciones disponibles para revertir el fraccionamiento."))

            reverse = self.create({
                "source_origin": rec.source_origin,
                "pos_config_id": rec.pos_config_id.id,
                "pos_session_id": rec.pos_session_id.id,
                "warehouse_id": rec.warehouse_id.id,
                "location_id": rec.location_id.id,
                "virtual_fraction_location_id": rec.virtual_fraction_location_id.id if rec.virtual_fraction_location_id else False,
                "full_product_id": rec.full_product_id.id,
                "slice_product_id": rec.slice_product_id.id,
                "qty_full": rec.qty_full,
                "qty_slices_created": rec.qty_slices_created,
                "reason_id": rec.reason_id.id,
                "note": _("Reversión automática de %s") % rec.name,
                "reverse_of_id": rec.id,
            })

            reverse._execute_reversal_moves()
            rec.reversal_fraction_id = reverse.id
            rec.state = "reversed"
            reversed_records |= reverse

        if len(self) == 1:
            rec = self[0]
            return rec._success_notification(
                _("Reversión aplicada"),
                _("Se revirtió %s y se generó %s.")
                % (rec.name, rec.reversal_fraction_id.name),
            )

        action = self.env.ref("pasteleria_pos_fraccionamiento.action_pasteleria_cake_fraction")
        return {
            "type": "ir.actions.act_window",
            "name": action.name,
            "res_model": "pasteleria.cake.fraction",
            "view_mode": "list,form",
            "domain": [("id", "in", reversed_records.ids)],
        }

    def action_open_consumption_move(self):
        self.ensure_one()
        if not self.consumption_move_id:
            raise UserError(_("Este fraccionamiento no tiene movimiento de salida."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Movimiento salida"),
            "res_model": "stock.move",
            "res_id": self.consumption_move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_production_move(self):
        self.ensure_one()
        if not self.production_move_id:
            raise UserError(_("Este fraccionamiento no tiene movimiento de entrada."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Movimiento entrada"),
            "res_model": "stock.move",
            "res_id": self.production_move_id.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def create_fraction_from_pos(self, payload):
        pos_session = self.env["pos.session"].browse(payload.get("pos_session_id"))
        if not pos_session:
            raise UserError(_("No se encontró la sesión POS para registrar el fraccionamiento."))

        pos_config = pos_session.config_id
        warehouse = pos_config.picking_type_id.warehouse_id
        full_product = self.env["product.product"].browse(payload.get("full_product_id"))

        if not full_product:
            raise UserError(_("Debe indicar el pastel completo a fraccionar."))

        slice_product = full_product.cake_slice_product_id
        if not slice_product:
            raise UserError(_("La variante seleccionada no tiene porción configurada."))

        bridge_location = self._get_fraction_bridge_location()
        if not bridge_location:
            raise UserError(_(
                "No se encontró una ubicación puente para fraccionamiento. "
                "Cree una ubicación tipo inventario llamada 'Fraccionamiento pasteles (virtual)'."
            ))

        if bridge_location.usage != "inventory":
            raise UserError(_("La ubicación puente '%s' no es de tipo inventario.") % bridge_location.display_name)

        record = self.create({
            "source_origin": "pos",
            "pos_config_id": pos_config.id,
            "pos_session_id": pos_session.id,
            "warehouse_id": warehouse.id,
            "location_id": warehouse.lot_stock_id.id,
            "virtual_fraction_location_id": bridge_location.id,
            "full_product_id": full_product.id,
            "slice_product_id": slice_product.id,
            "qty_full": payload.get("qty_full", 1),
            "qty_slices_created": payload.get("qty_slices_created", 0),
            "reason_id": payload.get("reason_id"),
            "note": payload.get("note"),
        })
        record.action_confirm()

        return {
            "fraction_id": record.id,
            "name": record.name,
            "slice_product_id": record.slice_product_id.id,
            "qty_slices_created": record.qty_slices_created,
        }