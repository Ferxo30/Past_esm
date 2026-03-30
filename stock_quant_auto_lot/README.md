# Stock Quant Auto Lot

Módulo para Odoo 18 Community.

## Qué hace
Cuando el usuario captura cantidad en la pantalla **Actualizar cantidad / Ajustes de inventario**, si:

- el producto está configurado con trazabilidad **Por lotes**,
- la línea no tiene lote,
- y la cantidad capturada es distinta de 0,

el módulo crea automáticamente un lote y lo asigna a la línea antes de aplicar el ajuste.

## Formato del lote
El lote se genera así:

`PREFIJO-AAAAMMDD-####`

Ejemplos:

- `ZANAHORIA-20260330-0001`
- `POSMINICUPC-20260330-0002`

El prefijo se toma de `Referencia interna` (`default_code`) si existe; si no, usa el nombre del producto.

## Alcance
- Aplica al flujo de **Actualizar cantidad / Ajuste de inventario**.
- Solo genera automáticamente para productos con rastreo **por lotes**.
- No modifica productos con rastreo **por número de serie**.
- No llena fechas de caducidad automáticamente.

## Instalación
1. Copiar la carpeta del módulo a tu ruta de addons personalizada.
2. Reiniciar Odoo.
3. Actualizar lista de aplicaciones.
4. Instalar **Stock Quant Auto Lot**.

## Nota
No fue probado directamente sobre tu base, así que te recomiendo instalarlo primero en una copia o ambiente de pruebas.
