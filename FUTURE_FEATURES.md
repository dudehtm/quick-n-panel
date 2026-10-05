# Future Features

Registro de propuestas que no forman parte del comportamiento actual ni del
paquete publicado. Cada propuesta debe conservar la navegacion, la persistencia
y el lenguaje visual existentes antes de implementarse.

## Modo edicion del launcher

Estado: parcialmente implementado como opcion experimental.

El Modo edicion permitiria personalizar visualmente el launcher sin convertir la
configuracion normal en una interfaz compleja.

Implementado:

- elegir si el atajo del launcher abre solo el launcher o tambien despliega
  `Library` o `Categories`;
- activar o desactivar la apertura automatica de `Library` o `Categories`, con una
  sola opcion activa a la vez;
- mostrar el atajo efectivo configurado por el usuario en ambas opciones;

Pendiente:

- elegir que bloques aparecen en el launcher;
- cambiar la posicion de `Library`, `Categories` y `Configure`;
- ordenar categorias directamente desde el popup;
- configurar filtros o grupos visibles en `Library` y `Categories`;
- elegir si las categorias vacias se muestran, se ocultan o empiezan plegadas;
- ajustar columnas, separacion y densidad de las tarjetas;
- seleccionar una estrategia de overflow: scroll, lista o paginacion.

Las opciones de apertura automatica permanecen desactivadas por defecto y solo
una puede activarse a la vez desde las secciones `Library` y `Categories`. La
implementacion experimental conserva el popup principal y reutiliza los
popovers registrados mediante una llamada diferida de la API publica de
Blender; el comportamiento de posicion y apilado puede variar entre versiones
de Blender.

## Navegacion de listas grandes

Estado: aplazado hasta medir el limite real del popup en Blender 5.0, 5.1 y 5.2.

Si una instalacion tiene muchas categorias o una categoria contiene decenas de
tabs, se evaluaran alternativas publicas y estables:

- `UIList` con viewport desplazable;
- paginacion manteniendo las tarjetas actuales;
- busqueda o filtros dentro de la vista activa;
- una vista de administracion separada del launcher compacto.

No se debe prometer un scroll interno para un grid arbitrario mientras Blender no
exponga un contenedor publico que lo soporte.

## Orden visual de categorias

Estado: posible modo edicion.

El orden persistente existente seguira siendo la fuente de verdad. Una edicion
visual futura debe reutilizar los operadores actuales de movimiento y no crear un
segundo orden incompatible con `preferences.groups`.
