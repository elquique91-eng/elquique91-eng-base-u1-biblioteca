# elquique91-eng-base-u1-biblioteca
este es el repositorio para el proyecto de la unidad 1 de topicos,creado por eliud dueñas garcia,trata sobre una biblioteca en la que se guardan los datos del lector, de los libros disponibles y demas
Descripción general

Este proyecto implementa un sistema sencillo de gestión de una biblioteca. Permite:

Registrar libros y lectores.
Realizar movimientos de préstamo y devolución.
Consultar reportes (préstamos activos, vencidos, y una vista de unión obligatoria entre préstamo‑lector‑libro).
Aplicar reglas de negocio (sin stock, lector inactivo, un mismo libro no se puede prestar dos veces al mismo lector, etc.).
Utilizar dos back‑ends de bases de datos: SQLite (local) y MySQL (remoto). La GUI está escrita con Tkinter y se adapta automáticamente al motor disponible.
Estructura del proyecto
library_db/                     # Directorio raíz del proyecto
├─ library_db.py                # Wrapper de SQLite (clase LibraryDB)
├─ mysql_library.py            # Wrapper de MySQL (clase MySQLLibrary)
├─ app.py                      # Aplicación GUI con Tkinter
├─ library_workbench.sql        # Script SQL para crear la base en MySQL Workbench
├─ create_shareable_db.py       # Genera `library.db` con datos de ejemplo
├─ library.db                   # Base de datos SQLite ya generada (shareable)
└─ README.md                   # (Este archivo)
Código Python
library_db.py (SQLite)
Clase LibraryDB que encapsula todas las operaciones contra SQLite.
Métodos principales:
add_book, get_book, list_books, update_book, deactivate_book
add_reader, get_reader, list_readers, update_reader, deactivate_reader
borrow_book, return_book
list_borrows, get_borrows_with_details, get_overdue_borrows
Validaciones de reglas de negocio (stock, lector activo, préstamo duplicado, etc.).
Usa tipo DATE de SQLite; los parámetros de fecha se pasan como cadena YYYY‑MM‑DD.
mysql_library.py (MySQL)
Clase MySQLLibrary con la misma API que LibraryDB pero usando MySQL.
Re‑utiliza la lógica de validación de LibraryDB para mantener consistencia.
Conexión por defecto: root / 1234 en localhost:3306. Puede modificarse en app.py.
app.py (Tkinter GUI)
Interfaz gráfica con tablas para:
Libros – CRUD (alta, edición, desactivación, borrado).
Lectores – CRUD similar.
Movimientos – Préstamos y devoluciones. Al prestar se descuenta una unidad de stock y se verifica la fecha límite (7 días).
Unión Obligatoria – Vista que muestra prestamo + nombre del lector + título del libro.
Reporte de Vencidos – Lista los préstamos activos cuya fecha de vencimiento es anterior a la fecha actual.
Detección automática del motor: al iniciar intenta conectar a MySQL; si falla, carga la base SQLite library.db que se encuentra en la misma carpeta.
Barra superior indica el motor activo (MySQL o SQLite).
Cada pestaña incluye botones Agregar, Actualizar, Eliminar/Desactivar y campos de texto para los atributos.
create_shareable_db.py
Script autónomo que crea una nueva base SQLite limpia (library.db).
Inserta 4 libros, 4 lectores (uno inactivo) y 3 movimientos (dos activos, uno devuelto).
Genera la vista view_borrows_details para inspección externa.
Ejecutar este script vuelve a generar el archivo .db listo para compartir.
SQL – Esquema MySQL Workbench (library_workbench.sql)
sql
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    isbn VARCHAR(20) NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    author VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    total_stock INTEGER NOT NULL,
    available_stock INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
CREATE TABLE readers (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    folio VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    type ENUM('student','docent','outsider') NOT NULL,
    active BOOLEAN DEFAULT TRUE
);
CREATE TABLE movements (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    reader_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date DATE NOT NULL,
    due_date DATE NOT NULL,
    return_date DATE,
    FOREIGN KEY (reader_id) REFERENCES readers(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

Este script es usado por app.py para crear la base en MySQL cuando el usuario selecciona la opción de reinicializar el esquema.

Cómo ejecutar la aplicación Tkinter
Requisitos
Python 3.9 o superior.
Paquetes instalados (ver requirements.txt opcional):
bash
pip install mysql-connector-python   # Sólo si usarás MySQL
Si vas a usar MySQL, asegúrate de que el servidor esté corriendo y que el usuario/contraseña coincidan con los definidos en app.py.
Opcional – generar/renovar el .db
bash
python create_shareable_db.py   # recrea library.db con datos de ejemplo
Ejecutar la GUI
bash
python app.py
La ventana mostrará la barra de estado con el motor activo.
Si MySQL está disponible, la aplicación usará esa base; en caso contrario, cargará automáticamente el SQLite library.db.
Uso básico
Pestaña "Libros": pulsa Añadir para registrar un nuevo libro, Actualizar para modificar datos, Desactivar para marcarlo como inactivo (no se puede prestar).
Pestaña "Lectores": operaciones similares a los libros.
Pestaña "Movimientos": selecciona un lector y un libro, pulsa Prestar (se calcula la fecha de vencimiento a 7 días) o Devolver (se registra la fecha de devolución y se incrementa el stock).
Pestaña "Unión": muestra la vista con nombre del lector + título del libro para cada préstamo activo.
Pestaña "Vencidos": lista los préstamos cuya due_date es anterior a la fecha de hoy.
Salir
Cierra la ventana o pulsa Ctrl‑C en la consola.
Consideraciones importantes
Reglas de negocio están implementadas en los métodos de la capa de datos; la GUI solo llama a esas funciones.
No se permite eliminar un libro o lector que tenga préstamos activos; la acción recomendada es Desactivar.
Las fechas se ingresan como YYYY‑MM‑DD. No se maneja zona horaria ni hora.
En SQLite, el archivo library.db se encuentra en la misma carpeta que app.py. Puedes copiarlo a otro equipo; la aplicación seguirá funcionando sin cambios.
En MySQL, los cambios persisten en el servidor configurado; asegúrate de respaldar la base si la vas a mover.
