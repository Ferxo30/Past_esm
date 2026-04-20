# Pastelería POS - Recargar Recibo

Este módulo agrega un botón **Recargar recibo** en la pantalla final del POS.

## Mejoras incluidas

- Fuerza el re-render del recibo de la orden actual.
- Muestra estado visible: `Recargando...`, `Recargado ✓` o error.
- Deja una marca visible con la hora de la última recarga.
- Lleva conteo de cuántas veces se ha recargado el recibo durante esa vista.

## Nota

Esto sirve como apoyo operativo. No sustituye la limpieza de caché local del navegador cuando el problema viene de IndexedDB, Local Storage o assets viejos del POS.
