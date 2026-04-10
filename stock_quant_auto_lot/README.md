# Stock Quant Auto Lot

Módulo para Odoo 18 Community.

## Qué hace
Cuando el usuario captura cantidad en la pantalla **Actualizar cantidad / Ajustes de inventario**, si:

- el producto está configurado con trazabilidad **Por lotes**,
- la línea no tiene lote,
- y la cantidad capturada es distinta de 0,

el módulo crea automáticamente un lote y lo asigna a la línea antes de aplicar el ajuste.

## Mejora incluida en esta versión
- Al crear el lote automáticamente, intenta colocar la **fecha de producción** con la **fecha de hoy**.
- Si el usuario cambia manualmente la fecha de producción, el módulo intenta **preservarla**.
- Si el producto tiene configurados días de caducidad, el módulo llena los campos estándar de vencimiento partiendo de la fecha base usada.

> Nota: la fecha de producción no es un campo estándar en todas las bases.
> Este módulo detecta nombres comunes como `production_date`, `fecha_produccion`,
> `x_studio_fecha_de_produccion`, entre otros.

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

## Instalación
1. Reemplaza la carpeta anterior del módulo por esta nueva versión.
2. Reinicia Odoo.
3. Actualiza la lista de aplicaciones.
4. Actualiza el módulo **Stock Quant Auto Lot**.

## Nota
Si tu campo de fecha de producción tiene un nombre técnico muy distinto, avísame y lo ajusto.


## Ajuste adicional en esta versión
- Si detecta una fecha placeholder tipo `31/12/...`, la reemplaza por la fecha de hoy durante el ajuste de inventario.
- Si el usuario escribe otra fecha distinta, por ejemplo ayer, la conserva.


- v4: also normalizes stock.quant.inventory_date to today's date during inventory adjustments when Odoo carries placeholder 31/12/xxxx values.
