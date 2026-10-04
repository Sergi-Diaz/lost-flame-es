# Lost Flame en español

Traducción no oficial de Lost Flame al español. Incluye textos, nombres, descripciones, menús y compatibilidad con tildes y ñ. Requiere tener instalado el juego de Steam: https://store.steampowered.com/app/856570/Lost_Flame/

La traducción se ha realizado con uso de GPT y revisión a mano de montones de casuísticas o nombres peculiares, obviamente es una traducción no profesional y puede haber errores, tenlo en cuenta. 

## Instalación en Windows

1. Descarga **LostFlame-es-0.9.8.zip** desde [la última versión](https://github.com/Sergi-Diaz/lost-flame-es/releases/latest).
2. Extrae el ZIP completo y cierra el juego.
3. Abre **Instalar.cmd** con doble clic.
4. Si no encuentra el juego, pulsa **Buscar…** y selecciona su carpeta. Puedes localizarla desde Steam: Propiedades → Archivos instalados → Explorar.
5. Pulsa **Instalar traducción** y espera al aviso de finalización. Después inicia el juego desde Steam como siempre.

El instalador usa Windows PowerShell y .NET, incluidos en Windows 10 y 11. No requiere instalar Python ni otra copia de Java. Si la carpeta no permite escribir, mueve la instalación del juego a una biblioteca de Steam en la que tu usuario tenga permisos.

Windows está pendiente de una prueba de juego en un equipo real. El instalador solo acepta archivos compatibles con la versión de referencia; si la edición de Windows difiere en alguna entrada modificada, se detendrá sin aplicar cambios. Comunica el aviso completo para añadir compatibilidad.

## Restaurar y actualizar

Para quitar la traducción, abre el mismo instalador y pulsa **Restaurar original**. El respaldo permanece en `%LOCALAPPDATA%\LostFlameES\respaldos`, fuera de la carpeta de Steam.

Una actualización de Steam o la verificación de archivos puede reemplazar la traducción. Si ocurre, busca una versión compatible del parche y vuelve a aplicarla. El instalador comprueba cada entrada modificada antes de escribir: no aplica este parche a una versión desconocida ni restaura un respaldo antiguo encima de una actualización.

Los respaldos se conservan aunque se elimine el ZIP del parche. No se modifican partidas guardadas ni ajustes del juego.

## Instalación en Linux

Requiere Python 3.9 o posterior, sin paquetes adicionales. Extrae el ZIP, cierra el juego y ejecuta en su carpeta:

```sh
python3 instalar.py
```

Detecta bibliotecas de Steam, incluida la instalación Flatpak. Si hay varias instalaciones o no encuentra la tuya:

```sh
python3 instalar.py --carpeta "/ruta/a/Lost Flame"
```

Para restaurar:

```sh
python3 instalar.py restaurar --carpeta "/ruta/a/Lost Flame"
```

Los respaldos se guardan en `~/.local/share/lost-flame-es/respaldos`. En Linux se ajusta también el lanzador para usar UTF-8 y X11, como en la instalación con la que se ha probado esta traducción.

## Estado y correcciones

La versión 0.9.8 cubre los textos inventariados y se ha probado durante varias partidas en Linux. Todavía pueden aparecer textos o nombres en inglés en avisos generados por el juego. Para comunicar un fallo, abre una [incidencia](https://github.com/Sergi-Diaz/lost-flame-es/issues) con una captura, la frase, dónde aparece, el sistema operativo y la versión del juego y del parche.

He tratado de usar un español natural y breve, adecuado al tono del juego, aunque en ocasiones he tirado de tenido que tirar de libertad creativa, pero muy pocas. Se conserva «parry» y se usa «traslación» para blink. Los nombres propios se mantienen cuando corresponde. El glosario está en `traduccion/glosario.json`.

## Contenido y mantenimiento

El paquete contiene diferencias aplicables al JAR de tu instalación, los instaladores y los catálogos de traducción. No contiene el juego completo ni respaldos personales. La referencia actual es el build de Steam **22743398**, app **856570**. Se comprueba el contenido de las entradas que cambian, no el hash del JAR completo, para conservar archivos específicos de cada plataforma.

Los catálogos de `traduccion/` permiten revisar y proponer correcciones. Editarlos no cambia por sí solo el parche publicado: el mantenedor debe integrar los cambios y regenerar `parche/parche.json` con copias locales del JAR original y traducido:

```sh
python3 herramientas/generar_parche.py original.jar traducido.jar parche/parche.json
python3 -m unittest discover -s tests -v
python3 herramientas/empaquetar.py
```

Nunca añadas esos JAR, respaldos o partidas al repositorio. Para preparar una nueva compatibilidad hay que comparar también los cambios del juego, no reutilizar los hashes antiguos.
