---
id: CON-03
titulo: Red cableada, DNS y router
categoria: conectividad
version: 1.0
fecha: 2026-11-17
autoria: Equipo del proyecto (redacción original)
licencia: CC0-1.0
---
# Red cableada, DNS y router

## El cable de red no da conexión
Si el cable de red no da conexión, revisa que las luces del puerto de red de la computadora parpadeen. Si no se encienden, prueba otro cable y otro puerto de la pared o de la mesa. Los puertos de pared marcados con etiqueta roja son solo para teléfonos y no dan acceso a la red de datos. Si ningún puerto funciona, abre un reporte indicando el número de puerto que aparece en la placa.

## El servidor DNS no responde
Cuando el navegador dice que el servidor DNS no responde, la computadora no puede traducir los nombres de los sitios. Abre una terminal y ejecuta «ipconfig /flushdns» en Windows para limpiar la caché de nombres. Revisa también que la configuración de DNS esté en automático: los servidores DNS escritos a mano bloquean el acceso a los sistemas internos.

## El router muestra una luz roja
En los módulos remotos y oficinas pequeñas hay un router de Cumbre Digital. Una luz roja fija significa que el router no recibe servicio del proveedor de internet. Desconecta el router de la corriente durante 30 segundos y vuelve a conectarlo; tarda unos cinco minutos en iniciar. Si la luz sigue roja después de diez minutos, abre un reporte con prioridad alta indicando la dirección del módulo.

## Hay internet en el celular pero no en la computadora
Si el celular navega en la misma red pero la computadora no, el problema está en la computadora y no en la red. Desconecta y vuelve a conectar la red, ejecuta «ipconfig /release» seguido de «ipconfig /renew» y revisa que no haya un proxy configurado en el navegador. Si la computadora usa la VPN, desconéctala y prueba de nuevo.

## Diagnóstico básico antes de reportar
Antes de abrir un reporte de conectividad, anota si el problema ocurre por cable, por wifi o en ambos, desde cuándo ocurre y si afecta a otras personas cercanas. Esta información permite a la mesa de ayuda distinguir entre una falla de tu equipo y una falla de la red del edificio.
