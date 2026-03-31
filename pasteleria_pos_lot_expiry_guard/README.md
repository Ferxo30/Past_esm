# pasteleria_pos_lot_expiry_guard

Módulo base para Odoo 18 Community que agrega:

- Semáforo por producto dentro del POS.
- Indicador secundario negro si existen lotes vencidos.
- Selección FEFO visual mediante `preferred_lot_id`.
- Bloqueo frontend al intentar pasar a pago con lotes vencidos.
- Validación backend en `create_from_ui` para impedir que se genere la venta.

## Qué sí resuelve
- No permite cobrar ni generar la venta si el pedido tiene un lote vencido.
- El lote vencido sigue existiendo en inventario para procesos como desecho o fraccionamiento.
- Deja disponible una capa de datos reutilizable (`pos_get_expiry_snapshot`) para popup de lotes, desechos o fraccionamiento.

## Qué debes conectar después
1. El popup de selección de lotes que ya uses en tu POS.
2. Tu módulo de desechos para consumir `stock.lot.pos_build_product_expiry_snapshot`.
3. Tu módulo de fraccionamiento si también debe listar lotes negros.

## Nota importante
Los nombres de componentes Owl de POS pueden variar levemente según el build exacto de Odoo 18 que tengas instalado.
Si un patch no levanta por nombre de template/componente, la lógica Python del módulo sigue siendo válida y solo habría que ajustar el nombre del componente JS/XML a tu build.
